# GitHub配置说明

## 仓库设置

1. 在GitHub上创建新仓库
2. 初始化本地Git仓库:

```bash
git init
git add .
git commit -m "初始提交"
git remote add origin https://github.com/你的用户名/ScrcpyGUI.git
git push -u origin master
```

## 拉取代码和环境配置

### 拉取代码

1. 克隆仓库到本地:
```bash
git clone https://github.com/你的用户名/ScrcpyGUI.git
cd ScrcpyGUI
```

2. 如果您想切换到特定分支或标签:
```bash
git checkout 分支名/标签名
```

### 安装和激活虚拟环境

#### Windows系统

1. 安装虚拟环境:
```bash
python -m venv .venv
```

2. 激活虚拟环境:
```bash
.venv\Scripts\activate
```

3. 安装依赖:
```bash
pip install -r requirements.txt
```

#### Linux/macOS系统

1. 安装虚拟环境:
```bash
python3 -m venv .venv
```

2. 激活虚拟环境:
```bash
source .venv/bin/activate
```

3. 安装依赖:
```bash
pip install -r requirements.txt
```

### 运行程序

1. 使用批处理文件运行 (Windows):
```bash
start.bat
```

2. 或直接运行:
```bash
python main.py
```

## 配置文件说明

### .gitignore

已配置忽略以下文件和目录:
- Python缓存和编译文件 (`__pycache__/`, `*.pyc`)
- 构建和分发目录 (`build/`, `dist/`)
- 虚拟环境目录 (`.venv/`)
- IDE和编辑器配置文件
- 临时文件
- 日志文件

### 关键文件

保留的关键文件:
- `main.py`: 程序主入口
- `scrcpy_controller.py`: 控制器核心逻辑
- `app_manager.py`: 应用管理器
- `utils.py`: 工具函数
- `create_icon.py`: 图标生成工具
- `ScrcpyGUI_separate.spec`和`ScrcpyGUI_onefile_separate.spec`: 打包配置
- `build_windows.py`: 打包脚本
- `requirements.txt`: 依赖项列表
- `scrcpy_config.json`: 配置文件
- `README.md`: 项目说明
- `使用说明文档.md`: 详细中文文档

## 测试和运行

1. 确保已激活虚拟环境:
```bash
# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate
```

2. 使用批处理文件运行 (Windows):
```bash
start.bat
```

3. 或直接运行:
```bash
python main.py
```

## 发布版本

更新版本时:

1. 更新`CHANGE_LOG.md`文件
2. 使用打包脚本生成可执行文件:
```bash
python build_windows.py --spec ScrcpyGUI_onefile_separate.spec
```
3. 在GitHub上发布新版本，附上生成的可执行文件

## 删除已提交但不需要的文件

如果您已经提交了一些文件到仓库，后来在.gitignore中添加了这些文件，但它们仍然存在于仓库中，可以按照以下步骤删除它们:

1. 使用以下命令从仓库中删除文件但保留本地文件:
```bash
git rm --cached <文件名>
```

2. 对于目录，使用:
```bash
git rm --cached -r <目录名>
```

3. 删除后提交更改:
```bash
git commit -m "从仓库中删除不需要的文件"
```

4. 推送更改到远程仓库:
```bash
git push origin master
```

5. 如果有多个文件需要删除，可以使用以下命令批量处理与.gitignore匹配的所有文件:
```bash
git rm --cached `git ls-files -i --exclude-from=.gitignore`
git commit -m "删除所有与.gitignore匹配的文件"
git push origin master
```

注意: 使用这些命令后，文件将从Git历史记录中的最新版本中删除，但仍然存在于历史提交中。如果需要完全从Git历史中删除这些文件，需要使用更复杂的操作如`git filter-branch`或`BFG Repo-Cleaner`工具。

## 协作开发

1. 创建分支进行开发:
```bash
git checkout -b feature/new-feature
```

2. 提交更改:
```bash
git add .
git commit -m "添加新功能: xxx"
```

3. 推送分支并创建Pull Request:
```bash
git push origin feature/new-feature
``` 