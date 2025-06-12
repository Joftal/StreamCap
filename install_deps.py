#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import platform
import subprocess
import sys
import argparse

def main():
    """根据当前平台安装相应的依赖"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="安装StreamCap依赖")
    parser.add_argument("--web", action="store_true", help="安装Web环境依赖")
    args = parser.parse_args()
    
    print("检测当前平台...")
    system = platform.system().lower()
    
    # 确定要使用的依赖文件
    if args.web:
        req_file = "requirements-web.txt"
        print("安装Web环境依赖")
    else:
        if system == "windows":
            req_file = "requirements-win.txt"
            print("检测到 Windows 平台")
        elif system == "darwin":
            req_file = "requirements-mac.txt"
            print("检测到 macOS 平台")
        else:
            req_file = "requirements-linux.txt"
            print("检测到 Linux 平台")
    
    # 检查文件是否存在
    if not os.path.exists(req_file):
        print(f"错误: 找不到依赖文件 {req_file}")
        if os.path.exists("requirements.txt"):
            print("使用默认的 requirements.txt 文件")
            req_file = "requirements.txt"
        else:
            print("找不到任何依赖文件，退出安装")
            return 1
    
    print(f"正在安装依赖 ({req_file})...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file])
        print("依赖安装完成")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"安装依赖时出错: {e}")
        return e.returncode

if __name__ == "__main__":
    sys.exit(main()) 