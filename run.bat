@echo off
echo 正在启动Scrcpy GUI...
echo 使用虚拟环境中的Python...

call .venv\Scripts\activate.bat
python main.py %*

if %errorlevel% neq 0 (
    echo 程序异常退出，错误码: %errorlevel%
    pause
) 