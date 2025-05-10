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
    icon_path = os.path.join(os.getcwd(), "1.ico")
    print(f"使用图标路径: {icon_path}")
    
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
    
    # PyInstaller打包命令
    pyinstaller_cmd = [
        "pyinstaller",
        "--name=ScrcpyGUI",
        "--onefile",  # 打包成单个可执行文件
        "--noconsole",  # 不显示控制台窗口
        "--clean",
        "--noconfirm",
    ]
    
    # 添加图标参数（如果图标文件存在）
    if os.path.exists(icon_path):
        pyinstaller_cmd.append(f"--icon={icon_path}")
    else:
        print(f"警告: 图标文件 {icon_path} 不存在，将使用默认图标")
    
    # 添加数据文件参数
    pyinstaller_cmd.extend(add_data_args)
    
    # 添加主脚本
    pyinstaller_cmd.append("main.py")
    
    # 执行打包命令
    print("正在打包应用程序...")
    print(f"执行命令: {' '.join(pyinstaller_cmd)}")
    try:
        subprocess.check_call(pyinstaller_cmd)
    except subprocess.CalledProcessError as e:
        print(f"打包失败: {e}")
        print("请检查是否安装了PyInstaller最新版本，可以使用以下命令更新:")
        print("  pip install --upgrade pyinstaller")
        return
    
    # 创建桌面文件
    desktop_file = """[Desktop Entry]
Name=ScrcpyGUI
Comment=Android设备屏幕镜像和控制工具
Exec=env QT_QPA_PLATFORM=xcb {}/dist/ScrcpyGUI
Icon={}/1.ico
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