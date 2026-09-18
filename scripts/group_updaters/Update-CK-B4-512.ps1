<#
.SYNOPSIS
    Workstation Manager - Обновление агентов группы "ЦК B4 / 5 этаж / 512"
.DESCRIPTION
    Токен: wm_tok_2d20a75eef21e61d
    Компьютеров в группе: 5
    Учетные данные: admin / bmstu023
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

# 2. Вшитые учетные данные администратора для группы ЦК B4 / 5 этаж / 512
$EmbeddedUser = "admin"
$EmbeddedPass = "bmstu023"

if (-not $Credential) {
    $secPass = ConvertTo-SecureString $EmbeddedPass -AsPlainText -Force
    $Credential = New-Object System.Management.Automation.PSCredential($EmbeddedUser, $secPass)
}

$GroupName = "ЦК B4 / 5 этаж / 512"
$Token = "wm_tok_2d20a75eef21e61d"

$Devices = @(
    @{ IP = "172.16.223.145"; Name = "B4-512-15" },
    @{ IP = "172.16.221.6"; Name = "B4-512-18" },
    @{ IP = "172.16.45.217"; Name = "B4-512-01" },
    @{ IP = "172.16.47.143"; Name = "B4-512-17" },
    @{ IP = "172.16.46.58"; Name = "B4-512-28" }
)

Execute-GroupUpdate `
    -GroupName $GroupName `
    -Token $Token `
    -Devices $Devices `
    -ServerUrl $ServerUrl `
    -Credential $Credential `
    -LocalInstall:$LocalInstall `
    -PingOnly:$PingOnly
