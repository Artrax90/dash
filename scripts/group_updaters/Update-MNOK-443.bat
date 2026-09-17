@echo off
chcp 65001 >nul
title Обновление агентов: МНОК / 4 этаж / 443
echo ================================================================================
echo    WORKSTATION MANAGER - ОБНОВЛЕНИЕ АГЕНТОВ
echo    Группа: МНОК / 4 этаж / 443
echo    Токен:  wm_tok_8bd126283a901236
echo    ПК:     0 шт.
echo ================================================================================
echo.

set SCRIPT_DIR=%~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Update-MNOK-443.ps1" %*

echo.

pause >nul
