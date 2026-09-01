@echo off
title Real-Time Translator

if not exist .venv (
    echo [ERROR] Virtual environment not found.
    echo Please run 'install_windows.bat' first.
    pause
    exit /b
)

echo [Launcher] Activating environment...
call .venv\Scripts\activate.bat

echo [Launcher] Starting Realtime Subtitle...
python launcher.py
if %errorlevel% neq 0 (
    echo.
    echo [App Crashed or Exited]
    pause
)
