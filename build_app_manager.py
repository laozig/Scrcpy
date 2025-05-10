#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
构建应用管理器EXE的打包脚本
使用PyInstaller打包应用管理器为独立的EXE文件
"""

import os
import sys
import shutil
import subprocess

def build_exe():
    print("开始构建应用管理器EXE...")
    
    # 检查PyInstaller是否安装
    try:
        import PyInstaller
    except ImportError:
        print("未安装PyInstaller，正在安装...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # 准备打包命令
    icon_file = "1.ico"
    if not os.path.exists(icon_file):
        print(f"警告: 未找到图标文件 {icon_file}，将使用默认图标")
        icon_param = ""
    else:
        icon_param = f"--icon={icon_file}"
    
    # 构建命令
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        icon_param,
        "--name=AppManager",
        "--add-data=1.ico;.",
        "--hidden-import=argparse",  # 添加对argparse模块的支持
        "launch_app_manager.py"
    ]
    
    # 过滤掉空参数
    cmd = [x for x in cmd if x]
    
    # 运行打包命令
    print(f"执行命令: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    
    if result.returncode != 0:
        print("构建失败，退出码:", result.returncode)
        return False
    
    print("构建成功!")
    print(f"应用管理器EXE已生成: {os.path.abspath('dist/AppManager.exe')}")
    return True

if __name__ == "__main__":
    build_exe() 