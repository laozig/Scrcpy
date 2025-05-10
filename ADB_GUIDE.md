# ADB 文件传输指南

本指南详细介绍如何使用 ADB (Android Debug Bridge) 在计算机和 Android 设备之间传输文件。

## 什么是 ADB？

ADB (Android Debug Bridge) 是一个多功能的命令行工具，用于与 Android 设备进行通信。通过 ADB，您可以：

- 在计算机和设备之间传输文件
- 安装和卸载应用程序
- 运行 shell 命令
- 查看设备日志
- 以及执行许多其他设备管理任务

## 前提条件

在开始使用 ADB 传输文件之前，请确保：

1. 已安装 ADB 工具（请参考 [INSTALL.md](INSTALL.md)）
2. Android 设备已开启 USB 调试模式
3. 设备已通过 USB 连接到计算机，或通过 WiFi 连接

## 基本 ADB 命令

### 检查设备连接状态

在执行任何文件传输操作前，首先确认设备是否已正确连接：

```bash
adb devices
```

输出应类似于：
```
List of devices attached
ABCD1234    device
```

如果显示 `unauthorized`，请在设备上接受 USB 调试授权提示。

### 推送文件到设备 (adb push)

使用 `adb push` 命令将文件从计算机传输到 Android 设备：

```bash
adb push <本地文件路径> <设备文件路径>
```

示例：
```bash
# 推送单个文件到设备
adb push C:\Users\username\Documents\myfile.txt /sdcard/Download/

# 推送整个文件夹到设备
adb push C:\Users\username\Documents\myfolder /sdcard/Download/
```

**常用设备路径**：
- `/sdcard/` 或 `/storage/emulated/0/` - 设备内部存储根目录
- `/sdcard/Download/` - 下载文件夹
- `/sdcard/DCIM/Camera/` - 相机拍摄的照片/视频
- `/sdcard/Pictures/` - 图片文件夹

### 从设备拉取文件 (adb pull)

使用 `adb pull` 命令将文件从 Android 设备传输到计算机：

```bash
adb pull <设备文件路径> <本地文件路径>
```

示例：
```bash
# 从设备拉取单个文件
adb pull /sdcard/DCIM/Camera/IMG_1234.jpg C:\Users\username\Pictures\

# 从设备拉取整个文件夹
adb pull /sdcard/Download/ C:\Users\username\Downloads\phone_files\
```

如果省略本地路径，文件将下载到当前工作目录：
```bash
adb pull /sdcard/DCIM/Camera/IMG_1234.jpg
```

## 高级用法

### 指定设备

如果连接了多个设备，您需要使用 `-s` 参数指定目标设备：

```bash
adb -s <设备ID> push <本地文件路径> <设备文件路径>
adb -s <设备ID> pull <设备文件路径> <本地文件路径>
```

示例：
```bash
adb -s ABCD1234 push myfile.txt /sdcard/
```

### 使用通配符

您可以使用通配符批量传输文件：

```bash
# 推送所有 .jpg 文件
adb push C:\Users\username\Pictures\*.jpg /sdcard/Pictures/

# 拉取所有 .mp4 文件
adb pull /sdcard/DCIM/Camera/*.mp4 C:\Users\username\Videos\
```

### 显示传输进度

添加 `-p` 参数可以显示传输进度：

```bash
adb push -p <本地文件路径> <设备文件路径>
adb pull -p <设备文件路径> <本地文件路径>
```

### 使用 WiFi 传输文件

如果设备通过 WiFi 连接到 ADB，您可以使用相同的命令通过无线方式传输文件：

```bash
# 首先通过 USB 连接并启用 TCP/IP 模式
adb tcpip 5555

# 断开 USB 连接并通过 WiFi 连接设备
adb connect <设备IP地址>:5555

# 然后正常使用 push/pull 命令
adb push <本地文件路径> <设备文件路径>
adb pull <设备文件路径> <本地文件路径>
```

## 使用 Scrcpy GUI 传输文件

Scrcpy GUI 提供了基于 ADB 的文件传输功能：

1. 在 Scrcpy GUI 中连接设备
2. 选择"文件传输"选项
3. 使用图形界面选择要传输的文件和目标位置

## 常见问题解决

### 权限被拒绝

如果遇到权限错误：

```
adb: error: failed to copy 'file.txt' to '/sdcard/file.txt': remote couldn't create file: Permission denied
```

尝试以下解决方案：

1. 确保目标目录可写入：
   ```bash
   adb shell ls -la /sdcard/
   ```

2. 在较新的 Android 版本中，尝试使用其他存储位置：
   ```bash
   adb push file.txt /storage/emulated/0/Download/
   ```

3. 使用 root 访问权限（如果设备已 root）：
   ```bash
   adb root
   adb push file.txt /data/local/tmp/
   ```

### 存储空间不足

如果设备存储空间不足，请先清理设备上的文件或使用 `adb shell df` 检查可用空间。

### 文件未找到

如果提示"文件未找到"，请仔细检查路径是否正确，包括文件名大小写。

### 设备离线或未授权

如果设备显示为"offline"或"unauthorized"，请尝试：

1. 在设备上接受 USB 调试授权
2. 重新启动 ADB 服务：
   ```bash
   adb kill-server
   adb start-server
   ```
3. 尝试使用不同的 USB 电缆或端口
4. 重启设备和计算机

## 有用的 ADB 文件管理命令

### 列出设备上的文件和目录

```bash
adb shell ls -la /sdcard/
```

### 在设备上创建目录

```bash
adb shell mkdir /sdcard/mynewfolder
```

### 删除设备上的文件或目录

```bash
# 删除文件
adb shell rm /sdcard/myfile.txt

# 删除目录及其所有内容
adb shell rm -rf /sdcard/myfolder
```

### 查看文件内容

```bash
adb shell cat /sdcard/myfile.txt
```

### 检查设备存储空间

```bash
adb shell df -h
```

## 总结

ADB 提供了简单高效的方式在计算机和 Android 设备之间传输文件。掌握这些命令后，您可以轻松管理设备文件，而无需使用第三方工具或依赖设备制造商的软件。通过结合 Scrcpy GUI 的直观界面和 ADB 的强大功能，您可以获得最佳的 Android 设备管理体验。 