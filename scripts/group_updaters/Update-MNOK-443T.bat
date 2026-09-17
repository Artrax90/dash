@echo off
chcp 65001 >nul
title Обновление агентов: МНОК / 4 этаж / 443Т
echo ================================================================================
echo    WORKSTATION MANAGER - ОБНОВЛЕНИЕ АГЕНТОВ
echo    Группа: МНОК / 4 этаж / 443Т
echo    Токен:  wm_tok_84b4480be512b7db
echo    ПК:     3 шт.
echo ================================================================================
echo.

set SCRIPT_DIR=%~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Update-MNOK-443T.ps1" %*

echo.

pause >nul
