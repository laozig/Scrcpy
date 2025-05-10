@echo off
echo 正在启动应用管理器...

:: 检查是否存在exe版本
if exist "%~dp0ScrcpyGUI.exe" (
    start "" "%~dp0ScrcpyGUI.exe" --app-manager
) else (
    :: 尝试使用Python启动
    python "%~dp0main.py" --app-manager
    if errorlevel 1 (
        echo 启动失败，错误代码: %errorlevel%
        echo 请确保已安装Python并正确配置PATH环境变量。
        pause
    )
) 