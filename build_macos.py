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
    
    # 应用图标路径 (macOS使用.icns格式)
    icon_path = "1.ico"  # 原始图标
    icns_path = "icon.icns"  # macOS图标格式
    
    # 确保图标存在
    if not os.path.exists(icon_path):
        try:
            print("尝试生成图标...")
            import create_icon
            create_icon.create_simple_icon(icon_path)
        except Exception as e:
            print(f"无法生成图标: {e}")
    
    # 转换图标为ICNS格式(适用于macOS)
    if os.path.exists(icon_path):
        try:
            from PIL import Image
            print("正在转换图标为macOS ICNS格式...")
            
            # 使用PIL来转换图标为PNG
            img = Image.open(icon_path)
            png_path = "icon.png"
            img.save(png_path)
            
            # 使用iconutil将图标集转换为icns (需要macOS系统)
            iconset_dir = "icon.iconset"
            if not os.path.exists(iconset_dir):
                os.makedirs(iconset_dir)
            
            # 创建不同尺寸的图标
            sizes = [16, 32, 64, 128, 256, 512, 1024]
            for size in sizes:
                img_resized = img.resize((size, size), Image.LANCZOS)
                img_resized.save(f"{iconset_dir}/icon_{size}x{size}.png")
                # 创建@2x版本
                if size * 2 <= 1024:  # 确保不超过1024x1024
                    img_resized = img.resize((size*2, size*2), Image.LANCZOS)
                    img_resized.save(f"{iconset_dir}/icon_{size}x{size}@2x.png")
            
            # 使用iconutil转换为icns
            try:
                subprocess.run(["iconutil", "-c", "icns", iconset_dir], check=True)
                print(f"成功创建ICNS图标: {icns_path}")
                # 使用转换后的icns图标
                icon_path = icns_path
            except Exception as e:
                print(f"转换ICNS失败: {e}")
                print("将使用原始图标，但在macOS上可能不完全支持")
        except Exception as e:
            print(f"图标准备失败: {e}")
    
    # 使用spec文件进行打包，这样更可靠
    spec_file = "ScrcpyGUI_macos.spec"
    
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
        # 检查图标文件是否存在
        if not os.path.exists(icon_path):
            print(f"警告: 图标文件 {icon_path} 不存在，将使用默认图标")
            icon_arg = []
        else:
            icon_arg = [f"--icon={icon_path}"]
            
        # 直接使用命令行参数
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
        add_data_args = []
        
        if os.path.exists("settings_example.json"):
            add_data_args.append("--add-data=settings_example.json:.")
        else:
            print("警告: settings_example.json 文件不存在，打包时将不包含此文件")
        
        if os.path.exists("scrcpy_config.json"):
            add_data_args.append("--add-data=scrcpy_config.json:.")
        else:
            print("警告: scrcpy_config.json 文件不存在，打包时将不包含此文件")
            
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
    
    # 检查打包结果
    dist_dir = os.path.abspath("dist")
    exe_path = os.path.join(dist_dir, "ScrcpyGUI")
    
    if os.path.exists(exe_path):
        print(f"\n打包完成！可执行文件位于 {exe_path}")
        print(f"文件大小: {os.path.getsize(exe_path)/1024/1024:.2f} MB")
        
        # 创建应用程序包(app bundle)
        try:
            app_dir = os.path.join(dist_dir, "ScrcpyGUI.app")
            if not os.path.exists(app_dir):
                os.makedirs(os.path.join(app_dir, "Contents", "MacOS"), exist_ok=True)
                os.makedirs(os.path.join(app_dir, "Contents", "Resources"), exist_ok=True)
                
                # 复制可执行文件
                shutil.copy2(exe_path, os.path.join(app_dir, "Contents", "MacOS", "ScrcpyGUI"))
                
                # 复制图标
                if os.path.exists(icns_path):
                    shutil.copy2(icns_path, os.path.join(app_dir, "Contents", "Resources", "icon.icns"))
                
                # 创建Info.plist
                info_plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDisplayName</key>
    <string>ScrcpyGUI</string>
    <key>CFBundleExecutable</key>
    <string>ScrcpyGUI</string>
    <key>CFBundleIconFile</key>
    <string>icon.icns</string>
    <key>CFBundleIdentifier</key>
    <string>com.scrcpy.gui</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>ScrcpyGUI</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
"""
                # 写入Info.plist
                with open(os.path.join(app_dir, "Contents", "Info.plist"), "w") as f:
                    f.write(info_plist)
                
                print(f"已创建macOS应用程序包: {app_dir}")
            else:
                print(f"macOS应用程序包已存在: {app_dir}")
        except Exception as e:
            print(f"创建macOS应用程序包失败: {e}")
    else:
        print(f"警告: 可执行文件 {exe_path} 未创建!")
    
    # 清理临时文件
    for temp_file in ["icon.iconset", "icon.png"]:
        if os.path.exists(temp_file):
            try:
                if os.path.isdir(temp_file):
                    shutil.rmtree(temp_file)
                else:
                    os.remove(temp_file)
            except Exception:
                pass
    
    print("\n请确保在运行程序的计算机上已安装ADB和scrcpy，且已添加到系统PATH中。")
    print("在macOS上可以使用Homebrew安装ADB和scrcpy:")
    print("  brew install android-platform-tools")
    print("  brew install scrcpy")

if __name__ == "__main__":
    main() 