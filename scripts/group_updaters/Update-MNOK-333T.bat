@echo off
chcp 65001 >nul
title Обновление агентов: МНОК / 3 этаж / 333Т
echo ================================================================================
echo    WORKSTATION MANAGER - ОБНОВЛЕНИЕ АГЕНТОВ
echo    Группа: МНОК / 3 этаж / 333Т
echo    Токен:  wm_tok_662a7290c2bcec36
echo    ПК:     11 шт.
echo ================================================================================
echo.

set SCRIPT_DIR=%~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Update-MNOK-333T.ps1" %*

echo.
echo Нажмите любую клавишу для выхода...
pause >nul
