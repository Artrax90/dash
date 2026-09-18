@echo off
chcp 65001 >nul
title Обновление агентов: МНОК / 5 этаж / 518Т
set SCRIPT_DIR=%~dp0
call "%SCRIPT_DIR%Update-MNOK-518T.bat" %*
