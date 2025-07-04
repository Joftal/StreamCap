import asyncio
import os
import threading
import time
import signal
import psutil
import sys

from .utils.logger import logger


class BackgroundService:

    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = BackgroundService()
        return cls._instance
    
    def __init__(self):
        self.tasks = []
        self.is_running = False
        self.worker_thread = None
        self._lock = threading.Lock()
    
    def add_task(self, task_func, *args, **kwargs):
        with self._lock:
            self.tasks.append((task_func, args, kwargs))
            logger.info(f"添加后台任务: {task_func.__name__}")
        
        if not self.is_running:
            self.start()
    
    def start(self):
        if self.is_running:
            return
        
        with self._lock:
            if not self.is_running:  # 双重检查锁定
                self.is_running = True
                self.worker_thread = threading.Thread(target=self._process_tasks, daemon=False)
                self.worker_thread.start()
                logger.info("后台服务已启动")
    
    def _process_tasks(self):
        while True:
            task = None
            with self._lock:
                if not self.tasks:
                    self.is_running = False
                    logger.info("所有后台任务已完成，服务停止")
                    break
                task_func, args, kwargs = self.tasks.pop(0)
                task = (task_func, args, kwargs)
            
            if task:
                task_func, args, kwargs = task
                try:
                    logger.info(f"执行后台任务: {task_func.__name__}")
                    task_func(*args, **kwargs)
                    logger.info(f"后台任务完成: {task_func.__name__}")
                except Exception as e:
                    logger.error(f"后台任务执行失败: {e}")


class AsyncProcessManager:
    def __init__(self):
        self.ffmpeg_processes = []
        self._lock = asyncio.Lock()
        self._process_start_time = {}  # 记录进程启动时间
        self._is_frozen = getattr(sys, 'frozen', False)  # 检查是否为打包环境
        
        env_info = "打包环境" if self._is_frozen else "开发环境"
        logger.info(f"进程管理器初始化完成 - 运行于{env_info}")
        logger.info(f"系统信息: {sys.platform}, Python版本: {sys.version}")

    async def add_process(self, process):
        async with self._lock:
            # 检查进程是否有效
            if process is None:
                logger.warning("尝试添加无效进程")
                return
                
            # 检查进程是否已经存在
            for existing_process in self.ffmpeg_processes:
                if existing_process.pid == process.pid:
                    logger.warning(f"进程已存在，不重复添加: PID={process.pid}")
                    return
            
            # 验证进程是否真正运行
            try:
                if process.returncode is not None:
                    logger.warning(f"进程已终止，不添加: PID={process.pid}, returncode={process.returncode}")
                    return
                    
                # 使用psutil验证进程是否存在
                if not psutil.pid_exists(process.pid):
                    logger.warning(f"进程不存在于系统中，不添加: PID={process.pid}")
                    return
                    
                # 获取进程信息
                try:
                    proc = psutil.Process(process.pid)
                    proc_info = f"名称: {proc.name()}, 状态: {proc.status()}"
                    logger.info(f"系统进程验证通过: PID={process.pid}, {proc_info}")
                except psutil.NoSuchProcess:
                    logger.warning(f"无法获取进程信息，但仍添加: PID={process.pid}")
            except Exception as e:
                logger.error(f"验证进程时出错: {e}")
                    
            # 添加新进程
            self.ffmpeg_processes.append(process)
            self._process_start_time[process.pid] = time.time()
            
            # 清理已经终止的进程
            self._clean_terminated_processes()
            
            # 输出详细日志
            active_count = len([p for p in self.ffmpeg_processes if p.returncode is None])
            logger.info(f"进程管理 - 添加新进程: PID={process.pid}, 当前总进程数: {len(self.ffmpeg_processes)}, 活跃进程数: {active_count}")
            logger.debug(f"当前所有进程PID列表: {[p.pid for p in self.ffmpeg_processes]}")

    def _clean_terminated_processes(self):
        """清理已终止的进程，但保留进程对象以便查询状态"""
        terminated_pids = []
        for process in self.ffmpeg_processes:
            if process.returncode is not None:
                terminated_pids.append(process.pid)
        
        if terminated_pids:
            logger.debug(f"检测到已终止的进程: {terminated_pids}")
            
    async def _verify_processes(self):
        """验证所有进程的状态"""
        logger.debug("开始验证所有进程状态")
        for process in self.ffmpeg_processes:
            try:
                # 检查进程状态
                if process.returncode is None:
                    # 检查系统中是否存在该进程
                    if psutil.pid_exists(process.pid):
                        try:
                            proc = psutil.Process(process.pid)
                            status = proc.status()
                            logger.debug(f"进程状态验证: PID={process.pid}, 状态={status}")
                        except psutil.NoSuchProcess:
                            logger.warning(f"进程在系统中不存在，但在列表中标记为活跃: PID={process.pid}")
                    else:
                        logger.warning(f"进程不存在于系统中，但在列表中标记为活跃: PID={process.pid}")
                        # 在打包环境中，可能需要手动更新进程状态
                        if self._is_frozen:
                            logger.info(f"在打包环境中，手动将进程标记为已终止: PID={process.pid}")
                            # 注意：这里不直接修改process.returncode，因为它可能是只读的
                            # 而是在后续的get_active_processes_count中特殊处理
            except Exception as e:
                logger.error(f"验证进程状态时出错: PID={process.pid}, 错误: {e}")

    async def cleanup(self):
        """清理所有进程，确保它们被正确终止"""
        async with self._lock:
            processes_to_clean = self.ffmpeg_processes.copy()
            self.ffmpeg_processes.clear()
            logger.info(f"开始清理所有进程，总数: {len(processes_to_clean)}")
            
        cleanup_tasks = []
        for process in processes_to_clean:
            task = asyncio.create_task(self._cleanup_process(process))
            cleanup_tasks.append(task)
        
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks)
            logger.debug(f"所有进程清理完成，共清理 {len(cleanup_tasks)} 个进程")
    
    async def _cleanup_process(self, process):
        """清理单个进程，使用更可靠的方法确保进程终止"""
        try:
            if process.returncode is None:
                pid = process.pid
                logger.debug(f"正在终止进程 PID={pid}")
                
                # 首先尝试正常退出FFmpeg
                if os.name == "nt":
                    if process.stdin:
                        try:
                            process.stdin.write(b"q")
                            await asyncio.wait_for(process.stdin.drain(), timeout=2.0)
                        except (asyncio.TimeoutError, ConnectionError, BrokenPipeError):
                            # 如果无法通过stdin退出，则继续使用信号
                            pass
                
                # 发送SIGTERM信号
                try:
                    process.terminate()
                except ProcessLookupError:
                    # 进程可能已经不存在
                    logger.debug(f"进程 PID={pid} 不存在，可能已经终止")
                    return
                
                # 等待进程正常终止
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                    logger.debug(f"进程 PID={pid} 已正常终止")
                    return
                except asyncio.TimeoutError:
                    logger.warning(f"进程 PID={pid} 未能在超时时间内终止，尝试强制终止")
                
                # 如果进程仍在运行，尝试发送SIGKILL信号
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=3.0)
                    logger.debug(f"进程 PID={pid} 已被强制终止")
                except (asyncio.TimeoutError, ProcessLookupError):
                    # 如果进程仍然无法终止，尝试使用psutil
                    self._force_kill_process(pid)
            
            # 移除进程启动时间记录
            if process.pid in self._process_start_time:
                del self._process_start_time[process.pid]
                
        except Exception as e:
            logger.error(f"进程清理出错: {e}")
    
    def _force_kill_process(self, pid):
        """使用psutil强制终止进程及其子进程"""
        try:
            # 检查进程是否仍然存在
            if not psutil.pid_exists(pid):
                logger.debug(f"进程 PID={pid} 不存在，无需强制终止")
                return
            
            # 获取进程对象
            p = psutil.Process(pid)
            
            # 先终止子进程
            children = p.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                    logger.debug(f"已终止子进程 PID={child.pid}")
                except psutil.NoSuchProcess:
                    pass
            
            # 终止主进程
            p.kill()
            logger.debug(f"已通过psutil强制终止进程 PID={pid}")
        except psutil.NoSuchProcess:
            logger.debug(f"进程 PID={pid} 不存在，可能已经终止")
        except Exception as e:
            logger.error(f"使用psutil终止进程 PID={pid} 时出错: {e}")
    
    async def get_running_processes_info(self):
        """获取所有运行中进程的信息，包括运行时间"""
        running_processes = []
        current_time = time.time()
        
        # 先验证所有进程
        await self._verify_processes()
        
        async with self._lock:
            # 检查每个进程的状态
            for process in self.ffmpeg_processes:
                try:
                    # 检查进程是否仍在运行
                    if process.returncode is None:
                        # 在打包环境中额外验证
                        if self._is_frozen and not psutil.pid_exists(process.pid):
                            logger.debug(f"打包环境中检测到进程不存在，跳过: PID={process.pid}")
                            continue
                            
                        pid = process.pid
                        start_time = self._process_start_time.get(pid, current_time)
                        running_time = current_time - start_time
                        running_processes.append({
                            "pid": pid,
                            "running_time": running_time,
                            "running_time_str": self._format_time(running_time)
                        })
                except Exception as e:
                    logger.error(f"获取进程信息时出错: {e}")
        
        logger.debug(f"获取到运行中进程信息: {len(running_processes)} 个进程")
        return running_processes
    
    async def get_active_processes_count(self):
        """获取当前活跃进程数量"""
        # 先验证所有进程
        await self._verify_processes()
        
        async with self._lock:
            # 检查每个进程的状态
            active_processes = []
            for p in self.ffmpeg_processes:
                if p.returncode is None:
                    # 在打包环境中额外验证
                    if self._is_frozen and not psutil.pid_exists(p.pid):
                        continue
                    active_processes.append(p)
                    
            active_count = len(active_processes)
            total_count = len(self.ffmpeg_processes)
            
            # 输出详细日志
            if active_count > 0:
                logger.debug(f"当前活跃进程数: {active_count}/{total_count}, 活跃进程PID: {[p.pid for p in active_processes]}")
            else:
                logger.debug(f"当前没有活跃进程, 总进程数: {total_count}")
                
            return active_count
            
    async def check_system_processes(self):
        """检查系统中的所有进程，尝试找出FFmpeg相关进程"""
        try:
            logger.info("开始检查系统中的所有进程")
            ffmpeg_processes = []
            python_processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    # 检查是否为FFmpeg进程
                    if 'ffmpeg' in proc.info['name'].lower():
                        ffmpeg_processes.append(proc.info)
                        logger.info(f"发现FFmpeg进程: PID={proc.info['pid']}, 名称={proc.info['name']}")
                        
                    # 检查是否为Python进程
                    if 'python' in proc.info['name'].lower():
                        python_processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
                    
            logger.info(f"系统中发现 {len(ffmpeg_processes)} 个FFmpeg进程")
            logger.info(f"系统中发现 {len(python_processes)} 个Python进程")
            
            # 检查我们的进程列表中的进程是否存在于系统中
            for process in self.ffmpeg_processes:
                if process.returncode is None:
                    pid_exists = psutil.pid_exists(process.pid)
                    logger.info(f"我们的进程列表中PID={process.pid}, 系统中存在: {pid_exists}")
                    
            return {
                'ffmpeg_processes': ffmpeg_processes,
                'python_processes': python_processes
            }
        except Exception as e:
            logger.error(f"检查系统进程时出错: {e}")
            return {'error': str(e)}
    
    @staticmethod
    def _format_time(seconds):
        """将秒数格式化为可读的时间字符串"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}小时 {minutes}分钟 {seconds}秒"
        elif minutes > 0:
            return f"{minutes}分钟 {seconds}秒"
        else:
            return f"{seconds}秒"
