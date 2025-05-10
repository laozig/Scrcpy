@echo off
echo 正在启动应用管理器...
python "%~dp0main.py" --app-manager
if errorlevel 1 (
    echo 启动失败，错误代码: %errorlevel%
    pause
) 