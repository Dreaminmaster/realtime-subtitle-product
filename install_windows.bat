@echo off
title Realtime Subtitle - developer setup
echo This script is only for running from source.
echo End users should install the Windows setup EXE from GitHub Releases.
where py >nul 2>&1 || (echo Python 3.10+ is required for source development.& pause & exit /b 1)
if not exist .venv py -3 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo Setup complete. System audio uses native WASAPI loopback; VB-CABLE is not required.
pause
