#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import sys
import shutil
import tempfile

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
    
    # 应用图标路径 - 使用相对路径
    icon_path = "1.ico"
    
    # 确保图标存在
    if not os.path.exists(icon_path) or os.path.getsize(icon_path) < 100:
        print(f"没有找到有效的图标文件 {icon_path}")
        try:
            print("尝试生成图标...")
            import create_icon
            create_icon.create_simple_icon(icon_path)
        except:
            print("无法生成图标，将使用默认图标")
    
    # 确认图标状态
    if os.path.exists(icon_path) and os.path.getsize(icon_path) > 0:
        print(f"使用图标：{icon_path} (大小: {os.path.getsize(icon_path)} 字节)")
    else:
        print("警告: 找不到有效的图标文件，将使用默认图标")
        icon_path = None
    
    # 检查必要的文件是否存在
    add_data_args = []
    
    if os.path.exists("settings_example.json"):
        add_data_args.append("--add-data=settings_example.json;.")
    else:
        print("警告: settings_example.json 文件不存在，打包时将不包含此文件")
    
    if os.path.exists("scrcpy_config.json"):
        add_data_args.append("--add-data=scrcpy_config.json;.")
    else:
        print("警告: scrcpy_config.json 文件不存在，打包时将不包含此文件")
    
    # 添加图标文件作为数据文件
    if icon_path and os.path.exists(icon_path):
        add_data_args.append(f"--add-data={icon_path};.")
        print(f"将图标文件 {icon_path} 添加到数据文件")
    
    # 使用spec文件进行打包，这样更可靠
    if os.path.exists("ScrcpyGUI.spec"):
        print("找到.spec文件，将使用它进行打包")
        # 使用.spec文件进行打包
        pyinstaller_cmd = [
            "pyinstaller",
            "--clean",
            "--noconfirm",
            "ScrcpyGUI.spec"
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
        
        # 添加图标参数
        if icon_path:
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
    
    # 如果打包成功，检查可执行文件
    dist_dir = os.path.abspath("dist")
    exe_path = os.path.join(dist_dir, "ScrcpyGUI.exe")
    
    if os.path.exists(exe_path):
        print(f"\n打包完成！可执行文件位于 {exe_path} (大小: {os.path.getsize(exe_path)/1024/1024:.2f} MB)")
        
        # 复制图标文件到dist目录，确保文件图标能够显示
        if icon_path and os.path.exists(icon_path):
            try:
                # 复制图标文件
                dist_icon_path = os.path.join(dist_dir, icon_path)
                shutil.copy2(icon_path, dist_icon_path)
                print(f"已复制图标文件 {icon_path} 到 {dist_dir} 目录")
                
                # 创建快捷方式 - 确保图标能在文件浏览器中显示
                try:
                    # 创建VBS脚本来创建快捷方式
                    vbs_content = f"""
Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{dist_dir}\\ScrcpyGUI.lnk"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{exe_path}"
oLink.IconLocation = "{dist_icon_path}"
oLink.Save
                    """
                    
                    vbs_path = os.path.join(dist_dir, "create_shortcut.vbs")
                    with open(vbs_path, "w") as vbs_file:
                        vbs_file.write(vbs_content)
                    
                    # 执行VBS脚本创建快捷方式
                    try:
                        print(f"执行脚本: {vbs_path}")
                        subprocess.call(["cscript", "//nologo", vbs_path])
                        print("已创建带图标的快捷方式")
                    except Exception as e:
                        print(f"执行VBS脚本失败: {e}")
                    
                    # 删除VBS脚本
                    if os.path.exists(vbs_path):
                        os.remove(vbs_path)
                        print("已清理VBS脚本")
                    
                except Exception as e:
                    print(f"创建快捷方式失败: {e}")
            except Exception as e:
                print(f"复制图标文件失败: {e}")
    else:
        print("\n警告: 可执行文件未创建!")
    
    print("\n请确保在运行程序的计算机上已安装ADB和scrcpy，且已添加到系统PATH中。")

if __name__ == "__main__":
    main()