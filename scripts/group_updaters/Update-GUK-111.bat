@echo off
chcp 65001 >nul
title Обновление агентов: ГУК / 1 этаж / 111
echo ================================================================================
echo    WORKSTATION MANAGER - ОБНОВЛЕНИЕ АГЕНТОВ
echo    Группа: ГУК / 1 этаж / 111
echo    Токен:  wm_tok_060f74580d9652d7
echo    ПК:     3 шт.
echo    Логин:  admin (пароль вшит)
echo ================================================================================
echo.

set SCRIPT_DIR=%~dp0

:: Если переданы аргументы командной строки (например -LocalInstall или -PingOnly)
if not "%~1"=="" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Update-GUK-111.ps1" %*
    goto :done
)

echo Выберите режим работы:
echo   [1] Удаленное обновление всех 3 станций кабинета (по сети)
echo   [2] Локальная установка на ЭТОМ компьютере (если запустили через RDP)
echo   [3] Только проверка связи (Ping Only)
echo.
set "MODE=1"
set /p "MODE=Ваш выбор [1, 2, 3] (по умолчанию 1): "

if "%MODE%"=="2" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Update-GUK-111.ps1" -LocalInstall
) else if "%MODE%"=="3" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Update-GUK-111.ps1" -PingOnly
) else (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Update-GUK-111.ps1"
)

:done
echo.
echo ================================================================================
echo Работа скрипта завершена. Нажмите любую клавишу для закрытия...
echo ================================================================================
pause >nul
