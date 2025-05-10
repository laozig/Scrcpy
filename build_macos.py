#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import sys

def main():
    # 确保已安装PyInstaller
    try:
        import PyInstaller
    except ImportError:
        print("正在安装PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        
    # 确保已安装依赖
    print("正在安装项目依赖...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    
    # 应用图标路径 (macOS使用.icns格式)
    # icon_path = "screenshot.icns"  # 如果有图标的话，否则可以省略--icon参数
    
    # PyInstaller打包命令
    pyinstaller_cmd = [
        "pyinstaller",
        "--name=ScrcpyGUI",
        "--onefile",  # 打包成单个可执行文件
        "--windowed",  # 不显示控制台窗口
        # "--icon=" + icon_path,  # 如果有图标文件则取消注释
        "--clean",
        "--noconfirm",
        "--add-data=settings_example.json:.",  # macOS使用冒号作为分隔符
        "--add-data=scrcpy_config.json:.",  # 如果文件存在
        "main.py"
    ]
    
    # 执行打包命令
    print("正在打包应用程序...")
    subprocess.check_call(pyinstaller_cmd)
    
    print("\n打包完成！可执行文件位于 dist/ScrcpyGUI")
    print("请确保在运行程序的计算机上已安装ADB和scrcpy，且已添加到系统PATH中。")
    print("在macOS上可以使用Homebrew安装ADB和scrcpy:")
    print("  brew install android-platform-tools")
    print("  brew install scrcpy")

if __name__ == "__main__":
    main() 