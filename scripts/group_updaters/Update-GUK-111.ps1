<#
.SYNOPSIS
    Workstation Manager - Обновление агентов группы "ГУК / 1 этаж / 111"
.DESCRIPTION
    Токен: wm_tok_060f74580d9652d7
    Компьютеров в группе: 3
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

$GroupName = "ГУК / 1 этаж / 111"
$Token = "wm_tok_060f74580d9652d7"

$Devices = @(
    @{ IP = "192.168.0.238"; Name = "DESKTOP-E8566AH" },
    @{ IP = "192.168.0.203"; Name = "DESKTOP-J8IDHQH" },
    @{ IP = "192.168.0.210"; Name = "PC01-A1-UIITTP-" }
)

Execute-GroupUpdate `
    -GroupName $GroupName `
    -Token $Token `
    -Devices $Devices `
    -ServerUrl $ServerUrl `
    -Credential $Credential `
    -LocalInstall:$LocalInstall `
    -PingOnly:$PingOnly
