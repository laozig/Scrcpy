# 贡献指南

感谢您考虑为 Scrcpy GUI 项目做出贡献！以下是参与项目开发的指南。

## 开发环境设置

1. Fork 本仓库
2. 克隆你的 Fork 版本
```bash
git clone https://github.com/YOUR_USERNAME/scrcpy-gui.git
cd scrcpy-gui
```
3. 设置上游仓库
```bash
git remote add upstream https://github.com/ORIGINAL_OWNER/scrcpy-gui.git
```
4. 安装依赖
```bash
pip install -r requirements.txt
```

## 提交更改

1. 创建新的分支以进行功能开发或错误修复
```bash
git checkout -b feature/your-feature-name
# 或
git checkout -b fix/issue-description
```

2. 进行代码更改，遵循以下规范：
   - 遵循现有代码风格
   - 为新功能编写清晰的文档
   - 确保代码可以正常运行

3. 提交您的更改：
```bash
git add .
git commit -m "清晰描述您的更改"
```

4. 推送到您的 Fork 仓库：
```bash
git push origin feature/your-feature-name
```

5. 提交 Pull Request：
   - 在 GitHub 上打开您的 Fork 仓库
   - 点击 "Compare & pull request"
   - 提供清晰的描述和说明

## 代码规范

1. **Python 编码风格**
   - 遵循 PEP 8 规范
   - 使用 4 空格缩进
   - 行长度不超过 100 个字符
   - 类名使用 CamelCase，方法和变量使用 snake_case
   - 添加有意义的注释，特别是对于复杂逻辑

2. **提交规范**
   - 每个提交解决一个特定问题
   - 提交消息应清晰地描述更改内容
   - 提交消息格式建议：`类型: 简短描述`
     - 类型可以是: feat, fix, docs, style, refactor, test, chore 等

3. **文档规范**
   - 为新功能添加文档
   - 更新 README.md 以反映重要变更
   - 中文文档使用简体中文

## 功能开发指南

1. **新功能提议**
   - 首先创建一个 Issue 讨论新功能
   - 说明新功能的用途和实现思路
   - 等待社区反馈后再开始开发

2. **功能实现建议**
   - 保持代码模块化，使用 MVC 模式
   - GUI 组件放在 main.py 或专门的 UI 模块中
   - 设备交互逻辑放在 controller 模块中
   - 通用工具函数放在 utils.py 中

3. **测试**
   - 在提交前测试您的代码
   - 确保在不同环境下功能正常
   - 考虑各种边缘情况

## 报告问题

如果您发现问题但不打算自己修复，请创建新的 Issue：

1. 清晰描述问题
2. 提供重现步骤
3. 附上错误信息或截图
4. 说明您的操作系统和 Python 版本

## 许可证

通过提交代码，您同意您的贡献将在本项目的 GPL-3.0 许可证下发布。