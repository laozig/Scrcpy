#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import sys
import shutil

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
    icon_path = "1.ico"
    if not os.path.exists(icon_path):
        try:
            print("尝试生成图标...")
            import create_icon
            create_icon.create_simple_icon(icon_path)
        except Exception as e:
            print(f"无法生成图标: {e}")
    
    # 确认图标状态
    if os.path.exists(icon_path) and os.path.getsize(icon_path) > 0:
        print(f"使用图标：{icon_path} (大小: {os.path.getsize(icon_path)} 字节)")
        # 在Linux上，我们可能需要将.ico转换为.png以便更好地支持
        try:
            from PIL import Image
            img = Image.open(icon_path)
            png_icon_path = "icon.png"
            img.save(png_icon_path)
            print(f"已将ICO图标转换为PNG格式: {png_icon_path}")
            icon_path = png_icon_path
        except Exception as e:
            print(f"转换图标格式失败: {e}")
    else:
        print("警告: 找不到有效的图标文件，将使用默认图标")
        icon_path = None
    
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
    
    # 使用spec文件进行打包，这样更可靠
    spec_file = "ScrcpyGUI_linux.spec"
    
    if os.path.exists(spec_file):
        print(f"找到{spec_file}文件，将使用它进行打包")
        # 使用.spec文件进行打包
        pyinstaller_cmd = [
            "pyinstaller",
            "--clean",
            "--noconfirm",
            spec_file
        ]
    else:
        # 直接使用命令行参数
        pyinstaller_cmd = [
            "pyinstaller",
            "--name=ScrcpyGUI",
            "--onefile",  # 打包成单个可执行文件
            "--noconsole",  # 不显示控制台窗口
            "--clean",
            "--noconfirm",
        ]
        
        # 添加图标参数（如果图标文件存在）
        if icon_path and os.path.exists(icon_path):
            pyinstaller_cmd.append(f"--icon={icon_path}")
        
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
    
    # 检查可执行文件是否创建成功
    dist_dir = os.path.abspath("dist")
    exe_path = os.path.join(dist_dir, "ScrcpyGUI")
    if not os.path.exists(exe_path):
        print(f"警告: 可执行文件 {exe_path} 未创建!")
        return
    
    print(f"\n打包完成！可执行文件位于 {exe_path}")
    print(f"文件大小: {os.path.getsize(exe_path)/1024/1024:.2f} MB")
    
    # 创建桌面文件
    desktop_file = """[Desktop Entry]
Name=ScrcpyGUI
Comment=Android设备屏幕镜像和控制工具
Exec={exe_path}
Icon={icon_path}
Terminal=false
Type=Application
Categories=Utility;
""".format(exe_path=os.path.abspath(exe_path), 
           icon_path=os.path.abspath(icon_path) if icon_path and os.path.exists(icon_path) else "")

    desktop_path = os.path.expanduser("~/.local/share/applications/scrcpy-gui.desktop")
    os.makedirs(os.path.dirname(desktop_path), exist_ok=True)
    
    try:
        with open(desktop_path, "w") as f:
            f.write(desktop_file)
        os.chmod(desktop_path, 0o755)
        print(f"已创建桌面快捷方式: {desktop_path}")
    except Exception as e:
        print(f"创建桌面快捷方式失败: {e}")
    
    print("\n请确保在运行程序的计算机上已安装ADB和scrcpy，且已添加到系统PATH中。")
    print("在Ubuntu/Debian上可以使用以下命令安装依赖:")
    print("  sudo apt update")
    print("  sudo apt install android-tools-adb scrcpy")
    print("在Fedora上可以使用以下命令安装依赖:")
    print("  sudo dnf install android-tools scrcpy")
    print("在Arch Linux上可以使用以下命令安装依赖:")
    print("  sudo pacman -S android-tools scrcpy")

if __name__ == "__main__":
    main() 