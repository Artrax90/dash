@echo off
chcp 65001 >nul
title Обновление агентов: МНОК / 4 этаж / 444
echo ================================================================================
echo    WORKSTATION MANAGER - ОБНОВЛЕНИЕ АГЕНТОВ
echo    Группа: МНОК / 4 этаж / 444
echo    Токен:  wm_tok_9dae52edee48d1b6
echo    ПК:     0 шт.
echo ================================================================================
echo.

set SCRIPT_DIR=%~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Update-MNOK-444.ps1" %*

echo.
echo Нажмите любую клавишу для выхода...
pause >nul
