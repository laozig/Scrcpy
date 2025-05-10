# Linux 安装指南

本文档提供了在 Linux 系统上安装和运行 Scrcpy GUI 的详细步骤。

## 支持的 Linux 发行版

Scrcpy GUI 应该可以在大多数主流 Linux 发行版上运行，包括但不限于：

- Ubuntu/Debian
- Fedora
- Arch Linux
- openSUSE
- Linux Mint

## 方法一：使用预编译版本（推荐）

1. 下载最新的 Linux 版本 `ScrcpyGUI`
2. 添加可执行权限：
   ```bash
   chmod +x ScrcpyGUI
   ```
3. 运行应用程序：
   ```bash
   ./ScrcpyGUI
   ```

或将其移动到系统路径中：

```bash
sudo mv ScrcpyGUI /usr/local/bin/
```

## 方法二：从源码运行

### 1. 安装必要的依赖

#### Ubuntu/Debian 系列

```bash
sudo apt update
sudo apt install python3 python3-pip python3-pyqt5 adb scrcpy
```

#### Fedora

```bash
sudo dnf install python3 python3-pip python3-qt5 android-tools scrcpy
```

#### Arch Linux

```bash
sudo pacman -S python python-pip python-pyqt5 android-tools scrcpy
```

### 2. 安装 Scrcpy GUI

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
python3 build_linux.py
```

生成的可执行文件将位于 `dist` 目录中。脚本也会自动创建桌面快捷方式。

## 设备设置

### 在 Android 设备上启用 USB 调试

1. 打开 设置 → 关于手机
2. 点击"版本号"多次，直到提示已启用开发者选项
3. 返回设置 → 开发者选项
4. 启用"USB调试"选项

### 连接设备

1. 用 USB 线将设备连接到计算机
2. 在设备上接受 USB 调试授权提示
3. 打开 Scrcpy GUI 应用，选择设备并点击连接

### 设置 udev 规则（可选但推荐）

为了让非 root 用户能访问 Android 设备，建议创建 udev 规则：

1. 创建一个新的 udev 规则文件：

```bash
sudo nano /etc/udev/rules.d/51-android.rules
```

2. 添加以下内容：

```
SUBSYSTEM=="usb", ATTR{idVendor}=="[VENDOR_ID]", MODE="0666", GROUP="plugdev"
```

将 `[VENDOR_ID]` 替换为您设备的厂商 ID（例如，三星通常是 04e8，小米通常是 2717）。

3. 保存文件并重新加载 udev 规则：

```bash
sudo chmod a+r /etc/udev/rules.d/51-android.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## WiFi 连接设置

要通过 WiFi 连接设备，请确保：

1. 设备和计算机在同一个 WiFi 网络中
2. 已经通过 USB 首次连接并授权设备
3. 使用"一键 WiFi 连接"功能，或手动输入设备 IP 地址

## 常见问题解决

### ADB 无法识别设备

- 确保已在设备上授权 USB 调试
- 尝试设置 udev 规则（见上文）
- 检查用户是否属于 `plugdev` 组

```bash
sudo usermod -aG plugdev $USER
```

然后注销并重新登录。

### GUI 无法启动

如果遇到 Qt 或 OpenGL 错误，请安装相关依赖：

```bash
# Ubuntu/Debian
sudo apt install libgl1-mesa-glx libxcb-xinerama0

# Fedora
sudo dnf install mesa-libGL libxcb

# Arch Linux
sudo pacman -S libgl libxcb
```

### scrcpy 启动失败

- 确认 ADB 可以识别设备：终端中运行 `adb devices`
- 尝试降低分辨率和比特率设置
- 确认 scrcpy 版本兼容：`scrcpy --version`

如果使用的是 Wayland 显示服务器，可能需要设置以下环境变量：

```bash
export QT_QPA_PLATFORM=xcb
```

您可以将此行添加到您的 `.bashrc` 或 `.zshrc` 文件中。 