@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found on this computer.
    echo Install it from https://www.python.org/downloads/ ^(check "Add python.exe to PATH" during setup^), then run this file again.
    pause
    exit /b 1
)

if not exist venv (
    echo First run - setting things up, this takes a minute...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install --upgrade pip >nul
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

echo.
echo Starting Wire...
echo Your browser will open automatically. Close this window to stop the app.
echo.
python app.py

if errorlevel 1 (
    echo.
    echo Wire exited with an error - see above for details.
    pause
)
