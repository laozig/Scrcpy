# ScrcpyGUI

**一个用于控制安卓设备屏幕的图形化界面程序**

此项目为scrcpy提供了一个简洁易用的图形界面，使得连接和控制Android设备变得更加简单。

[English](#english) | [中文](#中文)

## 中文

### 主要功能

- 简单的设备连接和管理
- USB和无线（WiFi）连接方式
- 设备屏幕镜像显示
- 支持多设备同时连接
- 群控功能（多设备同步操作）
- 应用管理器
- 截图和录屏功能
- 自定义命令发送

### 详细说明文档

请查阅 [使用说明文档.md](使用说明文档.md) 获取更多信息，包括：
- 安装步骤
- 使用方法
- 打包说明
- 故障排除

### 环境要求

- Windows系统 (已测试：Windows 10/11)
- Python 3.8+
- scrcpy环境 (应用程序会提示下载或自动查找)

### 快速开始

1. 克隆或下载此仓库
2. 运行 `pip install -r requirements.txt` 安装依赖
3. 运行 `python main.py` 启动程序
4. 连接您的Android设备并开启USB调试

## English

A GUI interface for scrcpy to control Android device screens.

### Key Features

- Simple device connection and management
- USB and wireless (WiFi) connection methods
- Device screen mirroring
- Support for connecting multiple devices simultaneously
- Group control (synchronous operation across devices)
- Application manager
- Screenshot and screen recording functions
- Custom command sending

### Detailed Documentation

Please check [使用说明文档.md](使用说明文档.md) (Documentation in Chinese) for more information, including:
- Installation steps
- Usage guide
- Packaging instructions
- Troubleshooting

### Requirements

- Windows system (tested on Windows 10/11)
- Python 3.8+
- scrcpy environment (application will prompt for download or search automatically)

### Quick Start

1. Clone or download this repository
2. Run `pip install -r requirements.txt` to install dependencies
3. Run `python main.py` to start the program
4. Connect your Android device with USB debugging enabled

## 许可证 / License

[MIT License](LICENSE) 