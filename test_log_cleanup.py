import os
import time
import datetime
import glob
import shutil
from pathlib import Path
import sys

# 获取当前脚本路径
script_path = os.path.split(os.path.realpath(sys.argv[0]))[0]
log_dir = os.path.join(script_path, "logs", "test_cleanup")

def create_test_logs():
    """创建测试日志文件，并设置不同的修改时间"""
    # 确保测试目录存在
    os.makedirs(log_dir, exist_ok=True)
    
    # 清理之前的测试文件
    for old_file in glob.glob(os.path.join(log_dir, "*.*")):
        os.remove(old_file)
    
    # 获取当前时间
    now = time.time()
    
    # 创建不同天数的日志文件
    days_list = [1, 3, 5, 7, 10, 15, 30]
    
    # 创建三种类型的日志文件：streamget、play_url、memory_clean
    log_types = ["streamget", "play_url", "memory_clean"]
    
    print("\n创建测试日志文件...")
    total_files = 0
    
    # 为每种类型创建不同天数的日志文件
    for log_type in log_types:
        print(f"\n创建 {log_type} 类型的日志文件:")
        for days in days_list:
            # 计算时间戳
            file_time = now - (days * 24 * 60 * 60)
            # 创建文件
            filename = os.path.join(log_dir, f"{log_type}.{days}_days_ago.log")
            
            # 写入测试内容
            with open(filename, 'w') as f:
                f.write(f"这是一个测试日志文件，模拟 {days} 天前的日志。\n")
                f.write(f"文件类型: {log_type}\n")
                f.write(f"创建时间: {datetime.datetime.fromtimestamp(file_time).strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            # 修改文件的访问和修改时间
            os.utime(filename, (file_time, file_time))
            
            # 格式化显示时间
            time_str = datetime.datetime.fromtimestamp(file_time).strftime('%Y-%m-%d %H:%M:%S')
            print(f"  - {os.path.basename(filename)} ({time_str})")
            total_files += 1
    
    # 创建filtered_urls_{timestamp}.txt格式的文件
    print("\n创建 filtered_urls 类型的日志文件:")
    for days in days_list:
        # 计算时间戳
        file_time = now - (days * 24 * 60 * 60)
        
        # 生成时间戳字符串，格式类似于 20240616_150635
        timestamp = datetime.datetime.fromtimestamp(file_time).strftime('%Y%m%d_%H%M%S')
        
        # 创建文件
        filename = os.path.join(log_dir, f"filtered_urls_{timestamp}.txt")
        
        # 写入测试内容
        with open(filename, 'w') as f:
            f.write(f"这是一个测试过滤URL文件，模拟 {days} 天前的文件。\n")
            f.write(f"创建时间: {datetime.datetime.fromtimestamp(file_time).strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("URL,原因\n")
            f.write("http://example.com/stream1,URL完全相同\n")
            f.write("http://example.com/stream2,同平台同名主播\n")
        
        # 修改文件的访问和修改时间
        os.utime(filename, (file_time, file_time))
        
        # 格式化显示时间
        time_str = datetime.datetime.fromtimestamp(file_time).strftime('%Y-%m-%d %H:%M:%S')
        print(f"  - {os.path.basename(filename)} ({time_str})")
        total_files += 1
    
    print(f"\n创建完成，共创建 {total_files} 个测试日志文件")
    
    # 显示文件列表
    print("\n当前日志目录文件:")
    for file in sorted(glob.glob(os.path.join(log_dir, "*.*"))):
        mtime = os.path.getmtime(file)
        time_str = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        print(f"  - {os.path.basename(file)} ({time_str})")

def test_log_cleanup():
    """测试日志清理功能"""
    # 导入日志清理函数
    sys.path.insert(0, script_path)
    from app.utils.logger import cleanup_old_logs
    
    # 清理7天前的日志
    retention_days = 7
    print(f"\n执行日志清理，保留 {retention_days} 天内的日志...")
    cleanup_old_logs(days=retention_days, log_dir=log_dir)
    
    # 显示清理后剩余文件
    print("\n清理后剩余文件:")
    remaining_files = sorted(glob.glob(os.path.join(log_dir, "*.*")))
    
    # 按文件类型分组
    files_by_type = {}
    for file in remaining_files:
        base_name = os.path.basename(file)
        if base_name.startswith("filtered_urls_"):
            file_type = "filtered_urls"
        else:
            file_type = base_name.split('.')[0]
        
        if file_type not in files_by_type:
            files_by_type[file_type] = []
        files_by_type[file_type].append(file)
    
    # 显示每种类型的文件
    total_remaining = 0
    for file_type, files in files_by_type.items():
        print(f"\n类型 [{file_type}] 的文件:")
        for file in files:
            mtime = os.path.getmtime(file)
            time_str = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            days_ago = (time.time() - mtime) / (24 * 60 * 60)
            print(f"  - {os.path.basename(file)} ({time_str}, {days_ago:.1f} 天前)")
            total_remaining += 1
    
    print(f"\n清理完成，剩余 {total_remaining} 个文件")
    print("检查结果:")
    
    # 预期每种日志类型应至少保留一个最新的文件，即使它超过了保留期限
    expected_min_files = len(files_by_type)
    print(f"至少应保留 {expected_min_files} 个文件 (每种类型保留最新的一个)")
    
    # 检查是否有7天内的文件被误删
    recent_files_count = 0
    deleted_recent_files = []
    for file in glob.glob(os.path.join(log_dir, "*.*")):
        mtime = os.path.getmtime(file)
        days_ago = (time.time() - mtime) / (24 * 60 * 60)
        if days_ago < retention_days:
            recent_files_count += 1
    
    # 在创建的数据中，每种类型应有相同数量的最近文件
    expected_recent_files = len(files_by_type) * len([d for d in [1, 3, 5] if d < retention_days])
    if recent_files_count >= expected_recent_files:
        print(f"✅ 所有 {retention_days} 天内的文件都被正确保留")
    else:
        print(f"❌ 有 {retention_days} 天内的文件被错误删除，应保留 {expected_recent_files} 个，实际保留 {recent_files_count} 个")

if __name__ == "__main__":
    try:
        # 创建测试日志文件
        create_test_logs()
        
        # 运行测试
        test_log_cleanup()
    finally:
        # 删除测试目录（可选）
        # shutil.rmtree(log_dir, ignore_errors=True)
        pass 