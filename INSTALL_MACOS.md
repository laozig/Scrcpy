# macOS 安装指南

本文档提供了在 macOS 系统上安装和运行 Scrcpy GUI 的详细步骤。

## 方法一：使用预编译版本（推荐）

1. 下载最新的 macOS 版本 `ScrcpyGUI.app` 或 `ScrcpyGUI`
2. 将下载的 `.app` 文件拖到"应用程序"文件夹
3. 首次运行时，可能需要在"系统偏好设置 > 安全性与隐私"中允许运行

### 如果遇到"应用已损坏"的提示

打开终端，运行以下命令：

```bash
xattr -cr /Applications/ScrcpyGUI.app
```

然后重新尝试打开应用程序。

## 方法二：从源码运行

### 1. 安装 Homebrew

如果尚未安装 Homebrew，打开终端并运行：

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2. 安装 ADB 和 Scrcpy

```bash
brew install android-platform-tools
brew install scrcpy
```

### 3. 安装 Python 环境

macOS 通常预装了 Python，但建议使用 Homebrew 安装最新版本：

```bash
brew install python
```

### 4. 安装 Scrcpy GUI

1. 克隆或下载本仓库:
   ```bash
   git clone https://github.com/yourusername/scrcpy-gui.git
   cd scrcpy-gui
   ```

2. 安装 Python 依赖:
   ```bash
   pip3 install -r requirements.txt
   ```

3. 运行程序:
   ```bash
   python3 main.py
   ```

## 自行打包应用程序

如果您希望自己打包应用程序，可以使用提供的打包脚本：

```bash
python3 build_macos.py
```

生成的应用将位于 `dist` 目录中。

## 设备设置

### 在 Android 设备上启用 USB 调试

1. 打开 设置 → 关于手机
2. 点击"版本号"多次，直到提示已启用开发者选项
3. 返回设置 → 开发者选项
4. 启用"USB调试"选项

### 连接设备

1. 用 USB 线将设备连接到 Mac
2. 在设备上接受 USB 调试授权提示
3. 打开 Scrcpy GUI 应用，选择设备并点击连接

## WiFi 连接设置

要通过 WiFi 连接设备，请确保：

1. 设备和 Mac 在同一个 WiFi 网络中
2. 已经通过 USB 首次连接并授权设备
3. 使用"一键 WiFi 连接"功能，或手动输入设备 IP 地址

## 常见问题解决

### ADB 无法识别设备

- 确保已在设备上授权 USB 调试
- 尝试断开并重新连接 USB 线
- 重启设备和计算机
- 检查 USB 电缆是否支持数据传输（某些仅支持充电）

### scrcpy 启动失败

- 确认 ADB 可以识别设备：终端中运行 `adb devices`
- 尝试降低分辨率和比特率设置
- 确认 scrcpy 版本兼容：`scrcpy --version`

如果上述方法无法解决问题，请尝试重新安装 ADB 和 scrcpy：

```bash
brew reinstall android-platform-tools
brew reinstall scrcpy
``` 