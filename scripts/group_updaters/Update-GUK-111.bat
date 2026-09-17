@echo off
chcp 65001 >nul
title Обновление агентов: ГУК / 1 этаж / 111
echo ================================================================================
echo    WORKSTATION MANAGER - ОБНОВЛЕНИЕ АГЕНТОВ
echo    Группа: ГУК / 1 этаж / 111
echo    Токен:  wm_tok_060f74580d9652d7
echo    ПК:     3 шт.
echo ================================================================================
echo.

set SCRIPT_DIR=%~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Update-GUK-111.ps1" %*

echo.
echo Нажмите любую клавишу для выхода...
pause >nul
