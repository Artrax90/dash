@echo off
chcp 65001 >nul
title Обновление агентов: МНОК / 4 этаж / 446Т
echo ================================================================================
echo    WORKSTATION MANAGER - ОБНОВЛЕНИЕ АГЕНТОВ
echo    Группа: МНОК / 4 этаж / 446Т
echo    Токен:  wm_tok_8be3647c50f0d095
echo    ПК:     0 шт.
echo ================================================================================
echo.

set SCRIPT_DIR=%~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Update-MNOK-446T.ps1" %*

echo.
echo Нажмите любую клавишу для выхода...
pause >nul
