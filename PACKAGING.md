# Scrcpy GUI 打包指南

本文档提供了如何在不同平台上打包和安装 Scrcpy GUI 的详细说明。

## 打包应用程序

### 先决条件

- Python 3.6 或更高版本
- pip (Python 包管理器)
- 依赖项: PyQt5

### 通用打包方法

我们提供了一个通用的打包脚本，可以自动检测您的操作系统并使用相应的平台特定打包脚本：

```bash
python build.py
```

这个脚本会自动安装所需的依赖，然后使用 PyInstaller 来创建一个可执行文件。

### 特定平台打包

如果您想手动指定平台，可以直接运行特定平台的打包脚本：

- Windows: `python build_windows.py`
- macOS: `python build_macos.py`
- Linux: `python build_linux.py`

## 安装指南

### Windows

1. 运行 `build_windows.py` 脚本生成可执行文件
2. 在 `dist` 目录中找到 `ScrcpyGUI.exe`
3. 将该文件复制到任何位置，双击运行即可
4. 确保已安装 ADB 和 scrcpy，并添加到系统 PATH 中

### macOS

1. 运行 `build_macos.py` 脚本生成可执行文件
2. 在 `dist` 目录中找到 `ScrcpyGUI` 应用程序
3. 将该应用程序复制到 Applications 文件夹或任何位置
4. 确保已安装 ADB 和 scrcpy
   
   ```bash
   brew install android-platform-tools
   brew install scrcpy
   ```

### Linux

1. 运行 `build_linux.py` 脚本生成可执行文件
2. 在 `dist` 目录中找到 `ScrcpyGUI` 可执行文件
3. 确保已安装 ADB 和 scrcpy

   Ubuntu/Debian:
   ```bash
   sudo apt update
   sudo apt install android-tools-adb scrcpy
   ```

   Fedora:
   ```bash
   sudo dnf install android-tools scrcpy
   ```

   Arch Linux:
   ```bash
   sudo pacman -S android-tools scrcpy
   ```

4. 脚本会自动创建桌面快捷方式，位于 `~/.local/share/applications/scrcpy-gui.desktop`

## 疑难解答

### Windows 打包问题

- 如果遇到 DLL 错误，请确保已安装 Visual C++ 可再发行包
- 如果应用程序无法启动，尝试在命令行中运行可执行文件，查看错误消息

### macOS 打包问题

- 如果收到"应用程序已损坏"的错误，请尝试：
  ```bash
  xattr -cr /Applications/ScrcpyGUI.app
  ```
- 确保在"系统偏好设置 > 安全性与隐私"中允许运行未验证的应用

### Linux 打包问题

- 如果遇到 Qt 或 OpenGL 错误，请安装相关依赖：
  ```bash
  # Ubuntu/Debian
  sudo apt install libgl1-mesa-glx libxcb-xinerama0
  
  # Fedora
  sudo dnf install mesa-libGL libxcb
  
  # Arch Linux
  sudo pacman -S libgl libxcb
  ```

## 注意事项

- 请注意，打包后的应用程序仍然依赖于系统中已安装的 ADB 和 scrcpy
- 应用程序会在运行时自动查找 ADB 和 scrcpy 的路径
- 如果 ADB 或 scrcpy 不在系统 PATH 中，您可能需要手动指定路径

如有任何问题，请在 GitHub 上提交 Issue。 