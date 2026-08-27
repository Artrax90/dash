@echo off
setlocal
title Workstation Manager Agent Setup

:: Auto-elevate to Administrator with UAC prompt
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Запрос прав Администратора...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
cls
echo ========================================================
echo   Workstation Manager - Установка и запуск службы v2.1.0
echo ========================================================
echo.

if exist "%~dp0standalone_installer.ps1" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0standalone_installer.ps1" -ServerUrl "http://192.168.1.109:2301" -Token "wm_tok_live_7f8a92b3c4d5e6f7"
    goto finish
)

echo [*] Загрузка актуального установщика v2.1.0 с сервера...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "[System.Net.ServicePointManager]::SecurityProtocol = 3072; (New-Object Net.WebClient).DownloadFile('http://192.168.1.109:2301/install.ps1', '%TEMP%\wm_install.ps1')"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\wm_install.ps1" -ServerUrl "http://192.168.1.109:2301" -Token "wm_tok_live_7f8a92b3c4d5e6f7"

:finish
echo.
echo ========================================================
echo   Готово. Системная служба успешно запущена в фоне.
echo ========================================================
timeout /t 5
