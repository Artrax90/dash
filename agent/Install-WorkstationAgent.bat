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

set "TARGET_SERVER=%~1"
set "SCRIPT_DIR=%~dp0"
if exist "%SCRIPT_DIR%standalone_installer.ps1" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$p = Join-Path '%SCRIPT_DIR%' 'standalone_installer.ps1'; $b = [IO.File]::ReadAllBytes($p); if ($b.Length -ge 3 -and ($b[0] -ne 0xEF -or $b[1] -ne 0xBB -or $b[2] -ne 0xBF)) { [IO.File]::WriteAllBytes($p, ([byte[]](0xEF, 0xBB, 0xBF) + $b)) }; & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $p %*"
) else (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $dst = [IO.Path]::Combine($env:TEMP, 'Install-WorkstationAgent.ps1'); $wc = New-Object Net.WebClient; $wc.Proxy = $null; $srv = '%TARGET_SERVER%'; $dlOk = $false; $cands = @($srv); $gw = (Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty NextHop -First 1); if ($gw) { $cands += \"http://${gw}:2301\" }; $cands += @('http://192.168.1.109:2301', 'http://172.19.33.68:2301'); foreach ($cand in $cands) { if ($cand) { try { $wc.DownloadFile(\"$cand/install.ps1?token=wm_tok_live_7f8a92b3c4d5e6f7&download=1\", $dst); $srv = $cand; $dlOk = $true; break } catch {} } }; if (-not $dlOk) { Write-Host '[!] Ошибка: Не удалось скачать установщик агента с сервера.' -ForegroundColor Red; exit 1 }; $bytes = [IO.File]::ReadAllBytes($dst); if ($bytes.Length -ge 3 -and ($bytes[0] -ne 0xEF -or $bytes[1] -ne 0xBB -or $bytes[2] -ne 0xBF)) { [IO.File]::WriteAllBytes($dst, ([byte[]](0xEF, 0xBB, 0xBF) + $bytes)) }; & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $dst -ServerUrl $srv %*; Remove-Item $dst -Force -ErrorAction SilentlyContinue"
)

echo.
echo ==============================================================================
echo [*] Установка завершена. Нажмите любую клавишу для выхода...
echo ==============================================================================
pause >nul
