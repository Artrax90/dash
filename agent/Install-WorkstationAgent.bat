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
if exist "%SCRIPT_DIR%standalone_installer.ps1" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%standalone_installer.ps1"
) else (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12; $ProgressPreference = 'SilentlyContinue'; [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $wc = New-Object System.Net.WebClient; $wc.Encoding = [System.Text.Encoding]::UTF8; iex $wc.DownloadString('http://192.168.1.109:2301/install.ps1?token=wm_tok_live_7f8a92b3c4d5e6f7')"
)

echo.
echo ==============================================================================
echo [*] Установка завершена. Нажмите любую клавишу для выхода...
echo ==============================================================================
pause >nul
