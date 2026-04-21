# ScrcpyGUI

[![Release](https://img.shields.io/github/v/release/laozig/Scrcpy?label=Release)](https://github.com/laozig/Scrcpy/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/laozig/Scrcpy/total?label=Downloads)](https://github.com/laozig/Scrcpy/releases/latest)
[![License](https://img.shields.io/github/license/laozig/Scrcpy)](LICENSE)

**一个面向 Windows 的 Android 投屏与辅助管理图形界面，基于 scrcpy 构建。**

本项目为 `scrcpy` 提供更直观的桌面操作入口，重点解决以下问题：
- 设备连接路径不统一
- scrcpy/adb 环境部署麻烦
- 常用投屏参数需要反复手输
- 截图、录屏、应用管理、诊断信息分散

依赖项目：<https://github.com/Genymobile/scrcpy>

[English](#english) | [中文](#中文)

---

## 中文

### 最新版本

- 最新发行版：[`v1.0.1`](https://github.com/laozig/Scrcpy/releases/tag/v1.0.1)
- 下载发布页：<https://github.com/laozig/Scrcpy/releases/latest>
- 单文件版：[`ScrcpyGUI_v1.0.1.exe`](https://github.com/laozig/Scrcpy/releases/download/v1.0.1/ScrcpyGUI_v1.0.1.exe)
- 便携版：[`ScrcpyGUI_Portable_v1.0.1.zip`](https://github.com/laozig/Scrcpy/releases/download/v1.0.1/ScrcpyGUI_Portable_v1.0.1.zip)

### 项目定位

ScrcpyGUI 是一个偏“实用工具型”的桌面应用，核心目标是：

1. **快速连接 Android 设备进行投屏**
2. **降低 scrcpy/adb 环境配置门槛**
3. **把常用投屏控制、截图、录屏、应用管理集中到一个界面中**
4. **为环境问题提供可诊断、可追踪、可覆盖的路径解析机制**

---

### 当前主要功能

#### 1. 设备连接与投屏
- USB 连接投屏
- WiFi 连接投屏
- 设备列表自动刷新
- 显示设备状态（可用 / 离线 / 未授权）
- 窗口标题自动带设备型号和设备 ID
- 运行中切换“窗口置顶”可即时生效

#### 2. 投屏参数与预设
- 视频码率
- 最大尺寸
- 最大帧率
- 视频编码器选择
- 方向限制
- 显示 ID
- Crop 裁剪参数校验
- 参数预设与设备专属参数记忆
- 纯录制模式 / 无窗口模式联动

#### 3. 截图与录屏
- 普通截图
- 快速截图到默认目录
- 截图按日期归档
- 录屏路径选择
- 录屏完成后自动打开目录或文件

#### 4. 应用管理器
- 已安装应用列表
- 搜索、拼音搜索、首字母搜索
- 用户应用 / 系统应用过滤
- 最近操作应用过滤
- 前台应用定位
- 启动、停止、卸载应用
- 清除数据 / 清缓存
- 导出 APK
- 安装 APK / 安装分包 APK
- 内置 ADB 命令执行页
- ADB 历史命令与常用命令模板
- 查看应用详细信息

#### 5. 环境与诊断
- 环境自检
- 一键诊断报告
- 显示 ADB / scrcpy / scrcpy-server 的**解析路径与来源**
- 支持手动指定：
  - ADB 路径
  - scrcpy 路径
  - scrcpy-server 路径
- 支持恢复自动检测依赖路径

---

### 环境部署策略（当前实现）

当前项目已经升级为更稳的依赖解析策略：

**用户显式配置 > 打包内置 / 本地目录 > PATH > 常见安装目录 > 命令名兜底**

也就是说：

1. 如果你在程序里手动指定了 `adb.exe` / `scrcpy.exe` / `scrcpy-server.jar`，优先使用这些配置。
2. 否则程序会优先搜索项目目录、打包目录、本地可执行文件目录。
3. 再找系统 `PATH`。
4. 再尝试常见安装目录。
5. 最后才回退到 `adb` / `scrcpy` 这种命令名方式。

默认安装脚本当前使用 **scrcpy 3.3.4**，但运行时并没有被锁死；你仍然可以在程序菜单中切换到任意更新版本的 scrcpy。

---

### 快速开始

#### 方式一：开发运行

1. 克隆或下载仓库
2. 安装依赖

```bash
pip install -r requirements.txt
```

3. 可选：自动下载默认版 scrcpy 环境

```bash
python setup_scrcpy.py
```

4. 启动程序

```bash
python main.py
```

5. 在 Android 设备上开启 USB 调试并授权

#### 方式二：使用现成 scrcpy 环境

如果你已经在系统中安装了 scrcpy / adb，或者已有自己的 scrcpy 目录：

- 可以直接运行程序
- 也可以在程序菜单中手动指定 ADB / scrcpy / scrcpy-server 路径

---

### 文档导航

- [使用说明文档.md](使用说明文档.md)：用户使用与部署说明
- [ADB_GUIDE.md](ADB_GUIDE.md)：ADB 文件传输与常用命令
- [VENV_GUIDE.md](VENV_GUIDE.md)：虚拟环境使用说明
- [使用GitHub说明.md](使用GitHub说明.md)：仓库协作与发布说明
- [CHANGE_LOG.md](CHANGE_LOG.md)：更新记录与变更摘要

---

## English

ScrcpyGUI is a Windows-oriented GUI wrapper around `scrcpy` for Android screen mirroring and helper workflows.

### Latest release

- Latest version: [`v1.0.1`](https://github.com/laozig/Scrcpy/releases/tag/v1.0.1)
- Release page: <https://github.com/laozig/Scrcpy/releases/latest>
- Single-file build: [`ScrcpyGUI_v1.0.1.exe`](https://github.com/laozig/Scrcpy/releases/download/v1.0.1/ScrcpyGUI_v1.0.1.exe)
- Portable bundle: [`ScrcpyGUI_Portable_v1.0.1.zip`](https://github.com/laozig/Scrcpy/releases/download/v1.0.1/ScrcpyGUI_Portable_v1.0.1.zip)

### Key capabilities
- USB / WiFi device connection
- Screen mirroring with runtime topmost switching
- Common scrcpy parameter presets and per-device profiles
- Screenshot and recording workflows
- App manager (search, filter, start/stop/uninstall, export APK, install APK, split APK install, ADB command panel)
- Environment self-check and diagnosis report
- Explicit dependency path override for:
  - ADB
  - scrcpy
  - scrcpy-server

### Runtime dependency strategy

The project now uses this resolution order:

**User-configured path > bundled/local path > PATH > common install paths > command fallback**

Default installer version is currently **scrcpy 3.3.4**, but runtime usage is not hard-locked; users can still point the app to a newer scrcpy version manually.

### Quick start

```bash
pip install -r requirements.txt
python setup_scrcpy.py   # optional
python main.py
```

---

## 许可证 / License

[MIT License](LICENSE)
