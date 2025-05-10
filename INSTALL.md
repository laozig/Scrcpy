# Scrcpy GUI 安装指南

## Windows 系统安装指南

### 1. 安装 ADB

1. 下载 [Android SDK Platform Tools](https://developer.android.com/studio/releases/platform-tools)
2. 解压到一个固定目录，如 `C:\android-sdk`
3. 将 ADB 所在目录添加到系统环境变量 Path 中:
   - 右键点击"此电脑" -> 属性 -> 高级系统设置 -> 环境变量
   - 在"系统变量"中找到并编辑"Path"
   - 点击"新建"并添加 ADB 所在的完整路径（如 `C:\android-sdk\platform-tools`）
   - 点击"确定"保存设置

4. 验证安装:
   - 打开命令提示符或 PowerShell
   - 运行 `adb version`
   - 如果显示版本信息，则安装成功

### 2. 安装 Scrcpy

1. 方法一：使用预编译版
   - 从 [Scrcpy GitHub 发布页](https://github.com/Genymobile/scrcpy/releases) 下载最新的 Windows 版本
   - 解压到一个固定目录，如 `C:\scrcpy`
   - 将 scrcpy 所在目录添加到系统环境变量 Path 中（同上述 ADB 的方法）

2. 方法二：使用包管理器（推荐）
   - 安装 [Chocolatey](https://chocolatey.org/install)
   - 打开管理员权限的 PowerShell
   - 运行 `choco install scrcpy`
   - 完成后会自动添加到环境变量

3. 验证安装:
   - 打开命令提示符或 PowerShell
   - 运行 `scrcpy --version`
   - 如果显示版本信息，则安装成功

### 3. 安装 Python 环境

1. 从 [Python 官网](https://www.python.org/downloads/windows/) 下载并安装 Python 3.6+
   - 安装时勾选"Add Python to PATH"选项
   - 建议勾选"Install pip"选项

2. 验证安装:
   - 打开命令提示符或 PowerShell
   - 运行 `python --version` 和 `pip --version`
   - 如果两个命令都显示版本信息，则安装成功

### 4. 安装 Scrcpy GUI

1. 克隆或下载本仓库:
   ```
   git clone https://github.com/yourusername/scrcpy-gui.git
   cd scrcpy-gui
   ```

2. 安装 Python 依赖:
   ```
   pip install -r requirements.txt
   ```

3. 运行程序:
   ```
   python main.py
   ```

### 5. 设备设置

1. 在 Android 设备上启用开发者选项:
   - 打开设置 -> 关于手机 -> 点击"版本号"多次直到提示已启用开发者选项

2. 启用 USB 调试:
   - 返回设置 -> 开发者选项 -> 启用"USB调试"

3. 连接设备:
   - 用 USB 线将设备连接到电脑
   - 设备上应该会弹出是否允许 USB 调试的提示，选择"允许"
   - 如果需要，可以勾选"始终允许来自此计算机的调试"

## 常见问题解决

### ADB 无法识别设备

1. 检查 USB 线是否正常工作
2. 确保已在设备上启用 USB 调试
3. 尝试不同的 USB 端口
4. 重新安装设备 USB 驱动
5. 重启设备和电脑

### Scrcpy 启动失败

1. 确保 ADB 可以识别设备（运行 `adb devices`）
2. 检查设备是否授权了 USB 调试
3. 尝试降低分辨率和比特率设置
4. 关闭设备上的省电模式

### 无线连接问题

1. 确保设备和电脑在同一 WiFi 网络
2. 检查设备 IP 地址是否正确
3. 确保 WiFi 网络没有阻止设备间通信
4. 尝试重新建立 USB 连接后再切换到无线连接 