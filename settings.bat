@echo off
chcp 65001 >nul
title pro2input Settings
echo ============================================
echo  pro2input Settings Launcher
echo ============================================
echo.

python tools/settings_ui.py

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start settings GUI.
    echo   Please ensure Python and tkinter are installed.
    echo.
    pause
)
