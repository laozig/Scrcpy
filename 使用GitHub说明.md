# GitHub 配置与协作说明

依赖项目：<https://github.com/Genymobile/scrcpy>

本文档用于说明：
- 如何拉取并运行本项目
- 如何在 GitHub 上协作开发
- 如何进行版本发布与打包

---

## 1. 仓库初始化

如果你是首次把项目推到自己的 GitHub 仓库，可参考：

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/你的用户名/ScrcpyGUI.git
git push -u origin master
```

> 若你的 GitHub 默认分支为 `main`，请按实际情况使用 `main`。

---

## 2. 拉取代码

```bash
git clone https://github.com/你的用户名/ScrcpyGUI.git
cd ScrcpyGUI
```

切换分支或标签：

```bash
git checkout 分支名或标签名
```

---

## 3. 本地运行环境准备

### 3.1 创建并激活虚拟环境

#### Windows系统

1. 创建虚拟环境：
```bash
python -m venv .venv
```

2. 激活虚拟环境：
```bash
.venv\Scripts\activate
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

4. 准备 scrcpy/adb（推荐）：
```bash
python setup_scrcpy.py
```

如已在系统 PATH 中安装 scrcpy/adb，或你准备在程序内手动指定路径，则此步骤可跳过。

#### Linux/macOS系统

1. 创建虚拟环境：
```bash
python3 -m venv .venv
```

2. 激活虚拟环境：
```bash
source .venv/bin/activate
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

4. 准备 scrcpy/adb（推荐）：
```bash
python setup_scrcpy.py
```

如已在系统 PATH 中安装 scrcpy/adb，或你准备在程序内手动指定路径，则此步骤可跳过。

---

## 4. 运行程序

Windows 下可直接：

```bash
start.bat
```

也可以通用方式运行：

```bash
python main.py
```

直接打开应用管理器：

```bash
python main.py --app-manager
```

---

## 5. 配置文件说明

### .gitignore

已配置忽略以下内容：
- Python缓存和编译文件 (`__pycache__/`, `*.pyc`)
- 构建和分发目录 (`build/`, `dist/`)
- 虚拟环境目录 (`.venv/`)
- IDE和编辑器配置文件
- 临时文件
- 日志文件

### 关键文件

核心文件包括：
- `main.py`: 程序主入口
- `runtime_helpers.py`: 环境路径解析、命令构建
- `scrcpy_controller.py`: ADB / scrcpy 调用控制器
- `app_manager.py`: 应用管理器
- `config_service.py`: 配置读写与设备参数保存
- `wifi_service.py`: WiFi 连接服务
- `screenshot_service.py`: 截图服务
- `utils.py`: 工具函数
- `create_icon.py`: 图标生成工具
- `ScrcpyGUI_separate.spec` / `ScrcpyGUI_onefile_separate.spec`: 打包配置
- `build_windows.py`: 打包脚本
- `setup_scrcpy.py`: 默认 scrcpy 环境下载脚本
- `requirements.txt`: 依赖项列表
- `scrcpy_config.json`: 配置文件
- `README.md`: 项目说明
- `使用说明文档.md`: 详细中文文档

---

## 6. 依赖环境策略说明

当前项目运行时依赖解析顺序：

**用户显式配置 > 本地/打包内置 > PATH > 常见安装目录 > fallback**

也就是说，协作开发时请优先遵循以下建议：

1. 开发者本地可以使用自己的 scrcpy 版本。
2. 如要保持测试一致，可运行 `setup_scrcpy.py` 使用默认基线版本。
3. 如要验证新版 scrcpy，可在程序菜单中手动指定路径。

---

## 7. 测试与运行

1. 确保已激活虚拟环境：
```bash
# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate
```

2. 运行：
```bash
python main.py
```

3. 基础校验：
```bash
python -m py_compile main.py
python .\main.py --version
```

---

## 8. 发布版本

发布建议流程：

1. 更新 `CHANGE_LOG.md`
2. 核对 `README.md` 和 `使用说明文档.md`
3. 使用打包脚本生成构建产物：
```bash
python build_windows.py --spec ScrcpyGUI_onefile_separate.spec
```
4. 如需 ZIP 包：

```bash
python build_windows.py --spec ScrcpyGUI_separate.spec --zip
```

5. 在 GitHub Releases 发布版本，并附带构建产物

---

## 9. 删除已提交但不需要的文件

如果某些文件已提交到仓库，但后来加入了 `.gitignore`，可以按如下方式处理：

1. 删除单个文件但保留本地副本：
```bash
git rm --cached <文件名>
```

2. 删除目录：
```bash
git rm --cached -r <目录名>
```

3. 提交：
```bash
git commit -m "从仓库中删除不需要的文件"
```

4. 推送：
```bash
git push origin master
```

5. 批量删除所有与 `.gitignore` 匹配但已跟踪的文件：
```bash
git rm --cached `git ls-files -i --exclude-from=.gitignore`
git commit -m "删除所有与.gitignore匹配的文件"
git push origin master
```

> 注意：上述方式只会从当前版本移除，不会清理历史提交中的文件。

---

## 10. 协作开发建议

1. 创建分支开发：
```bash
git checkout -b feature/new-feature
```

2. 提交代码：
```bash
git add .
git commit -m "添加新功能: xxx"
```

3. 推送并发起 PR：
```bash
git push origin feature/new-feature
``` 

4. 合并前建议至少完成：
- `python -m py_compile ...` 基础校验
- 文档同步更新
- 若改动到环境解析，验证“环境自检 / 一键诊断”输出
