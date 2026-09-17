@echo off
chcp 65001 >nul
title Обновление агентов: Servers
echo ================================================================================
echo    WORKSTATION MANAGER - ОБНОВЛЕНИЕ АГЕНТОВ
echo    Группа: Servers
echo    Токен:  wm_tok_f3a5231cc51af30d
echo    ПК:     2 шт.
echo ================================================================================
echo.

set SCRIPT_DIR=%~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Update-Servers.ps1" %*

echo.
echo Нажмите любую клавишу для выхода...
pause >nul
