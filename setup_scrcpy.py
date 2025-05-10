#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Scrcpy环境自动安装脚本
此脚本用于下载scrcpy-win64-v3.2并配置到项目目录中
"""

import os
import sys
import shutil
import zipfile
import subprocess
import tempfile
import urllib.request
from pathlib import Path

# scrcpy下载链接
SCRCPY_URL = "https://github.com/Genymobile/scrcpy/releases/download/v3.2/scrcpy-win64-v3.2.zip"
# 目标目录名
TARGET_DIR = "scrcpy-win64-v3.2"

def download_file(url, target_path):
    """从URL下载文件到指定路径"""
    print(f"正在下载 {url} 到 {target_path}...")
    
    # 使用临时文件下载，避免下载中断导致文件损坏
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_path = temp_file.name
    
    try:
        # 创建进度条显示
        def report_progress(blocknum, blocksize, totalsize):
            read = blocknum * blocksize
            if totalsize > 0:
                percent = min(100, read * 100 / totalsize)
                sys.stdout.write(f"\r下载进度: {percent:.2f}% ({read/(1024*1024):.2f} MB / {totalsize/(1024*1024):.2f} MB)")
                sys.stdout.flush()
            else:
                sys.stdout.write(f"\r下载进度: {read/(1024*1024):.2f} MB")
                sys.stdout.flush()
        
        # 执行下载
        urllib.request.urlretrieve(url, temp_path, reporthook=report_progress)
        print()  # 换行
        
        # 下载完成后移动到最终位置
        shutil.move(temp_path, target_path)
        return True
    except Exception as e:
        print(f"下载失败：{e}")
        # 清理临时文件
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        return False

def extract_zip(zip_path, extract_dir):
    """解压ZIP文件到指定目录"""
    print(f"正在解压 {zip_path} 到 {extract_dir}...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # 获取ZIP文件中的所有内容
            total_files = len(zip_ref.namelist())
            
            # 解压所有文件
            for i, file in enumerate(zip_ref.namelist()):
                if i % 10 == 0 or i+1 == total_files:  # 每10个文件更新一次进度
                    sys.stdout.write(f"\r解压进度: {(i+1)*100/total_files:.2f}% ({i+1}/{total_files})")
                    sys.stdout.flush()
                zip_ref.extract(file, extract_dir)
            
            print()  # 换行
        return True
    except Exception as e:
        print(f"解压失败：{e}")
        return False

def test_scrcpy_installation(scrcpy_dir):
    """测试scrcpy安装是否成功"""
    scrcpy_exe = os.path.join(scrcpy_dir, "scrcpy.exe")
    if not os.path.exists(scrcpy_exe):
        print(f"错误: 找不到scrcpy.exe: {scrcpy_exe}")
        return False
    
    adb_exe = os.path.join(scrcpy_dir, "adb.exe")
    if not os.path.exists(adb_exe):
        print(f"错误: 找不到adb.exe: {adb_exe}")
        return False
    
    print("检测scrcpy和adb可执行文件...")
    
    # 测试adb版本
    try:
        result = subprocess.run([adb_exe, "version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"ADB版本: {result.stdout.splitlines()[0]}")
        else:
            print(f"ADB测试失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"ADB测试出错: {e}")
        return False
    
    # 测试scrcpy版本
    try:
        result = subprocess.run([scrcpy_exe, "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Scrcpy版本: {result.stdout.strip()}")
        else:
            print(f"Scrcpy测试失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"Scrcpy测试出错: {e}")
        return False
    
    return True

def main():
    # 获取当前脚本所在目录作为工作目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 设置目标路径
    target_dir = os.path.join(script_dir, TARGET_DIR)
    zip_path = os.path.join(script_dir, "scrcpy-win64-v3.2.zip")
    
    # 检查是否已存在目标目录
    if os.path.exists(target_dir):
        choice = input(f"发现已存在的 {TARGET_DIR} 目录，是否覆盖? (y/n): ").lower()
        if choice != 'y':
            print("操作已取消")
            return
        
        print(f"正在删除已存在的 {TARGET_DIR} 目录...")
        try:
            shutil.rmtree(target_dir)
        except Exception as e:
            print(f"删除目录失败: {e}")
            return
    
    # 检查是否已存在下载文件
    if os.path.exists(zip_path):
        choice = input(f"发现已下载的文件 {os.path.basename(zip_path)}，是否重新下载? (y/n): ").lower()
        if choice != 'y':
            print("将使用已下载的文件")
        else:
            # 删除已存在的文件并重新下载
            os.unlink(zip_path)
            if not download_file(SCRCPY_URL, zip_path):
                print("下载失败，操作已取消")
                return
    else:
        # 下载scrcpy
        if not download_file(SCRCPY_URL, zip_path):
            print("下载失败，操作已取消")
            return
    
    # 创建临时解压目录
    extract_dir = os.path.join(script_dir, "temp_extract")
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)
    os.makedirs(extract_dir)
    
    # 解压ZIP
    if not extract_zip(zip_path, extract_dir):
        print("解压失败，操作已取消")
        shutil.rmtree(extract_dir)
        return
    
    # 找到解压后的scrcpy目录
    scrcpy_extracted = None
    for item in os.listdir(extract_dir):
        item_path = os.path.join(extract_dir, item)
        if os.path.isdir(item_path) and item.startswith("scrcpy-win64"):
            scrcpy_extracted = item_path
            break
    
    if not scrcpy_extracted:
        print("未找到解压后的scrcpy目录，请检查下载文件是否正确")
        shutil.rmtree(extract_dir)
        return
    
    # 移动到最终位置
    try:
        shutil.move(scrcpy_extracted, target_dir)
        print(f"成功安装scrcpy到 {target_dir}")
    except Exception as e:
        print(f"移动目录失败: {e}")
        shutil.rmtree(extract_dir)
        return
    
    # 清理临时目录
    shutil.rmtree(extract_dir)
    
    # 测试安装
    if test_scrcpy_installation(target_dir):
        print("\n✅ scrcpy环境安装成功!")
        print(f"\n现在您可以运行 python main.py 启动Scrcpy GUI，")
        print(f"程序将自动使用 {TARGET_DIR} 目录中的scrcpy和adb。")
        
        # 询问是否删除下载的ZIP文件
        choice = input("\n是否删除下载的ZIP文件以节省空间? (y/n): ").lower()
        if choice == 'y':
            try:
                os.unlink(zip_path)
                print(f"已删除文件: {zip_path}")
            except Exception as e:
                print(f"删除文件失败: {e}")
    else:
        print("\n❌ scrcpy环境安装测试失败，请检查安装")

if __name__ == "__main__":
    main() 