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
    
    # 应用图标路径 (macOS使用.icns格式或.ico格式)
    icon_path = "1.ico"  # 使用1.ico作为图标
    
    # 检查必要的文件是否存在
    add_data_args = []
    
    if os.path.exists("settings_example.json"):
        add_data_args.append("--add-data=settings_example.json:.")
    else:
        print("警告: settings_example.json 文件不存在，打包时将不包含此文件")
    
    if os.path.exists("scrcpy_config.json"):
        add_data_args.append("--add-data=scrcpy_config.json:.")
    else:
        print("警告: scrcpy_config.json 文件不存在，打包时将不包含此文件")
    
    # 检查图标文件是否存在
    if not os.path.exists(icon_path):
        print(f"警告: 图标文件 {icon_path} 不存在，将使用默认图标")
        icon_arg = []
    else:
        icon_arg = [f"--icon={icon_path}"]
    
    # PyInstaller打包命令
    pyinstaller_cmd = [
        "pyinstaller",
        "--name=ScrcpyGUI",
        "--onefile",  # 打包成单个可执行文件
        "--noconsole",  # 不显示控制台窗口
        "--clean",
        "--noconfirm",
    ]
    
    # 添加图标参数
    pyinstaller_cmd.extend(icon_arg)
    
    # 添加数据文件参数
    pyinstaller_cmd.extend(add_data_args)
    
    # 添加主脚本
    pyinstaller_cmd.append("main.py")
    
    # 执行打包命令
    print("正在打包应用程序...")
    try:
        subprocess.check_call(pyinstaller_cmd)
    except subprocess.CalledProcessError as e:
        print(f"打包失败: {e}")
        print("请检查是否安装了PyInstaller最新版本，可以使用以下命令更新:")
        print("  pip install --upgrade pyinstaller")
        return
    
    print("\n打包完成！可执行文件位于 dist/ScrcpyGUI")
    print("请确保在运行程序的计算机上已安装ADB和scrcpy，且已添加到系统PATH中。")
    print("在macOS上可以使用Homebrew安装ADB和scrcpy:")
    print("  brew install android-platform-tools")
    print("  brew install scrcpy")

if __name__ == "__main__":
    main() 