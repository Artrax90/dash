@echo off
chcp 65001 >nul
title Обновление агентов: МНОК / 4 этаж / 444Т
echo ================================================================================
echo    WORKSTATION MANAGER - ОБНОВЛЕНИЕ АГЕНТОВ
echo    Группа: МНОК / 4 этаж / 444Т
echo    Токен:  wm_tok_c85c6b07cd5e5c3d
echo    ПК:     9 шт.
echo ================================================================================
echo.

set SCRIPT_DIR=%~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Update-MNOK-444T.ps1" %*

echo.

pause >nul
