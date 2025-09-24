import asyncio
import os
import shutil
import time
import datetime
import subprocess
import tempfile
import threading
import random
import sys
import platform as sys_platform
from typing import Dict, List, Optional, Tuple

from ..models.recording_model import Recording
from .logger import logger


class FileLock:
    """
    文件锁管理器，用于防止多个任务同时操作同一个文件
    """
    _locks = {}
    _lock = threading.Lock()
    
    @classmethod
    def acquire(cls, file_path):
        """获取指定文件路径的锁"""
        with cls._lock:
            if file_path not in cls._locks:
                cls._locks[file_path] = threading.Lock()
            return cls._locks[file_path]
    
    @classmethod
    def release_unused(cls):
        """释放未使用的锁以避免内存泄漏"""
        with cls._lock:
            # 保留所有锁，因为无法确定哪些锁不再使用
            # 这个方法预留给未来可能的优化
            pass


class ThumbnailManager:
    """
    管理直播间缩略图的捕获和存储
    """
    
    def __init__(self, app):
        self.app = app
        self.settings = app.settings
        self.user_config = self.settings.user_config
        
        # 缩略图存储目录
        if getattr(sys, 'frozen', False):
            # 如果是打包后的可执行文件
            base_path = os.path.dirname(sys.executable)
        else:
            # 如果是开发环境
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        self.thumbnail_dir = os.path.join(base_path, "Live preview image")
        os.makedirs(self.thumbnail_dir, exist_ok=True)
        
        # 目录锁，用于保护目录扫描操作
        self.dir_lock = threading.Lock()
        
        # 每个直播间的缩略图捕获任务
        self.thumbnail_tasks: Dict[str, asyncio.Task] = {}
        
        # 缩略图更新间隔（默认60秒）
        try:
            update_interval = self.user_config.get("thumbnail_update_interval", 60)
            # 确保值是整数，如果无法转换，使用默认值60
            self.update_interval = int(update_interval) if isinstance(update_interval, int | str) else 60
            # 确保值在合理范围内
            if self.update_interval < 15:
                #logger.warning(f"缩略图更新间隔过小 ({self.update_interval}秒)，使用最小值15秒")
                self.update_interval = 15
            elif self.update_interval > 300:
                #logger.warning(f"缩略图更新间隔过大 ({self.update_interval}秒)，使用最大值300秒")
                self.update_interval = 300
        except (ValueError, TypeError) as e:
            logger.error(f"初始化时解析缩略图更新间隔出错: {e}，使用默认值60秒")
            self.update_interval = 60
        
        # 每个直播间最多保存的缩略图数量
        self.max_thumbnails_per_room = 3
        
        # 缩略图大小
        self.thumbnail_width = 230
        self.thumbnail_height = 120
        
        # 重试配置
        self.max_retry_attempts = 3  # 最大重试次数
        self.retry_base_delay = 2.0  # 基础重试延迟(秒)
        
        # 设置配置变更监听器
        if hasattr(self.settings, 'add_config_change_listener'):
            self.settings.add_config_change_listener('show_live_thumbnail', self._on_thumbnail_switch_changed)
        
        logger.info(f"缩略图管理器初始化完成，存储目录: {self.thumbnail_dir}")
    
    async def _on_thumbnail_switch_changed(self, key, value):
        """监听全局缩略图开关变化
        
        Args:
            key: 配置键名
            value: 新的配置值
        """
        if key == 'show_live_thumbnail':
            logger.info(f"全局缩略图开关已{'开启' if value else '关闭'}")
            
            if value:  # 开启缩略图
                # 如果有正在录制的任务，为它们启动缩略图捕获
                if hasattr(self.app, 'record_manager'):
                    active_recordings = []
                    for recording in self.app.record_manager.recordings.values():
                        if recording.is_live or recording.recording:
                            active_recordings.append(recording)
                    
                    if active_recordings:
                        logger.info(f"开始为 {len(active_recordings)} 个活跃直播间启动缩略图捕获")
                        for recording in active_recordings:
                            await self.start_thumbnail_capture(recording)
            else:  # 关闭缩略图
                # 停止所有缩略图捕获任务
                await self.stop_all_thumbnail_captures()
    
    async def start_thumbnail_capture(self, recording: Recording):
        """开始为指定直播间捕获缩略图"""
        rec_id = recording.rec_id
        
        # 检查是否应该为这个房间捕获缩略图
        global_thumbnail_enabled = self.user_config.get("show_live_thumbnail", False)
        if not recording.is_thumbnail_enabled(global_thumbnail_enabled):
            logger.info(f"直播间 {recording.streamer_name} (ID: {rec_id}) 的缩略图功能已关闭，跳过启动缩略图捕获")
            return
        
        # 如果已经有任务在运行，先停止它
        if rec_id in self.thumbnail_tasks and not self.thumbnail_tasks[rec_id].done():
            self.thumbnail_tasks[rec_id].cancel()
            try:
                await self.thumbnail_tasks[rec_id]
            except asyncio.CancelledError:
                pass
        
        # 创建新的缩略图捕获任务
        self.thumbnail_tasks[rec_id] = asyncio.create_task(
            self._thumbnail_capture_loop(recording)
        )
        logger.info(f"开始为直播间 {recording.streamer_name} (ID: {rec_id}) 捕获缩略图")
    
    async def stop_thumbnail_capture(self, recording: Recording):
        """停止为指定直播间捕获缩略图"""
        rec_id = recording.rec_id
        if rec_id in self.thumbnail_tasks and not self.thumbnail_tasks[rec_id].done():
            self.thumbnail_tasks[rec_id].cancel()
            try:
                await self.thumbnail_tasks[rec_id]
            except asyncio.CancelledError:
                pass
            logger.info(f"已停止为直播间 {recording.streamer_name} (ID: {rec_id}) 捕获缩略图")
    
    async def stop_all_thumbnail_captures(self):
        """停止所有直播间的缩略图捕获"""
        for rec_id, task in list(self.thumbnail_tasks.items()):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self.thumbnail_tasks.clear()
        logger.info("已停止所有直播间的缩略图捕获")
    
    async def _thumbnail_capture_loop(self, recording: Recording):
        """缩略图捕获循环"""
        rec_id = recording.rec_id
        
        while True:
            try:
                # 检查是否应该继续捕获缩略图
                global_thumbnail_enabled = self.user_config.get("show_live_thumbnail", False)
                if not recording.is_thumbnail_enabled(global_thumbnail_enabled):
                    logger.info(f"缩略图功能已关闭（全局: {global_thumbnail_enabled}, 房间设置: {recording.thumbnail_enabled}），停止为直播间 {recording.streamer_name} 捕获缩略图")
                    break
                
                # 检查录制状态
                if not recording.is_live and not recording.recording:
                    #logger.debug(f"直播间 {recording.streamer_name} 未在直播，跳过缩略图捕获")
                    await asyncio.sleep(self.update_interval)
                    continue
                
                # 获取最新的更新间隔设置，安全地将值转换为整数
                try:
                    update_interval = self.user_config.get("thumbnail_update_interval", 60)
                    # 确保值是整数，如果无法转换，使用默认值60
                    self.update_interval = int(update_interval) if isinstance(update_interval, int | str) else 60
                    # 确保值在合理范围内
                    if self.update_interval < 15:
                        #logger.warning(f"缩略图更新间隔过小 ({self.update_interval}秒)，使用最小值15秒")
                        self.update_interval = 15
                    elif self.update_interval > 300:
                        #logger.warning(f"缩略图更新间隔过大 ({self.update_interval}秒)，使用最大值300秒")
                        self.update_interval = 300
                except (ValueError, TypeError) as e:
                    logger.error(f"解析缩略图更新间隔时出错: {e}，使用默认值60秒")
                    self.update_interval = 60
                
                # 获取直播流URL
                stream_url = None
                try:
                    # 使用get_stream_url方法获取直播流URL
                    stream_url, error_msg = await self.app.record_manager.get_stream_url(recording)
                    if error_msg:
                        logger.warning(f"获取直播流URL时发生警告: {error_msg}")
                    
                    if not stream_url:
                        #logger.debug(f"未获取到直播间 {recording.streamer_name} 的流URL，跳过缩略图捕获")
                        await asyncio.sleep(self.update_interval)
                        continue
                except Exception as e:
                    logger.error(f"获取直播流URL失败: {e}")
                    await asyncio.sleep(self.update_interval)
                    continue
                
                # 捕获缩略图（带重试机制）
                thumbnail_path, success = await self._capture_thumbnail_with_retry(stream_url, recording)
                
                if thumbnail_path:
                    # 清理旧的缩略图
                    await self._cleanup_old_thumbnails(recording)
                    
                    # 通知UI更新缩略图
                    await self._update_ui_thumbnail(recording, thumbnail_path)
                
                # 等待下一次捕获
                await asyncio.sleep(self.update_interval)
            
            except asyncio.CancelledError:
                logger.info(f"直播间 {recording.streamer_name} 的缩略图捕获任务被取消")
                break
            except Exception as e:
                logger.error(f"缩略图捕获过程中发生错误: {e}")
                await asyncio.sleep(self.update_interval)
    
    async def _capture_thumbnail_with_retry(self, stream_url: str, recording: Recording) -> Tuple[Optional[str], bool]:
        """使用重试机制捕获缩略图
        
        Args:
            stream_url: 直播流URL
            recording: 录制对象
            
        Returns:
            Tuple[Optional[str], bool]: (缩略图路径, 是否成功)
        """
        attempt = 0
        max_attempts = self.max_retry_attempts
        base_delay = self.retry_base_delay
        
        while attempt < max_attempts:
            attempt += 1
            
            # 第一次尝试
            if attempt == 1:
                logger.debug(f"开始为直播间 {recording.streamer_name} 捕获缩略图")
            # 重试
            else:
                # 计算递增延迟（加入随机抖动避免同步问题）
                delay = base_delay * (2 ** (attempt - 2)) + random.uniform(0, 0.5)
                delay = min(delay, 10)  # 最大延迟不超过10秒
                logger.info(f"缩略图捕获重试 #{attempt}/{max_attempts} (延迟 {delay:.1f}秒)，直播间: {recording.streamer_name}")
                
                # 等待一段时间后重试
                await asyncio.sleep(delay)
            
            # 尝试捕获缩略图
            thumbnail_path = await self._capture_thumbnail(stream_url, recording)
            
            # 成功捕获
            if thumbnail_path:
                # 如果是重试成功，记录日志
                if attempt > 1:
                    logger.info(f"重试成功：第 {attempt} 次尝试为直播间 {recording.streamer_name} 捕获缩略图")
                return thumbnail_path, True
        
        # 所有重试都失败
        if attempt > 1:
            logger.warning(f"重试失败：尝试 {attempt} 次后仍未能为直播间 {recording.streamer_name} 捕获缩略图")
        return None, False
    
    async def _capture_thumbnail(self, stream_url: str, recording: Recording) -> Optional[str]:
        """使用ffmpeg捕获直播流的一帧作为缩略图"""
        rec_id = recording.rec_id
        timestamp = int(time.time())
        thumbnail_filename = f"{rec_id}_{timestamp}.jpg"
        thumbnail_path = os.path.join(self.thumbnail_dir, thumbnail_filename)
        
        try:
            # 使用ffmpeg捕获一帧作为缩略图
            cmd = [
                "ffmpeg",
                "-y",
                "-v", "error",
                "-i", stream_url,
                "-frames:v", "1",
                "-q:v", "2",
                "-vf", f"scale={self.thumbnail_width}:{self.thumbnail_height}",
                thumbnail_path
            ]
            
            # 添加代理设置（如果需要）
            if recording.use_proxy and self.user_config.get("enable_proxy"):
                proxy_address = self.user_config.get("proxy_address")
                if proxy_address and proxy_address.startswith('http://'):
                    cmd.insert(1, "-http_proxy")
                    cmd.insert(2, proxy_address)
            
            # 记录完整的ffmpeg命令（隐藏URL中的敏感信息）
            safe_cmd = cmd.copy()
            if stream_url in safe_cmd:
                # 替换URL以隐藏敏感信息，保留协议头
                url_parts = stream_url.split("://", 1)
                if len(url_parts) > 1:
                    protocol = url_parts[0]
                    safe_cmd[safe_cmd.index(stream_url)] = f"{protocol}://[已隐藏]"
                else:
                    safe_cmd[safe_cmd.index(stream_url)] = "[已隐藏URL]"
            
            #logger.debug(f"执行ffmpeg命令: {' '.join(safe_cmd)}")
            
            # 获取文件锁并运行ffmpeg命令
            with FileLock.acquire(thumbnail_path):
                # 运行ffmpeg命令，隐藏控制台窗口
                if sys_platform.system() == "Windows":
                    # Windows下使用CREATE_NO_WINDOW标志隐藏控制台窗口
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                else:
                    # Linux/macOS下使用start_new_session隐藏控制台窗口
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        start_new_session=True
                    )
                
                # 设置超时
                try:
                    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15.0)
                    stdout_text = stdout.decode('utf-8', errors='ignore') if stdout else ""
                    stderr_text = stderr.decode('utf-8', errors='ignore') if stderr else ""
                    
                    # 记录命令输出
                    if stdout_text:
                        logger.debug(f"ffmpeg标准输出: {stdout_text}")
                    if stderr_text:
                        logger.debug(f"ffmpeg错误输出: {stderr_text}")
                except asyncio.TimeoutError:
                    process.kill()
                    logger.error(f"捕获缩略图超时，已终止进程。直播间: {recording.streamer_name}, URL类型: {stream_url[:10]}...")
                    return None
                
                # 检查ffmpeg是否成功
                if process.returncode != 0:
                    logger.error(f"ffmpeg捕获缩略图失败(返回码:{process.returncode}): {stderr_text}")
                    return None
                
                # 检查文件是否成功创建
                if not os.path.exists(thumbnail_path):
                    logger.error(f"缩略图文件未创建: {thumbnail_path}")
                    return None
                    
                file_size = os.path.getsize(thumbnail_path)
                if file_size == 0:
                    logger.error(f"缩略图文件创建但为空(0字节): {thumbnail_path}")
                    return None
                    
                logger.info(f"成功为直播间 {recording.streamer_name} 捕获缩略图: {thumbnail_path} (大小: {file_size} 字节)")
                return thumbnail_path
            
        except Exception as e:
            import traceback
            logger.error(f"捕获缩略图过程中发生错误: {e}\n{traceback.format_exc()}")
            return None
    
    async def _cleanup_old_thumbnails(self, recording: Recording):
        """清理旧的缩略图，保持每个直播间最多只有指定数量的缩略图"""
        rec_id = recording.rec_id
        try:
            # 使用目录锁保护目录扫描操作
            with self.dir_lock:
                # 查找该直播间的所有缩略图
                thumbnails = []
                for filename in os.listdir(self.thumbnail_dir):
                    if filename.startswith(f"{rec_id}_") and filename.endswith(".jpg"):
                        file_path = os.path.join(self.thumbnail_dir, filename)
                        thumbnails.append((file_path, os.path.getmtime(file_path)))
                
                # 按修改时间排序（最新的在后面）
                thumbnails.sort(key=lambda x: x[1])
            
            # 删除多余的缩略图（保留最新的N个）
            if len(thumbnails) > self.max_thumbnails_per_room:
                for i in range(len(thumbnails) - self.max_thumbnails_per_room):
                    # 使用文件锁保护文件删除操作
                    with FileLock.acquire(thumbnails[i][0]):
                        try:
                            if os.path.exists(thumbnails[i][0]):  # 再次检查文件是否存在
                                os.remove(thumbnails[i][0])
                                logger.debug(f"删除旧缩略图: {thumbnails[i][0]}")
                        except Exception as e:
                            logger.error(f"删除旧缩略图失败: {e}")
        except Exception as e:
            logger.error(f"清理旧缩略图过程中发生错误: {e}")
    
    async def _update_ui_thumbnail(self, recording: Recording, thumbnail_path: str):
        """更新UI中的缩略图"""
        try:
            # 使用记录卡片管理器更新缩略图
            if hasattr(self.app, 'record_card_manager'):
                # 调用记录卡片管理器的update_thumbnail方法更新UI中的缩略图
                self.app.page.run_task(self.app.record_card_manager.update_thumbnail, recording, thumbnail_path)
        except Exception as e:
            logger.error(f"更新UI缩略图过程中发生错误: {e}")
    
    def get_latest_thumbnail(self, recording: Recording) -> Optional[str]:
        """获取指定直播间的最新缩略图路径"""
        rec_id = recording.rec_id
        try:
            # 使用目录锁保护目录扫描操作
            with self.dir_lock:
                # 查找该直播间的所有缩略图
                thumbnails = []
                for filename in os.listdir(self.thumbnail_dir):
                    if filename.startswith(f"{rec_id}_") and filename.endswith(".jpg"):
                        file_path = os.path.join(self.thumbnail_dir, filename)
                        # 检查文件是否可读
                        try:
                            if os.path.exists(file_path) and os.access(file_path, os.R_OK):
                                thumbnails.append((file_path, os.path.getmtime(file_path)))
                        except Exception as e:
                            logger.warning(f"检查缩略图文件访问权限时出错: {e}")
                
                # 按修改时间排序
                thumbnails.sort(key=lambda x: x[1])
                
                # 返回最新的缩略图路径
                if thumbnails:
                    return thumbnails[-1][0]
        except Exception as e:
            logger.error(f"获取最新缩略图路径过程中发生错误: {e}")
        
        return None
    
    def delete_thumbnails_for_recording(self, rec_id: str) -> int:
        """删除指定直播间的所有缩略图文件
        
        Args:
            rec_id: 录制项ID
            
        Returns:
            int: 删除的文件数量
        """
        try:
            # 使用目录锁保护目录扫描操作
            with self.dir_lock:
                # 查找该直播间的所有缩略图
                thumbnail_files = []
                for filename in os.listdir(self.thumbnail_dir):
                    if filename.startswith(f"{rec_id}_") and filename.endswith(".jpg"):
                        file_path = os.path.join(self.thumbnail_dir, filename)
                        thumbnail_files.append(file_path)
            
            # 删除所有找到的缩略图
            deleted_count = 0
            for file_path in thumbnail_files:
                # 使用文件锁保护文件删除操作
                with FileLock.acquire(file_path):
                    try:
                        if os.path.exists(file_path):  # 再次检查文件是否存在
                            os.remove(file_path)
                            deleted_count += 1
                            #logger.debug(f"删除缩略图: {file_path}")
                    except Exception as e:
                        logger.error(f"删除缩略图文件失败: {file_path}, 错误: {e}")
            
            if deleted_count > 0:
                logger.info(f"已删除直播间 {rec_id} 的 {deleted_count} 个缩略图文件")
            
            return deleted_count
        except Exception as e:
            logger.error(f"删除直播间缩略图过程中发生错误: {e}")
            return 0
            
    def delete_thumbnails_for_recordings(self, rec_ids: List[str]) -> int:
        """批量删除多个直播间的所有缩略图文件
        
        Args:
            rec_ids: 录制项ID列表
            
        Returns:
            int: 删除的文件总数
        """
        total_deleted = 0
        for rec_id in rec_ids:
            total_deleted += self.delete_thumbnails_for_recording(rec_id)
        
        if total_deleted > 0:
            logger.info(f"批量删除了 {len(rec_ids)} 个直播间的共 {total_deleted} 个缩略图文件")
        
        return total_deleted
    
    async def cleanup_old_thumbnails(self, max_age_days=1):
        """清理指定天数前的缩略图文件
        
        Args:
            max_age_days: 缩略图文件的最大保留天数，默认为1天
        
        Returns:
            int: 删除的文件数量
        """
        try:
            now = time.time()
            max_age_seconds = max_age_days * 24 * 60 * 60
            cutoff_time = now - max_age_seconds
            
            # 使用目录锁保护目录扫描操作
            with self.dir_lock:
                # 查找所有过期的缩略图
                thumbnails_to_delete = []
                for filename in os.listdir(self.thumbnail_dir):
                    if filename.endswith(".jpg"):
                        file_path = os.path.join(self.thumbnail_dir, filename)
                        try:
                            file_mod_time = os.path.getmtime(file_path)
                            if file_mod_time < cutoff_time:
                                thumbnails_to_delete.append(file_path)
                        except Exception as e:
                            logger.warning(f"获取文件修改时间失败: {file_path}, 错误: {e}")
            
            # 删除所有过期的缩略图
            deleted_count = 0
            for file_path in thumbnails_to_delete:
                # 使用文件锁保护文件删除操作
                with FileLock.acquire(file_path):
                    try:
                        if os.path.exists(file_path):  # 再次检查文件是否存在
                            os.remove(file_path)
                            deleted_count += 1
                    except Exception as e:
                        logger.error(f"删除过期缩略图文件失败: {file_path}, 错误: {e}")
            
            if deleted_count > 0:
                logger.info(f"已清理 {deleted_count} 个超过 {max_age_days} 天的缩略图文件")
            
            return deleted_count
        except Exception as e:
            logger.error(f"清理过期缩略图过程中发生错误: {e}")
            return 0 