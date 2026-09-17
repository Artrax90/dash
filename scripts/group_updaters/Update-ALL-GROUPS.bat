@echo off
chcp 65001 >nul
title Workstation Manager - Пульт обновления групп агентов

set SCRIPT_DIR=%~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Update-ALL-GROUPS.ps1" %*

echo.
echo Нажмите любую клавишу для выхода...
pause >nul
