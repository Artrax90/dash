<#
.SYNOPSIS
    Workstation Manager - Обновление агентов группы "МНОК / 1 этаж / 111"
.DESCRIPTION
    Токен: wm_tok_06791590421adcf6
    Компьютеров в группе: 0
#>

param(
    [string]$ServerUrl = "http://172.19.33.68:2301",
    [pscredential]$Credential = $null,
    [switch]$LocalInstall,
    [switch]$PingOnly
)

# Загрузка общего движка обновления
$scriptDir = $PSScriptRoot
if (-not $scriptDir) { $scriptDir = "." }
$commonPath = Join-Path $scriptDir "Common-Updater.ps1"
if (Test-Path $commonPath) {
    . $commonPath
} else {
    Write-Error "Не найден файл Common-Updater.ps1 рядом со скриптом!"
    exit 1
}

$GroupName = "МНОК / 1 этаж / 111"
$Token = "wm_tok_06791590421adcf6"

$Devices = @(

)

Execute-GroupUpdate `
    -GroupName $GroupName `
    -Token $Token `
    -Devices $Devices `
    -ServerUrl $ServerUrl `
    -Credential $Credential `
    -LocalInstall:$LocalInstall `
    -PingOnly:$PingOnly
