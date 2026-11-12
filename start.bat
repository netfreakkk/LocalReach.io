@echo off
cd /d "%~dp0"
title LocalReach.io Studio
echo ========================================================
echo  LocalReach.io Studio - RTX 4050 Accelerated
echo ========================================================
echo.
.venv\Scripts\python.exe server.py
pause
