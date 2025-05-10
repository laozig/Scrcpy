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
    
    # 应用图标路径
    # icon_path = "screenshot.png"  # 如果有图标的话，否则可以省略--icon参数
    
    # PyInstaller打包命令
    pyinstaller_cmd = [
        "pyinstaller",
        "--name=ScrcpyGUI",
        "--onefile",  # 打包成单个可执行文件
        "--windowed",  # 不显示控制台窗口
        # "--icon=" + icon_path,  # 如果有图标文件则取消注释
        "--clean",
        "--noconfirm",
        "--add-data=settings_example.json:.",  # Linux使用冒号作为分隔符
        "--add-data=scrcpy_config.json:.",  # 如果文件存在
        "main.py"
    ]
    
    # 执行打包命令
    print("正在打包应用程序...")
    subprocess.check_call(pyinstaller_cmd)
    
    # 创建桌面文件
    desktop_file = """[Desktop Entry]
Name=ScrcpyGUI
Comment=Android设备屏幕镜像和控制工具
Exec=env QT_QPA_PLATFORM=xcb {}/dist/ScrcpyGUI
Icon={}/screenshot.png
Terminal=false
Type=Application
Categories=Utility;
""".format(os.getcwd(), os.getcwd())

    desktop_path = os.path.expanduser("~/.local/share/applications/scrcpy-gui.desktop")
    os.makedirs(os.path.dirname(desktop_path), exist_ok=True)
    
    try:
        with open(desktop_path, "w") as f:
            f.write(desktop_file)
        os.chmod(desktop_path, 0o755)
        print(f"已创建桌面快捷方式: {desktop_path}")
    except Exception as e:
        print(f"创建桌面快捷方式失败: {e}")
    
    print("\n打包完成！可执行文件位于 dist/ScrcpyGUI")
    print("请确保在运行程序的计算机上已安装ADB和scrcpy，且已添加到系统PATH中。")
    print("在Ubuntu/Debian上可以使用以下命令安装依赖:")
    print("  sudo apt update")
    print("  sudo apt install android-tools-adb scrcpy")
    print("在Fedora上可以使用以下命令安装依赖:")
    print("  sudo dnf install android-tools scrcpy")
    print("在Arch Linux上可以使用以下命令安装依赖:")
    print("  sudo pacman -S android-tools scrcpy")

if __name__ == "__main__":
    main() 