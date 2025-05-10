@echo off
echo Starting Scrcpy GUI...
echo Using Python from virtual environment...

call .venv\Scripts\activate.bat
python main.py %*

if %errorlevel% neq 0 (
    echo Program exited with error code: %errorlevel%
    pause
) 