#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import platform
import subprocess

def main():
    # 获取当前操作系统
    system = platform.system()
    
    print(f"当前系统: {system}")
    print("准备打包 Scrcpy GUI 应用程序...")
    
    # 根据操作系统调用相应的打包脚本
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
    print("如需分发到不同平台，请在各目标平台上运行此脚本。")

if __name__ == "__main__":
    main() 