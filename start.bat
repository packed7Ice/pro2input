@echo off
chcp 65001 >nul
title pro2input - Switch 2 Pro Controller to XInput Converter
echo ============================================
echo  pro2input Launcher
echo ============================================
echo.
echo  [INFO] Starting Switch 2 Pro Controller converter...
echo  [INFO] Press Ctrl+C to stop.
echo.

python main.py

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start. Please check:
    echo   1. Python is installed and in PATH
    echo   2. pyusb and vgamepad are installed (pip install pyusb vgamepad)
    echo   3. The controller is connected via USB
    echo   4. libusbK driver is installed for Interface 1 (Zadig)
    echo.
    pause
)
