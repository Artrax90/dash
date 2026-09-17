<#
.SYNOPSIS
    Workstation Manager - Обновление агентов группы "МНОК / 4 этаж / 444Т"
.DESCRIPTION
    Токен: wm_tok_c85c6b07cd5e5c3d
    Компьютеров в группе: 9
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

$GroupName = "МНОК / 4 этаж / 444Т"
$Token = "wm_tok_c85c6b07cd5e5c3d"

$Devices = @(
    @{ IP = "172.16.220.32"; Name = "PC12-A2-CC444" },
    @{ IP = "172.16.42.92"; Name = "PC11-A2-CC444" },
    @{ IP = "172.16.42.39"; Name = "PC13-A2-CC444" },
    @{ IP = "172.16.100.101"; Name = "PC02-A2-CC444" },
    @{ IP = "172.16.42.74"; Name = "PC09-A2-CC444" },
    @{ IP = "172.16.43.126"; Name = "PC06-A2-CC444" },
    @{ IP = "10.21.78.248"; Name = "PC08-A2-CC444" },
    @{ IP = "172.16.41.95"; Name = "PC04-A2-CC444" },
    @{ IP = "172.16.40.225"; Name = "PC05-A2-CC444" }
)

Execute-GroupUpdate `
    -GroupName $GroupName `
    -Token $Token `
    -Devices $Devices `
    -ServerUrl $ServerUrl `
    -Credential $Credential `
    -LocalInstall:$LocalInstall `
    -PingOnly:$PingOnly
