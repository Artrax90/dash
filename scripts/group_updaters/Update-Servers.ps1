<#
.SYNOPSIS
    Workstation Manager - Обновление агентов группы "Servers"
.DESCRIPTION
    Токен: wm_tok_f3a5231cc51af30d
    Компьютеров в группе: 2
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

# 2. Вшитые учетные данные администратора для группы Servers
$EmbeddedUser = "admin"
$EmbeddedPass = "bmstu023"

if (-not $Credential) {
    $secPass = ConvertTo-SecureString $EmbeddedPass -AsPlainText -Force
    $Credential = New-Object System.Management.Automation.PSCredential($EmbeddedUser, $secPass)
}

$GroupName = "Servers"
$Token = "wm_tok_f3a5231cc51af30d"

$Devices = @(
    @{ IP = "192.168.0.237"; Name = "YEREMIN" },
    @{ IP = "192.168.0.233"; Name = "MEHANIZATOR1" }
)

Execute-GroupUpdate `
    -GroupName $GroupName `
    -Token $Token `
    -Devices $Devices `
    -ServerUrl $ServerUrl `
    -Credential $Credential `
    -LocalInstall:$LocalInstall `
    -PingOnly:$PingOnly
