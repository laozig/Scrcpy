# ScrcpyGUI

**一个基于 scrcpy 的安卓设备屏幕控制图形界面**

本项目为 scrcpy 提供更直观的桌面操作界面，简化设备连接、镜像控制与常用配置流程。

依赖项目：scrcpy https://github.com/Genymobile/scrcpy

[English](#english) | [中文](#中文)

## 中文

### 界面截图
![XWzoPw3pCADd9YAqjq1UzM8VWTUpY76u.webp](https://cdn.nodeimage.com/i/XWzoPw3pCADd9YAqjq1UzM8VWTUpY76u.webp)
![HcBpvP8R4XRq7UQO2R3Z8FEiu1P4zncx.webp](https://cdn.nodeimage.com/i/HcBpvP8R4XRq7UQO2R3Z8FEiu1P4zncx.webp)

### 主要功能

- 设备连接与管理：USB/无线连接、设备列表自动刷新、一键连接所有设备
- 设备屏幕镜像：支持多设备同时运行，窗口标题包含设备信息便于识别
- 镜像参数：码率、最大尺寸、方向限制等常用参数快速配置
- 录屏与截图：支持录制格式选择、保存路径配置、批量截图
- 窗口与交互：全屏、置顶、显示触摸、仅显示（无交互）、禁用剪贴板
- 应用管理器：应用列表、搜索与排序、启动/停止/卸载、系统应用筛选
- 环境自动识别：优先使用项目内置 scrcpy-win64-v3.2，其次使用系统 PATH
- 同步群控：维护中，暂不保证稳定

### 详细说明文档

请查阅 [使用说明文档.md](使用说明文档.md) 获取更多信息，包括：
- 安装步骤
- 使用方法
- 打包说明
- 故障排除

### 环境要求

- Windows系统 (已测试：Windows 10/11)
- Python 3.8+
- scrcpy/adb环境（支持以下任一方式）
  - 项目目录下的 `scrcpy-win64-v3.2`
  - 系统 PATH 中已安装的 scrcpy/adb
  - 运行 `python setup_scrcpy.py` 一键下载并配置

### 快速开始

1. 克隆或下载此仓库
2. 运行 `pip install -r requirements.txt` 安装依赖
3. 可选：运行 `python setup_scrcpy.py` 自动下载配置 scrcpy/adb
4. 运行 `python main.py` 启动程序
5. 连接 Android 设备并开启 USB 调试

## English

A GUI wrapper around scrcpy for controlling and mirroring Android device screens.

Powered by scrcpy: https://github.com/Genymobile/scrcpy

### Key Features

- Device connection and management (USB/WiFi, auto refresh, one-click connect all)
- Multi-device screen mirroring with descriptive window titles
- Common mirror options: bitrate, max size, orientation limit
- Recording and screenshots (format selection, save path, batch screenshots)
- Window and interaction options: fullscreen, always on top, show touches, view-only, disable clipboard
- App manager: list, search/sort, start/stop/uninstall, system app filter
- Auto-detect local/system adb and scrcpy (bundled scrcpy-win64-v3.2 supported)
- Sync group control: under maintenance, stability not guaranteed

### Detailed Documentation

Please check [使用说明文档.md](使用说明文档.md) (Documentation in Chinese) for more information, including:
- Installation steps
- Usage guide
- Packaging instructions
- Troubleshooting

### Requirements

- Windows system (tested on Windows 10/11)
- Python 3.8+
- scrcpy/adb available in one of these ways:
  - `scrcpy-win64-v3.2` under the project directory
  - scrcpy/adb installed in system PATH
  - run `python setup_scrcpy.py` to download and configure automatically

### Quick Start

1. Clone or download this repository
2. Run `pip install -r requirements.txt` to install dependencies
3. Optional: run `python setup_scrcpy.py` to download and configure scrcpy/adb
4. Run `python main.py` to start the program
5. Connect your Android device with USB debugging enabled

## 许可证 / License

[MIT License](LICENSE) 
