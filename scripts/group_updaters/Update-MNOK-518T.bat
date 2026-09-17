@echo off
chcp 65001 >nul
title Обновление агентов: МНОК / 5 этаж / 518Т
echo ================================================================================
echo    WORKSTATION MANAGER - ОБНОВЛЕНИЕ АГЕНТОВ
echo    Группа: МНОК / 5 этаж / 518Т
echo    Токен:  wm_tok_071feaacce3b7ef1
echo    ПК:     14 шт.
echo ================================================================================
echo.

set SCRIPT_DIR=%~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Update-MNOK-518T.ps1" %*

echo.

pause >nul
