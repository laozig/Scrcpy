#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Windows平台打包脚本
使用PyInstaller将Python脚本打包为Windows可执行文件
"""

import os
import shutil
import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

def build_windows_executable(spec_file=None, one_file=False, debug=False):
    print(f"开始构建Windows可执行文件...")
    
    # 确定spec文件
    if not spec_file:
        spec_file = "ScrcpyGUI.spec"
    
    if not os.path.exists(spec_file):
        print(f"错误: 指定的spec文件 '{spec_file}' 不存在")
        return False
    
    # 构建命令
    cmd = ["pyinstaller", "--clean"]
    
    # 检查是否使用spec文件
    if spec_file.endswith('.spec'):
        # 使用spec文件时，不需要其他选项
        cmd.append(spec_file)
    else:
        # 如果不是spec文件，则添加其他选项
        if one_file:
            cmd.append("--onefile")
        else:
            cmd.append("--onedir")
            
        if debug:
            cmd.append("--debug=all")
            
        # 添加scrcpy相关文件
        scrcpy_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scrcpy-win64-v3.2")
        if os.path.exists(scrcpy_dir):
            print(f"添加scrcpy目录: {scrcpy_dir}")
            cmd.append("--add-data")
            if sys.platform == "win32":
                cmd.append(f"{scrcpy_dir};scrcpy-win64-v3.2")
            else:
                cmd.append(f"{scrcpy_dir}:scrcpy-win64-v3.2")
        else:
            print(f"警告: 未找到scrcpy目录: {scrcpy_dir}")
            
        cmd.append(spec_file)
    
    # 执行打包命令
    try:
        print(f"执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        
        if result.returncode != 0:
            print("构建失败，退出码:", result.returncode)
            return False
        
        print("构建成功!")
        
        # 打印可执行文件路径
        if one_file:
            exe_path = os.path.abspath("dist/ScrcpyGUI.exe")
            if os.path.exists(exe_path):
                file_size = os.path.getsize(exe_path) / (1024 * 1024)
                print(f"可执行文件已生成: {exe_path} ({file_size:.2f} MB)")
            else:
                print(f"警告: 未找到生成的可执行文件: {exe_path}")
        else:
            dist_dir = os.path.abspath("dist/ScrcpyGUI")
            if os.path.exists(dist_dir):
                print(f"程序目录已生成: {dist_dir}")
            else:
                print(f"警告: 未找到生成的程序目录: {dist_dir}")
        
        return True
    except Exception as e:
        print(f"构建过程中出现错误: {e}")
        return False

def create_zip_archive(archive_name=None):
    """创建分发用的ZIP压缩包"""
    dist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dist')
    
    if not os.path.exists(dist_dir):
        print(f"错误: 没有找到打包后的dist目录")
        return False
    
    if not archive_name:
        archive_name = "ScrcpyGUI"
    
    # 如果没有扩展名，添加.zip
    if not archive_name.endswith('.zip'):
        archive_name += '.zip'
    
    # 确定压缩包路径
    zip_path = os.path.join(dist_dir, archive_name)
    
    try:
        executable_dir = os.path.join(dist_dir, 'ScrcpyGUI')
        if os.path.exists(executable_dir):
            # 创建压缩包
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(executable_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # 计算相对路径，作为压缩包内的路径
                        rel_path = os.path.relpath(file_path, executable_dir)
                        zipf.write(file_path, rel_path)
            
            print(f"成功创建压缩包: {zip_path}")
            return True
        else:
            print(f"错误: 找不到可执行文件目录: {executable_dir}")
            return False
    except Exception as e:
        print(f"创建压缩包时出错: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Windows平台打包脚本")
    parser.add_argument("--spec", help="指定spec文件路径", default="ScrcpyGUI.spec")
    parser.add_argument("--onefile", action="store_true", help="打包为单个文件")
    parser.add_argument("--debug", action="store_true", help="启用调试模式")
    parser.add_argument("--zip", action="store_true", help="创建ZIP归档")
    parser.add_argument("--zip-name", help="ZIP归档名称")
    
    args = parser.parse_args()
    
    # 构建可执行文件
    if build_windows_executable(args.spec, args.onefile, args.debug):
        print("构建完成!")
        
        # 如果需要创建ZIP归档
        if args.zip:
            if create_zip_archive(args.zip_name):
                print("ZIP归档创建成功!")
            else:
                print("ZIP归档创建失败!")
    else:
        print("构建失败!")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())