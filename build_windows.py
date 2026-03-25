#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Windows平台打包脚本
使用PyInstaller将Python脚本打包为Windows可执行文件
"""

import os
import argparse
import subprocess
import sys
import zipfile

from utils import console_log


def _find_local_scrcpy_dir(base_dir):
    candidates = []
    for name in os.listdir(base_dir):
        full_path = os.path.join(base_dir, name)
        if os.path.isdir(full_path) and name.startswith("scrcpy-win64-v"):
            candidates.append(full_path)
    return sorted(candidates, reverse=True)[0] if candidates else None

def build_windows_executable(spec_file=None, one_file=False, debug=False):
    console_log("开始构建Windows可执行文件...")
    
    # 确定spec文件（尝试一组候选，避免固定名称）
    if not spec_file:
        for candidate in ["ScrcpyGUI.spec", "ScrcpyGUI_separate.spec", "ScrcpyGUI_onefile_separate.spec"]:
            if os.path.exists(candidate):
                spec_file = candidate
                console_log(f"未指定spec，使用找到的文件: {spec_file}")
                break
    # 如果用户指定或默认候选不存在，再提示
    if not spec_file or not os.path.exists(spec_file):
        console_log("错误: 找不到可用的spec文件（期望之一: ScrcpyGUI.spec / ScrcpyGUI_separate.spec / ScrcpyGUI_onefile_separate.spec）", "ERROR")
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
        scrcpy_dir = _find_local_scrcpy_dir(os.path.dirname(os.path.abspath(__file__)))
        if os.path.exists(scrcpy_dir):
            console_log(f"添加scrcpy目录: {scrcpy_dir}")
            cmd.append("--add-data")
            if sys.platform == "win32":
                cmd.append(f"{scrcpy_dir};{os.path.basename(scrcpy_dir)}")
            else:
                cmd.append(f"{scrcpy_dir}:{os.path.basename(scrcpy_dir)}")
        else:
            console_log("警告: 未找到本地 scrcpy 目录，打包产物将依赖外部环境", "WARN")
            
        cmd.append(spec_file)
    
    # 执行打包命令
    try:
        console_log(f"执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        
        if result.returncode != 0:
            console_log(f"构建失败，退出码: {result.returncode}", "ERROR")
            return False
        
        console_log("构建成功!")
        
        # 打印可执行文件路径
        if one_file:
            exe_path = os.path.abspath("dist/ScrcpyGUI.exe")
            if os.path.exists(exe_path):
                file_size = os.path.getsize(exe_path) / (1024 * 1024)
                console_log(f"可执行文件已生成: {exe_path} ({file_size:.2f} MB)")
            else:
                console_log(f"警告: 未找到生成的可执行文件: {exe_path}", "WARN")
        else:
            dist_dir = os.path.abspath("dist/ScrcpyGUI")
            if os.path.exists(dist_dir):
                console_log(f"程序目录已生成: {dist_dir}")
            else:
                console_log(f"警告: 未找到生成的程序目录: {dist_dir}", "WARN")
        
        return True
    except Exception as e:
        console_log(f"构建过程中出现错误: {e}", "ERROR")
        return False

def create_zip_archive(archive_name=None):
    """创建分发用的ZIP压缩包"""
    dist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dist')
    
    if not os.path.exists(dist_dir):
        console_log("错误: 没有找到打包后的dist目录", "ERROR")
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
            
            console_log(f"成功创建压缩包: {zip_path}")
            return True
        else:
            console_log(f"错误: 找不到可执行文件目录: {executable_dir}", "ERROR")
            return False
    except Exception as e:
        console_log(f"创建压缩包时出错: {e}", "ERROR")
        return False

def main():
    parser = argparse.ArgumentParser(description="Windows平台打包脚本")
    parser.add_argument("--spec", help="指定spec文件路径（不填则自动选择现有spec）", default=None)
    parser.add_argument("--onefile", action="store_true", help="打包为单个文件")
    parser.add_argument("--debug", action="store_true", help="启用调试模式")
    parser.add_argument("--zip", action="store_true", help="创建ZIP归档")
    parser.add_argument("--zip-name", help="ZIP归档名称")
    
    args = parser.parse_args()
    
    # 构建可执行文件
    if build_windows_executable(args.spec, args.onefile, args.debug):
        console_log("构建完成!")
        
        # 如果需要创建ZIP归档
        if args.zip:
            if create_zip_archive(args.zip_name):
                console_log("ZIP归档创建成功!")
            else:
                console_log("ZIP归档创建失败!", "ERROR")
    else:
        console_log("构建失败!", "ERROR")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
