# Python虚拟环境使用指南

本文档介绍如何在 ScrcpyGUI 项目中使用 Python 虚拟环境。虚拟环境可以隔离依赖，减少系统 Python 与其他项目之间的冲突。

依赖项目：<https://github.com/Genymobile/scrcpy>

## 为什么使用虚拟环境？

- 隔离项目依赖，避免版本冲突
- 更容易管理项目特定的依赖
- 方便项目迁移和部署
- 不会影响系统级Python安装

## 创建虚拟环境

1. 在项目根目录下打开命令行/终端
2. 运行以下命令创建虚拟环境：

Windows:
```
python -m venv .venv
```

Linux/macOS:
```
python3 -m venv .venv
```

## 激活虚拟环境

根据您的操作系统，使用以下命令激活虚拟环境：

### Windows

命令提示符(CMD):
```
.venv\Scripts\activate.bat
```

PowerShell:
```
.\.venv\Scripts\Activate.ps1
```

### Linux/macOS

```
source .venv/bin/activate
```

激活成功后，命令提示符前会出现`(.venv)`前缀。

## 安装依赖

激活虚拟环境后，使用以下命令安装项目所需的所有依赖：

```
pip install -r requirements.txt
```

## 准备 scrcpy / adb 环境

安装完 Python 依赖后，还需要准备 scrcpy / adb。推荐做法：

```bash
python setup_scrcpy.py
```

该脚本会下载默认基线版本的 scrcpy 环境到项目目录中。

如果你已经：
- 在系统 PATH 中安装了 scrcpy / adb
- 或者打算在程序内手动指定依赖路径

则可以跳过该步骤。

## 运行程序

确保虚拟环境已激活，然后运行：

```
python main.py
```

快速校验：

```bash
python -m py_compile main.py
python .\main.py --version
```

## 添加新依赖

如果您需要添加新的依赖，可以使用以下命令：

```
pip install package_name
```

然后更新requirements.txt文件：

```
pip freeze > requirements.txt
```

## 退出虚拟环境

使用以下命令退出虚拟环境：

```
deactivate
```

## 注意事项

- 请始终在虚拟环境中运行和测试程序
- 添加新的依赖后记得更新requirements.txt
- `.venv`目录已被添加到`.gitignore`中，不会被提交到版本控制系统
- 在不同机器上部署时，需要重新创建虚拟环境并安装依赖
- 若切换了 scrcpy 版本，建议同时检查程序中的“环境自检”与“一键诊断”输出

## 故障排除

### 无法激活虚拟环境

如果您在Windows上使用PowerShell遇到执行策略限制，请以管理员身份运行PowerShell并执行：

```
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 依赖安装失败

如果遇到依赖安装问题，请尝试更新pip：

```
python -m pip install --upgrade pip
```

然后重新安装依赖。 

### 程序可以启动，但提示找不到 ADB / scrcpy

这通常不是虚拟环境问题，而是运行依赖未准备好。请按顺序检查：

1. 是否执行过 `python setup_scrcpy.py`
2. 是否在系统 PATH 中安装了 `adb` / `scrcpy`
3. 是否在程序菜单中手动设置了依赖路径
4. 查看程序中的“环境自检”和“一键诊断”
