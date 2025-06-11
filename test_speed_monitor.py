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

# 方法2：从文件大小变化监测速度
async def monitor_file_size_change(file_path, interval=1.0):
    """通过监测文件大小变化来计算写入速度"""
    try:
        if not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")
            return "0 KB/s"
        
        initial_size = os.path.getsize(file_path)
        await asyncio.sleep(interval)
        
        if not os.path.exists(file_path):  # 再次检查，文件可能被删除
            return "0 KB/s"
            
        new_size = os.path.getsize(file_path)
        size_diff = new_size - initial_size
        
        # 计算每秒KB
        kb_per_sec = size_diff / interval / 1024
        
        # 根据大小选择合适的单位
        if kb_per_sec >= 1024:
            return f"{kb_per_sec/1024:.2f} MB/s"
        else:
            return f"{kb_per_sec:.2f} KB/s"
    except Exception as e:
        print(f"监测文件大小变化出错: {e}")
        return "0 KB/s"

# 方法3：使用psutil监测进程IO
async def monitor_process_io(pid, interval=1.0):
    """使用psutil监测进程的IO读写速度"""
    try:
        if not psutil.pid_exists(pid):
            print(f"进程不存在: {pid}")
            return "0 KB/s"
            
        process = psutil.Process(pid)
        initial_io = process.io_counters()
        await asyncio.sleep(interval)
        
        if not psutil.pid_exists(pid):  # 再次检查，进程可能已终止
            return "0 KB/s"
            
        current_io = process.io_counters()
        
        # 计算写入速度 (bytes per second)
        write_bytes = current_io.write_bytes - initial_io.write_bytes
        bytes_per_sec = write_bytes / interval
        
        # 转换为适当的单位
        if bytes_per_sec >= 1024 * 1024:
            return f"{bytes_per_sec / (1024 * 1024):.2f} MB/s"
        elif bytes_per_sec >= 1024:
            return f"{bytes_per_sec / 1024:.2f} KB/s"
        else:
            return f"{bytes_per_sec:.2f} B/s"
    except Exception as e:
        print(f"监测进程IO出错: {e}")
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
            # 方法1: 从ffmpeg输出获取速度
            speed_from_output = await extract_speed_from_ffmpeg_output(ffmpeg_process)
            if speed_from_output:
                print(f"从FFmpeg输出获取速度: {speed_from_output}")
                recording.speed = speed_from_output
            
            # 方法2: 从文件大小变化获取速度
            if os.path.exists(output_file):
                file_speed = await monitor_file_size_change(output_file)
                print(f"从文件大小变化获取速度: {file_speed}")
                # 如果没有从输出获取到速度，就使用文件监测的速度
                if not speed_from_output:
                    recording.speed = file_speed
            
            # 方法3: 使用psutil监测进程IO
            if psutil.pid_exists(ffmpeg_process.pid):
                process_speed = await monitor_process_io(ffmpeg_process.pid)
                print(f"从进程IO获取速度: {process_speed}")
                # 如果其他方法都没获取到速度，就使用进程IO监测的速度
                if not speed_from_output and not os.path.exists(output_file):
                    recording.speed = process_speed
            
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
    asyncio.run(run_test())
    print(f"测试完成，时间: {datetime.now()}") 