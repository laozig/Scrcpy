# Scrcpy GUI 安装指南

本文档提供了在各种操作系统上安装 Scrcpy GUI 的详细步骤，包括依赖项的安装、配置和常见问题的解决方法。

## 目录

1. [Windows 安装指南](#windows-安装指南)
2. [设置 Python 环境](#设置-python-环境)
3. [虚拟环境配置](#虚拟环境配置)
4. [配置 ADB 和 Scrcpy](#配置-adb-和-scrcpy)
5. [安装及启动 Scrcpy GUI](#安装及启动-scrcpy-gui)
6. [故障排除](#故障排除)

## Windows 安装指南

### 系统要求

- Windows 10 或 Windows 11
- Python 3.6+ (推荐 Python 3.8 或更高版本)
- ADB (Android Debug Bridge)
- Scrcpy

### 安装 Python

1. 访问 [Python 官方网站](https://www.python.org/downloads/windows/) 下载最新版本
2. 运行安装程序，**务必勾选 "Add Python to PATH"** 选项
3. 完成安装后，打开命令提示符，验证 Python 是否正确安装：
   ```
   python --version
   pip --version
   ```

### 安装 ADB

1. 下载 [Android SDK Platform Tools](https://developer.android.com/studio/releases/platform-tools)
2. 解压下载的文件到合适的位置，例如 `C:\Android\platform-tools`
3. 添加 ADB 到系统环境变量 PATH：
   - 右键点击"此电脑" → 属性 → 高级系统设置 → 环境变量
   - 在"系统变量"部分，找到 Path 变量并点击"编辑"
   - 点击"新建"，添加解压路径，例如 `C:\Android\platform-tools`
   - 点击确定保存更改
4. 打开新的命令提示符，验证 ADB 是否正确安装：
   ```
   adb version
   ```

### 安装 Scrcpy

**方法 1：使用 Chocolatey（推荐）**

1. 安装 [Chocolatey](https://chocolatey.org/install)
2. 以管理员身份打开 PowerShell，运行：
   ```
   choco install scrcpy
   ```

**方法 2：手动安装**

1. 从 [Scrcpy GitHub 发布页面](https://github.com/Genymobile/scrcpy/releases) 下载最新的 Windows 预编译包
2. 解压文件到合适的位置，例如 `C:\Program Files\scrcpy`
3. 添加 Scrcpy 目录到系统环境变量 PATH（参考安装 ADB 的步骤）
4. 打开新的命令提示符，验证 Scrcpy 是否正确安装：
   ```
   scrcpy --version
   ```

## 设置 Python 环境

### 安装 Python 依赖项

1. 克隆或下载 Scrcpy GUI 项目：
   ```
   git clone https://github.com/yourusername/scrcpy-gui.git
   cd scrcpy-gui
   ```

2. 安装依赖项：
   ```
   pip install -r requirements.txt
   ```

### 更新 pip（可选但推荐）

```
python -m pip install --upgrade pip
```

## 虚拟环境配置

使用虚拟环境可以避免与系统其他 Python 项目的依赖冲突。

### 创建和激活虚拟环境

**Windows**:
```
python -m venv .venv
.venv\Scripts\activate
```

**Linux/macOS**:
```
python -m venv .venv
source .venv/bin/activate
```

### 在虚拟环境中安装依赖

```
pip install -r requirements.txt
```

### 退出虚拟环境（使用完毕后）

```
deactivate
```

## 配置 ADB 和 Scrcpy

### 验证 ADB 连接

1. 确保已在 Android 设备上启用 USB 调试
2. 使用 USB 线连接设备到计算机
3. 运行命令检查连接：
   ```
   adb devices
   ```
4. 首次连接时，设备会显示授权提示，点击"允许"或"确认"

### 测试 Scrcpy

```
scrcpy
```

成功运行后，您应该能看到设备屏幕显示在计算机上。

## 安装及启动 Scrcpy GUI

### 从源码运行

确保已完成前面所有步骤后，在项目目录中运行：
```
python main.py
```

### 使用批处理文件启动（Windows）

项目提供了快捷启动批处理文件，可以双击运行：
```
启动应用管理器.bat
```

### 创建快捷方式（可选）

为方便使用，可以创建桌面快捷方式：

1. 右键单击桌面 → 新建 → 快捷方式
2. 为主程序输入位置：`C:\Python38\pythonw.exe D:\path\to\scrcpy-gui\main.py`
3. 为应用管理器输入位置：`C:\Python38\pythonw.exe D:\path\to\scrcpy-gui\launch_app_manager.py`
4. 点击下一步，为快捷方式命名，然后点击完成
5. 右键单击创建的快捷方式 → 属性
6. 可以选择更改图标，选择项目中的 `1.ico` 文件

## 故障排除

### ADB 连接问题

**设备未授权**：
```
adb devices
```
如显示 `???????????? unauthorized`，请在设备上点击允许 USB 调试。

**无法识别设备**：
```
adb kill-server
adb start-server
adb devices
```

**驱动问题**：
为您的特定设备安装正确的 USB 驱动程序。

### Scrcpy 启动失败

**错误：could not find or load scrcpy server**
- 确认 Scrcpy 安装正确
- 尝试重新安装最新版本的 Scrcpy

**错误：Could not initialize OpenGL**
- 更新图形驱动程序
- 检查是否能运行其他 OpenGL 应用程序

### Python 相关问题

**ImportError: No module named 'PyQt5'**
确保正确安装了所有依赖：
```
pip install PyQt5
pip install -r requirements.txt
```

**权限错误**
在 Windows 上，尝试以管理员身份运行命令提示符或 PowerShell。

---

如果您遇到其他安装问题，请查看项目 GitHub 页面中的 Issues 部分，或者提交新的 Issue。 