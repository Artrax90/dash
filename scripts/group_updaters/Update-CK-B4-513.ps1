<#
.SYNOPSIS
    Workstation Manager - Обновление агентов группы "ЦК B4 / 5 этаж / 513"
.DESCRIPTION
    Токен: wm_tok_a78863fc5308e95e
    Компьютеров в группе: 12
    Учетные данные: admin / bmstu023
#>

param(
    [string]$ServerUrl = "http://172.19.33.68:2301",
    [pscredential]$Credential = $null,
    [switch]$LocalInstall,
    [switch]$PingOnly
)

# 1. Загрузка общего движка обновления
$scriptDir = $PSScriptRoot
if (-not $scriptDir) { $scriptDir = "." }
$commonPath = Join-Path $scriptDir "Common-Updater.ps1"
if (Test-Path $commonPath) {
    . $commonPath
} else {
    Write-Error "Не найден файл Common-Updater.ps1 рядом со скриптом!"
    exit 1
}

# 2. Вшитые учетные данные администратора для группы ЦК B4 / 5 этаж / 513
$EmbeddedUser = "admin"
$EmbeddedPass = "bmstu023"

if (-not $Credential) {
    $secPass = ConvertTo-SecureString $EmbeddedPass -AsPlainText -Force
    $Credential = New-Object System.Management.Automation.PSCredential($EmbeddedUser, $secPass)
}

$GroupName = "ЦК B4 / 5 этаж / 513"
$Token = "wm_tok_a78863fc5308e95e"

$Devices = @(
    @{ IP = "172.16.45.14"; Name = "B4-513-01" },
    @{ IP = "172.16.47.196"; Name = "B4-513-28" },
    @{ IP = "172.16.47.121"; Name = "B4-513-09" },
    @{ IP = "172.16.47.117"; Name = "B4-513-05" },
    @{ IP = "172.16.47.49"; Name = "B4-513-02" },
    @{ IP = "172.16.44.232"; Name = "B4-513-07" },
    @{ IP = "172.16.45.63"; Name = "B4-513-22" },
    @{ IP = "172.16.47.95"; Name = "B4-513-03" },
    @{ IP = "10.81.237.53"; Name = "B4-513-06" },
    @{ IP = "172.16.46.159"; Name = "B4-513-17" },
    @{ IP = "172.16.47.111"; Name = "B4-513-04" },
    @{ IP = "172.16.47.129"; Name = "B4-513-16" }
)

Execute-GroupUpdate `
    -GroupName $GroupName `
    -Token $Token `
    -Devices $Devices `
    -ServerUrl $ServerUrl `
    -Credential $Credential `
    -LocalInstall:$LocalInstall `
    -PingOnly:$PingOnly
