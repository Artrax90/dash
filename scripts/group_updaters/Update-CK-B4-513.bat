@echo off
chcp 65001 >nul
title Обновление агентов: ЦК B4 / 5 этаж / 513 (admin)
echo ================================================================================
echo    WORKSTATION MANAGER - ОБНОВЛЕНИЕ АГЕНТОВ
echo    Группа: ЦК B4 / 5 этаж / 513
echo    Токен:  wm_tok_a78863fc5308e95e
echo    ПК:     12 шт.
echo    Логин:  admin (пароль вшит)
echo ================================================================================
echo.

set SCRIPT_DIR=%~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Update-CK-B4-513.ps1" %*

echo.
echo Нажмите любую клавишу для выхода...
pause >nul
