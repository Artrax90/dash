<#
.SYNOPSIS
    Workstation Manager - Обновление агентов группы "ЦК B4 / 5 этаж / 541"
.DESCRIPTION
    Токен: wm_tok_4470ec159a499f5f
    Компьютеров в группе: 2
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

$GroupName = "ЦК B4 / 5 этаж / 541"
$Token = "wm_tok_4470ec159a499f5f"

$Devices = @(
    @{ IP = "172.16.110.207"; Name = "B4-541-01" },
    @{ IP = "172.16.44.128"; Name = "B4-541-02" }
)

Execute-GroupUpdate `
    -GroupName $GroupName `
    -Token $Token `
    -Devices $Devices `
    -ServerUrl $ServerUrl `
    -Credential $Credential `
    -LocalInstall:$LocalInstall `
    -PingOnly:$PingOnly
