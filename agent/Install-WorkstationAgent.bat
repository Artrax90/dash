@echo off
setlocal
chcp 65001 >nul
title Workstation Manager Agent Setup

:: Auto-elevate to Administrator with UAC prompt
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Запрос прав Администратора...
    powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
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
    powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File "%SCRIPT_DIR%standalone_installer.ps1"
) else (
    powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $dst = [IO.Path]::Combine($env:TEMP, 'Install-WorkstationAgent.ps1'); (New-Object Net.WebClient).DownloadFile('http://192.168.1.109:2301/install.ps1?token=wm_tok_live_7f8a92b3c4d5e6f7', $dst); $bytes = [IO.File]::ReadAllBytes($dst); if ($bytes.Length -ge 3 -and ($bytes[0] -ne 0xEF -or $bytes[1] -ne 0xBB -or $bytes[2] -ne 0xBF)) { [IO.File]::WriteAllBytes($dst, ([byte[]](0xEF, 0xBB, 0xBF) + $bytes)) }; & powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File $dst; Remove-Item $dst -Force -ErrorAction SilentlyContinue"
)

echo.
echo ==============================================================================
echo [*] Установка завершена. Нажмите любую клавишу для выхода...
echo ==============================================================================
pause >nul
