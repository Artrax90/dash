@echo off
setlocal
chcp 65001 >nul
title Workstation Manager Agent Setup

:: Auto-elevate to Administrator with UAC prompt
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Запрос прав Администратора...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cls
echo ==============================================================================
echo       WORKSTATION MANAGER - АВТОМАТИЧЕСКИЙ УСТАНОВЩИК АГЕНТА (WINDOWS)        
echo ==============================================================================
echo.
echo [*] Запуск сценария установки и настройки Wake-on-LAN...
echo.

set "SCRIPT_DIR=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%standalone_installer.ps1"

echo.
echo ==============================================================================
echo [*] Установка завершена. Нажмите любую клавишу для выхода...
echo ==============================================================================
pause >nul
