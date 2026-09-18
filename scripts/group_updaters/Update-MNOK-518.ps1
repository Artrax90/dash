<#
.SYNOPSIS
    Workstation Manager - Обновление агентов группы "МНОК / 5 этаж / 518Т"
.DESCRIPTION
    Токен: wm_tok_071feaacce3b7ef1
    Компьютеров в группе: 14
    Учетные данные: admin / bmstu023
#>

param(
    [string]$ServerUrl = "http://172.19.33.68:2301",
    [pscredential]$Credential = $null,
    [switch]$LocalInstall,
    [switch]$PingOnly
)

$scriptDir = $PSScriptRoot
if (-not $scriptDir) { $scriptDir = "." }
$targetScript = Join-Path $scriptDir "Update-MNOK-518T.ps1"
if (Test-Path $targetScript) {
    & $targetScript -ServerUrl $ServerUrl -Credential $Credential -LocalInstall:$LocalInstall -PingOnly:$PingOnly
} else {
    Write-Error "Не найден файл Update-MNOK-518T.ps1!"
}
