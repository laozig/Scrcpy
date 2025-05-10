# Scrcpy GUI

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/)
[![PyQt5](https://img.shields.io/badge/GUI-PyQt5-green.svg)](https://pypi.org/project/PyQt5/)

这是一个基于scrcpy的Android设备屏幕镜像和控制工具的精简GUI界面。本项目专注于提供最基本的投屏和设备控制功能，移除了不必要的复杂功能，保持轻量高效。

## 功能特点

- **屏幕镜像**：实时显示Android设备屏幕内容
- **设备控制**：通过鼠标和键盘控制Android设备
- **多设备支持**：同时管理和控制多个Android设备
- **USB/WiFi连接**：支持USB有线和WiFi无线两种连接方式
- **录屏/截图**：支持录制设备屏幕和截取屏幕画面
- **性能调节**：可调整比特率、分辨率、帧率等参数

## 安装指南

### 前置条件

- Python 3.6+
- ADB (Android Debug Bridge)
- Scrcpy

### 安装步骤

1. 克隆本仓库:
```bash
git clone https://github.com/yourusername/scrcpy-gui.git
cd scrcpy-gui
```

2. 安装依赖:
```bash
pip install -r requirements.txt
```

3. 运行程序:
```bash
python main.py
```

## 使用方法

### 连接设备

1. **USB连接**:
   - 使用USB线连接设备到电脑
   - 确保设备已开启USB调试
   - 点击"一键USB连接"按钮

2. **WiFi连接**:
   - 先通过USB连接设备
   - 确保设备和电脑在同一WiFi网络
   - 点击"一键WiFi连接"按钮
   - 连接成功后可拔掉USB线

### 常用操作

- **修改画面质量**: 调整比特率和分辨率
- **截图**: 点击"截图"按钮保存当前画面
- **录制**: 勾选"录制"并设置保存路径
- **全屏模式**: 勾选"全屏显示"选项
- **停止镜像**: 点击"停止"按钮结束当前连接

## 项目结构

- **main.py**: 主程序入口和GUI界面实现
- **scrcpy_controller.py**: 设备控制核心，负责与scrcpy和adb交互
- **utils.py**: 工具函数集合
- **requirements.txt**: 项目依赖

## 常见问题

- **无法连接设备?**
  确保已在设备上授权USB调试，并且ADB能够识别设备

- **WiFi连接失败?**
  确保设备和电脑在同一网络，检查设备IP地址是否正确

- **画面卡顿?**
  尝试降低比特率和分辨率，关闭其他占用网络带宽的应用

## 贡献指南

欢迎贡献代码、报告问题或提出新功能建议。请遵循以下步骤:

1. Fork 本仓库
2. 创建您的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交您的更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 提交 Pull Request

## 许可证

该项目基于 [GNU General Public License v3.0](https://github.com/Genymobile/scrcpy/blob/master/LICENSE) 开源。

## 致谢

- [Scrcpy](https://github.com/Genymobile/scrcpy) - 本项目的核心功能基于scrcpy实现
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) - GUI界面框架 