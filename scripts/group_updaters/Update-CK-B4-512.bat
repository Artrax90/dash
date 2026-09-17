@echo off
chcp 65001 >nul
title Обновление агентов: ЦК B4 / 5 этаж / 512
echo ================================================================================
echo    WORKSTATION MANAGER - ОБНОВЛЕНИЕ АГЕНТОВ
echo    Группа: ЦК B4 / 5 этаж / 512
echo    Токен:  wm_tok_2d20a75eef21e61d
echo    ПК:     5 шт.
echo ================================================================================
echo.

set SCRIPT_DIR=%~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Update-CK-B4-512.ps1" %*

echo.
echo Нажмите любую клавишу для выхода...
pause >nul
