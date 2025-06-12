import asyncio
import re
import os
import sys
import time
import psutil
import subprocess
from datetime import datetime

# 模拟Recording类
class Recording:
    def __init__(self):
        self.speed = "X KB/s"
        self.rec_id = "test123"
        self.recording = True
        self.recording_dir = "./test_output"

# 测试函数：从ffmpeg输出中提取速度信息
async def extract_speed_from_ffmpeg_output(ffmpeg_process):
    """从ffmpeg进程的输出中提取下载速度"""
    pattern = r"speed=\s*([0-9.]+)x"  # ffmpeg速度输出通常格式为"speed=1.2x"
    speed_pattern = r"bitrate=\s*([0-9.]+)(k|m)bits/s"  # 比特率通常为"bitrate= 1200kbits/s"
    
    if ffmpeg_process.stderr:
        try:
            line = await ffmpeg_process.stderr.readline()
            line_str = line.decode('utf-8', errors='ignore')
            
            print(f"FFmpeg输出: {line_str.strip()}")
            
            # 尝试匹配速度
            speed_match = re.search(pattern, line_str)
            if speed_match:
                speed_value = speed_match.group(1)
                print(f"找到速度: {speed_value}x")
                return speed_value + "x"
            
            # 尝试匹配比特率
            bitrate_match = re.search(speed_pattern, line_str)
            if bitrate_match:
                bitrate_value = bitrate_match.group(1)
                unit = bitrate_match.group(2).upper()
                print(f"找到比特率: {bitrate_value}{unit}bits/s")
                
                # 转换比特率到KB/s (8 bits = 1 byte)
                try:
                    if unit == "k":
                        kb_per_sec = float(bitrate_value) / 8
                        return f"{kb_per_sec:.1f} KB/s"
                    elif unit == "m":
                        mb_per_sec = float(bitrate_value) / 8
                        kb_per_sec = mb_per_sec * 1024
                        return f"{kb_per_sec:.1f} KB/s"
                except Exception as e:
                    print(f"转换比特率出错: {e}")
            
            return None
        except Exception as e:
            print(f"解析FFmpeg输出出错: {e}")
            return None
    return None

# 方法3：使用psutil监测进程IO（改进版）
async def monitor_process_io(pid, interval=1.0):
    """使用psutil监测进程的IO读写速度"""
    try:
        if not psutil.pid_exists(pid):
            print(f"进程不存在: {pid}")
            return "0 KB/s"
        
        # 获取进程对象
        process = psutil.Process(pid)
        
        # 获取初始IO计数
        try:
            initial_io = process.io_counters()
        except (psutil.AccessDenied, psutil.NoSuchProcess) as e:
            print(f"无法访问进程IO信息: {e}")
            return "0 KB/s"
        
        # 等待指定的时间间隔
        await asyncio.sleep(interval)
        
        # 再次检查进程是否存在
        if not psutil.pid_exists(pid):
            print(f"进程已终止: {pid}")
            return "0 KB/s"
        
        # 获取当前IO计数
        try:
            current_io = process.io_counters()
        except (psutil.AccessDenied, psutil.NoSuchProcess) as e:
            print(f"无法访问进程IO信息: {e}")
            return "0 KB/s"
        
        # 计算读写速度
        read_bytes = current_io.read_bytes - initial_io.read_bytes
        write_bytes = current_io.write_bytes - initial_io.write_bytes
        total_bytes = read_bytes + write_bytes  # 总IO流量
        
        # 计算每秒字节数
        bytes_per_sec = total_bytes / interval
        
        # 根据速度大小选择合适的单位
        if bytes_per_sec >= 1024 * 1024 * 1024:  # GB/s
            return f"{bytes_per_sec / (1024 * 1024 * 1024):.2f} GB/s"
        elif bytes_per_sec >= 1024 * 1024:  # MB/s
            return f"{bytes_per_sec / (1024 * 1024):.2f} MB/s"
        elif bytes_per_sec >= 1024:  # KB/s
            return f"{bytes_per_sec / 1024:.2f} KB/s"
        else:  # B/s
            return f"{bytes_per_sec:.2f} B/s"
    except Exception as e:
        print(f"监测进程IO出错: {e}")
        return "0 KB/s"

# 监测子进程的IO（递归）
async def monitor_process_tree_io(pid, interval=1.0):
    """监测进程及其所有子进程的IO总和"""
    try:
        if not psutil.pid_exists(pid):
            return "0 KB/s"
        
        # 获取主进程和所有子进程
        process = psutil.Process(pid)
        all_processes = [process]
        
        try:
            children = process.children(recursive=True)
            all_processes.extend(children)
        except (psutil.AccessDenied, psutil.NoSuchProcess) as e:
            print(f"获取子进程时出错: {e}")
        
        # 获取所有进程的初始IO计数
        initial_io_total = {"read_bytes": 0, "write_bytes": 0}
        for proc in all_processes:
            try:
                if proc.is_running():
                    io = proc.io_counters()
                    initial_io_total["read_bytes"] += io.read_bytes
                    initial_io_total["write_bytes"] += io.write_bytes
            except (psutil.AccessDenied, psutil.NoSuchProcess) as e:
                continue
        
        # 等待指定的时间间隔
        await asyncio.sleep(interval)
        
        # 获取所有进程的当前IO计数
        current_io_total = {"read_bytes": 0, "write_bytes": 0}
        for proc in all_processes:
            try:
                if proc.is_running():
                    io = proc.io_counters()
                    current_io_total["read_bytes"] += io.read_bytes
                    current_io_total["write_bytes"] += io.write_bytes
            except (psutil.AccessDenied, psutil.NoSuchProcess) as e:
                continue
        
        # 计算总IO速度
        read_diff = current_io_total["read_bytes"] - initial_io_total["read_bytes"]
        write_diff = current_io_total["write_bytes"] - initial_io_total["write_bytes"]
        total_diff = read_diff + write_diff
        
        # 计算每秒字节数
        bytes_per_sec = total_diff / interval
        
        # 输出详细信息
        print(f"IO详情 - 读取: {read_diff/interval/1024:.2f} KB/s, 写入: {write_diff/interval/1024:.2f} KB/s, 总计: {bytes_per_sec/1024:.2f} KB/s")
        
        # 根据速度大小选择合适的单位
        if bytes_per_sec >= 1024 * 1024 * 1024:  # GB/s
            return f"{bytes_per_sec / (1024 * 1024 * 1024):.2f} GB/s"
        elif bytes_per_sec >= 1024 * 1024:  # MB/s
            return f"{bytes_per_sec / (1024 * 1024):.2f} MB/s"
        elif bytes_per_sec >= 1024:  # KB/s
            return f"{bytes_per_sec / 1024:.2f} KB/s"
        else:  # B/s
            return f"{bytes_per_sec:.2f} B/s"
    except Exception as e:
        print(f"监测进程树IO出错: {e}")
        return "0 KB/s"

# 主函数：运行测试
async def run_test():
    recording = Recording()
    print(f"初始速度值: {recording.speed}")
    
    # 创建输出目录
    os.makedirs(recording.recording_dir, exist_ok=True)
    output_file = os.path.join(recording.recording_dir, "test_video.ts")
    
    # 构建ffmpeg命令 - 使用测试视频流
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", "https://vjs.zencdn.net/v/oceans.mp4",  # 测试视频URL
        "-c", "copy",
        "-f", "mpegts",
        output_file
    ]
    
    print(f"运行命令: {' '.join(ffmpeg_cmd)}")
    
    # 启动ffmpeg进程
    ffmpeg_process = await asyncio.create_subprocess_exec(
        *ffmpeg_cmd,
        stderr=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE
    )
    
    print(f"FFmpeg进程启动，PID: {ffmpeg_process.pid}")
    
    # 监测循环
    start_time = time.time()
    try:
        while recording.recording and time.time() - start_time < 30:  # 最多运行30秒
            # 优先使用方法1: 监测进程树的IO（包括子进程）
            if psutil.pid_exists(ffmpeg_process.pid):
                process_tree_speed = await monitor_process_tree_io(ffmpeg_process.pid)
                print(f"从进程树IO获取速度: {process_tree_speed}")
                # 优先使用IO监测的速度
                recording.speed = process_tree_speed
            
            # 备选方法2: 从ffmpeg输出获取速度
            speed_from_output = await extract_speed_from_ffmpeg_output(ffmpeg_process)
            if speed_from_output:
                print(f"从FFmpeg输出获取速度: {speed_from_output}")
                # 只有当IO监测失败时才使用
                if recording.speed == "0 KB/s" or recording.speed == "0.00 B/s":
                    recording.speed = speed_from_output
            
            print(f"当前Recording对象速度: {recording.speed}")
            print("-" * 50)
            await asyncio.sleep(1)
    except Exception as e:
        print(f"监测过程出错: {e}")
    finally:
        # 停止ffmpeg进程
        if ffmpeg_process.returncode is None:
            print("正在停止FFmpeg进程...")
            try:
                ffmpeg_process.terminate()
                await asyncio.wait_for(ffmpeg_process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                print("FFmpeg进程未能正常终止，尝试强制终止")
                ffmpeg_process.kill()
            except Exception as e:
                print(f"终止FFmpeg进程时出错: {e}")
        
        print(f"最终速度值: {recording.speed}")

# 运行测试
if __name__ == "__main__":
    print(f"开始测试速度监测功能，时间: {datetime.now()}")
    print(f"优先使用IO监测获取速度，备选使用FFmpeg输出")
    asyncio.run(run_test())
    print(f"测试完成，时间: {datetime.now()}") 