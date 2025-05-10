#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
应用管理器启动脚本
此脚本用于直接启动Scrcpy GUI的应用管理器功能
"""

import sys
import os
import subprocess

def main():
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 构建主程序路径
    main_script = os.path.join(script_dir, "main.py")
    
    # 检查文件是否存在
    if not os.path.exists(main_script):
        print(f"错误: 找不到主程序文件 {main_script}")
        return 1
    
    # 启动应用管理器
    print("正在启动应用管理器...")
    
    try:
        # 使用子进程启动应用管理器
        subprocess.run([sys.executable, main_script, "--app-manager"])
        return 0
    except Exception as e:
        print(f"启动应用管理器失败: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 