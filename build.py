#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import platform
import subprocess

VERSION = "1.0.0"

def main():
    # 打印版本信息
    print(f"ScrcpyGUI 打包工具 v{VERSION}")
    print("="*50)
    
    # 获取当前操作系统
    system = platform.system()
    
    print(f"当前系统: {system}")
    print("准备打包 Scrcpy GUI 应用程序...")
    
    # 检查Python版本
    python_version = sys.version.split()[0]
    print(f"Python版本: {python_version}")
    if not (sys.version_info.major == 3 and sys.version_info.minor >= 6):
        print("警告: 推荐使用Python 3.6或更高版本进行打包")
    
    # 根据操作系统调用相应的打包脚本
    try:
        if system == "Windows":
            print("检测到 Windows 系统，使用 Windows 打包脚本...")
            import build_windows
            build_windows.main()
        elif system == "Darwin":  # macOS
            print("检测到 macOS 系统，使用 macOS 打包脚本...")
            import build_macos
            build_macos.main()
        elif system == "Linux":
            print("检测到 Linux 系统，使用 Linux 打包脚本...")
            import build_linux
            build_linux.main()
        else:
            print(f"不支持的操作系统: {system}")
            print("请手动使用相应的打包脚本:")
            print("- Windows: python build_windows.py")
            print("- macOS: python build_macos.py")
            print("- Linux: python build_linux.py")
            sys.exit(1)
        
        print("\n打包过程完成！")
        print("===============================")
        
        # 检查打包结果
        if system == "Windows":
            expected_file = os.path.join("dist", "ScrcpyGUI.exe")
        else:
            expected_file = os.path.join("dist", "ScrcpyGUI")
            
        if os.path.exists(expected_file):
            file_size = os.path.getsize(expected_file) / (1024 * 1024)
            print(f"成功创建可执行文件: {expected_file} ({file_size:.2f} MB)")
        else:
            print(f"警告: 未找到预期的可执行文件: {expected_file}")
            print("打包过程可能未完全成功，请检查上面的输出信息。")
        
        print("\n如需分发到不同平台，请在各目标平台上运行此脚本。")
        
    except ImportError as e:
        print(f"错误: 无法导入打包脚本: {e}")
        print("请确保build_windows.py、build_macos.py和build_linux.py文件存在于当前目录。")
        sys.exit(1)
    except Exception as e:
        print(f"打包过程中出现错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 