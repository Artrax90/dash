@echo off
chcp 65001 >nul
title Обновление агентов: ЦК B4 / 5 этаж / 541
echo ================================================================================
echo    WORKSTATION MANAGER - ОБНОВЛЕНИЕ АГЕНТОВ
echo    Группа: ЦК B4 / 5 этаж / 541
echo    Токен:  wm_tok_4470ec159a499f5f
echo    ПК:     2 шт.
echo ================================================================================
echo.

set SCRIPT_DIR=%~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Update-CK-B4-541.ps1" %*

echo.
echo Нажмите любую клавишу для выхода...
pause >nul
