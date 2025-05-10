# Python 虚拟环境使用指南

本指南详细介绍如何为 Scrcpy GUI 项目创建、激活和使用 Python 虚拟环境，以避免与系统其他 Python 项目的依赖冲突。

## 什么是虚拟环境？

虚拟环境是一个独立的 Python 解释器环境，它允许您为特定项目安装和管理依赖包，而不会影响系统全局 Python 环境或其他项目。使用虚拟环境的好处包括：

- 避免不同项目之间的依赖冲突
- 简化依赖管理和版本控制
- 保持项目环境的一致性和可重现性
- 便于分享和部署项目

## 准备工作

确保您已经安装了 Python 3.6 或更高版本。您可以通过以下命令检查 Python 版本：

```bash
python --version
```

## 在 Windows 上设置虚拟环境

### 创建虚拟环境

1. 打开命令提示符或 PowerShell
2. 导航到 Scrcpy GUI 项目目录：
   ```
   cd path\to\scrcpy-gui
   ```
3. 创建虚拟环境：
   ```
   python -m venv .venv
   ```
   > 注意：`.venv` 是虚拟环境的名称，您可以使用任何名称，但 `.venv` 是常见的约定。

### 激活虚拟环境

在命令提示符中：
```
.venv\Scripts\activate.bat
```

在 PowerShell 中：
```
.venv\Scripts\Activate.ps1
```

成功激活后，您的命令提示符前面会出现 `(.venv)` 标记。

### 安装依赖

在激活的虚拟环境中安装项目依赖：
```
pip install -r requirements.txt
```

### 运行应用程序

```
python main.py
```

### 退出虚拟环境

当您完成工作后，可以使用以下命令退出虚拟环境：
```
deactivate
```

## 在 Linux/macOS 上设置虚拟环境

### 创建虚拟环境

1. 打开终端
2. 导航到 Scrcpy GUI 项目目录：
   ```bash
   cd path/to/scrcpy-gui
   ```
3. 创建虚拟环境：
   ```bash
   python3 -m venv .venv
   ```

### 激活虚拟环境

```bash
source .venv/bin/activate
```

成功激活后，您的终端提示符前面会出现 `(.venv)` 标记。

### 安装依赖

在激活的虚拟环境中安装项目依赖：
```bash
pip install -r requirements.txt
```

### 运行应用程序

```bash
python main.py
```

### 退出虚拟环境

当您完成工作后，可以使用以下命令退出虚拟环境：
```bash
deactivate
```

## 使用虚拟环境的最佳实践

### 1. 更新 pip

创建虚拟环境后，建议首先更新 pip：
```
python -m pip install --upgrade pip
```

### 2. 保存依赖列表

如果您安装了新的依赖，记得更新 requirements.txt 文件：
```
pip freeze > requirements.txt
```

### 3. 使用 .gitignore

确保将虚拟环境目录添加到 .gitignore 文件中，避免将虚拟环境文件提交到代码仓库：
```
# .gitignore
.venv/
```

### 4. 创建快速启动脚本

为了简化操作，您可以创建批处理文件或脚本来自动激活虚拟环境并启动应用程序。

Windows (run.bat)：
```batch
@echo off
call .venv\Scripts\activate.bat
python main.py
```

Linux/macOS (run.sh)：
```bash
#!/bin/bash
source .venv/bin/activate
python main.py
```

## 使用 IDE 集成虚拟环境

### PyCharm

1. 打开项目
2. 转到 File > Settings > Project > Python Interpreter
3. 点击齿轮图标 > Add
4. 选择 "Existing environment"
5. 选择虚拟环境中的 Python 解释器：`.venv\Scripts\python.exe` (Windows) 或 `.venv/bin/python` (Linux/macOS)
6. 点击 "OK" 确认

### VS Code

1. 打开项目
2. 按 `Ctrl+Shift+P` (或 `Cmd+Shift+P` on macOS) 打开命令面板
3. 输入并选择 "Python: Select Interpreter"
4. 选择以 `.venv` 开头的解释器

## 故障排除

### 无法激活虚拟环境

**Windows PowerShell 问题**：
如果在 PowerShell 中收到类似 "无法加载文件，因为在此系统上禁止运行脚本" 的错误，需要更改执行策略：
```
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**找不到虚拟环境**：
确保您位于正确的项目目录中，并且已正确创建虚拟环境。

### 依赖安装问题

如果安装依赖时遇到问题，尝试以下方法：

1. 确保您已激活虚拟环境
2. 单独安装有问题的依赖：
   ```
   pip install package_name
   ```
3. 尝试指定较低版本：
   ```
   pip install package_name==specific_version
   ```

### 其他资源

- [Python 官方虚拟环境文档](https://docs.python.org/3/library/venv.html)
- [pip 用户指南](https://pip.pypa.io/en/stable/user_guide/)
- [virtualenv 文档](https://virtualenv.pypa.io/en/latest/) (venv 的替代品) 