@echo off
chcp 65001 >nul
title Обновление агентов: МНОК / 1 этаж / 111
echo ================================================================================
echo    WORKSTATION MANAGER - ОБНОВЛЕНИЕ АГЕНТОВ
echo    Группа: МНОК / 1 этаж / 111
echo    Токен:  wm_tok_06791590421adcf6
echo    ПК:     0 шт.
echo ================================================================================
echo.

set SCRIPT_DIR=%~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Update-MNOK-111.ps1" %*

echo.
echo Нажмите любую клавишу для выхода...
pause >nul
