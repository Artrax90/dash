<#
.SYNOPSIS
    Workstation Manager - Обновление агентов группы "МНОК / 4 этаж / 443Т"
.DESCRIPTION
    Токен: wm_tok_84b4480be512b7db
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

$GroupName = "МНОК / 4 этаж / 443Т"
$Token = "wm_tok_84b4480be512b7db"

$Devices = @(
    @{ IP = "172.16.255.114"; Name = "PC04-A2-CC443" },
    @{ IP = "172.16.40.248"; Name = "PC14-A2-CC443" },
    @{ IP = "172.16.241.73"; Name = "PC11-A2-CC443" }
)

Execute-GroupUpdate `
    -GroupName $GroupName `
    -Token $Token `
    -Devices $Devices `
    -ServerUrl $ServerUrl `
    -Credential $Credential `
    -LocalInstall:$LocalInstall `
    -PingOnly:$PingOnly
