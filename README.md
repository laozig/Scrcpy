# Scrcpy GUI - Android设备控制器

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/)
[![PyQt5](https://img.shields.io/badge/GUI-PyQt5-green.svg)](https://pypi.org/project/PyQt5/)

Scrcpy GUI是一个基于scrcpy的Android设备屏幕镜像和控制工具的图形界面。本项目提供直观的操作界面，让您轻松实现Android设备的投屏、控制和应用管理。

![Scrcpy GUI界面截图](icon.png)

## 核心功能

- **设备投屏**：实时显示Android设备屏幕内容
- **设备控制**：通过鼠标和键盘直接控制Android设备
- **应用管理**：一键安装、卸载、启动和停止应用
- **USB/WiFi连接**：支持USB有线和WiFi无线两种连接方式
- **多设备支持**：同时管理和控制多个Android设备
- **录屏/截图**：一键录制设备屏幕和捕获屏幕画面
- **性能调节**：自定义比特率、分辨率、帧率等参数
- **跨平台兼容**：支持Windows、macOS和Linux系统

## 系统要求

- **操作系统**：Windows 10/11、macOS 10.14+、Ubuntu 18.04+
- **Python**：3.6或更高版本
- **依赖项**：ADB、Scrcpy、PyQt5、Pillow

## 安装指南

### 前置依赖

1. **安装ADB**

   ADB（Android Debug Bridge）是与Android设备通信的必要工具。

   - **Windows**：
     ```
     下载Android SDK Platform Tools: https://developer.android.com/studio/releases/platform-tools
     解压后添加到系统PATH环境变量
     ```

   - **macOS**：
     ```bash
     brew install android-platform-tools
     ```

   - **Linux (Ubuntu/Debian)**：
     ```bash
     sudo apt update
     sudo apt install android-tools-adb
     ```

2. **安装Scrcpy**

   Scrcpy是实现屏幕镜像的核心工具。

   - **Windows**：
     ```
     方法1：使用Chocolatey
     choco install scrcpy

     方法2：下载预编译版本
     https://github.com/Genymobile/scrcpy/releases
     ```

   - **macOS**：
     ```bash
     brew install scrcpy
     ```

   - **Linux (Ubuntu/Debian)**：
     ```bash
     sudo apt install scrcpy
     ```

### 安装Scrcpy GUI

#### 方法1：虚拟环境安装（推荐）

```bash
# 1. 克隆或下载项目
git clone https://github.com/yourusername/scrcpy-gui.git
cd scrcpy-gui

# 2. 创建虚拟环境
python -m venv .venv

# 3. 激活虚拟环境
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# 4. 安装依赖
pip install -r requirements.txt

# 5. 运行程序
python main.py
```

#### 方法2：全局安装

```bash
# 1. 克隆或下载项目
git clone https://github.com/yourusername/scrcpy-gui.git
cd scrcpy-gui

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行程序
python main.py
   ```

#### 方法3：使用打包版本（Windows）

1. 下载最新版本的`ScrcpyGUI.exe`
2. 确保已正确安装ADB和Scrcpy
3. 双击运行`ScrcpyGUI.exe`

## 使用指南

### 设备连接

#### USB连接

1. 使用USB线缆连接Android设备与电脑
2. 在设备上启用USB调试模式：
   - 打开设备的"设置" → "开发者选项" → 启用"USB调试"
   - 如果看不到"开发者选项"，请先进入"关于手机"，多次点击"版本号"直到提示已启用开发者模式
3. 在Scrcpy GUI中点击"一键USB连接"按钮

#### WiFi连接

1. 确保Android设备和电脑处于同一WiFi网络
2. 首先通过USB连接设备（按照上述步骤）
3. 点击"一键WiFi连接"按钮
4. 连接成功后可以拔掉USB线缆，设备将保持无线连接

### 屏幕投射控制

- **调整画面质量**：修改比特率下拉菜单中的选项
- **修改分辨率**：调整分辨率下拉菜单中的选项
- **全屏显示**：勾选"全屏显示"选项
- **录制屏幕**：勾选"录制"选项并选择保存路径
- **截取屏幕**：点击"截图"按钮保存当前画面
- **无控制模式**：勾选"仅显示"选项，禁用对设备的控制
- **禁用剪贴板同步**：取消勾选"剪贴板同步"

### 设备推送/拉取文件

1. 推送文件到设备
   ```bash
   adb push <本地文件路径> <设备路径>
   # 例如：adb push test.txt /sdcard/
   ```

2. 从设备拉取文件
   ```bash
   adb pull <设备文件路径> <本地路径>
   # 例如：adb pull /sdcard/DCIM/Camera/IMG_1234.jpg ./
   ```

### 应用管理

1. 在顶部菜单栏中点击"工具" → "应用管理器"
2. 选择连接的设备
3. 应用列表将显示已安装的应用
4. 通过界面按钮执行以下操作：
   - 启动应用
   - 停止应用
   - 卸载应用
   - 查看应用信息

## 项目结构

```
Scrcpy-GUI/
│
├── main.py              # 主程序入口和GUI界面
├── scrcpy_controller.py # 设备控制核心组件
├── app_manager.py       # 应用管理器实现
├── utils.py             # 工具函数集合
├── launch_app_manager.py# 应用管理器启动脚本
├── build_windows.py     # Windows打包脚本
├── build.py             # 通用打包脚本
├── create_icon.py       # 图标生成工具
├── requirements.txt     # 项目依赖列表
├── scrcpy_config.json   # 配置文件
├── 启动应用管理器.bat    # 快捷启动批处理
└── README.md            # 项目说明文档
```

## 常见问题

### 1. 无法检测到设备？

- 确保已启用USB调试模式
- 检查是否已授权当前电脑连接（设备上会弹出授权提示）
- 使用`adb devices`命令验证设备是否正确连接
- 尝试更换USB线缆或USB端口
- 重启设备和电脑

### 2. WiFi连接失败？

- 确保设备和电脑在同一个WiFi网络
- 检查设备IP地址是否正确
- 尝试使用`adb connect <IP地址>:5555`命令手动连接
- 确保设备WiFi已启用并连接到正确的网络
- 检查路由器是否有防火墙限制

### 3. 画面卡顿？

- 降低比特率和分辨率设置
- 关闭录制功能
- 检查电脑和设备的性能是否足够
- 使用USB连接代替WiFi连接
- 关闭电脑上其他占用资源的程序

### 4. 应用管理器没有显示应用？

- 确保设备已正确连接
- 尝试点击刷新按钮
- 检查是否选择了正确的设备
- 重新启动应用管理器

## 故障排除

```bash
# 检查ADB版本
adb version

# 查看ADB设备连接状态
adb devices

# 重启ADB服务
adb kill-server
adb start-server

# 检查scrcpy版本
scrcpy --version

# 手动连接WiFi设备
adb tcpip 5555
adb connect <设备IP>:5555
```

## 贡献指南

欢迎贡献代码、报告问题或提出新功能建议！请遵循以下步骤:

1. Fork 本仓库
2. 创建您的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交您的更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 提交 Pull Request

## 许可证

该项目基于 [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0) 开源。

## 致谢

- [Scrcpy](https://github.com/Genymobile/scrcpy) - 本项目的核心功能基于scrcpy实现
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) - GUI界面框架 