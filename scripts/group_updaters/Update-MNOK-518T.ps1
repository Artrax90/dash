<#
.SYNOPSIS
    Workstation Manager - Обновление агентов группы "МНОК / 5 этаж / 518Т"
.DESCRIPTION
    Токен: wm_tok_071feaacce3b7ef1
    Компьютеров в группе: 14
    Учетные данные: admin / oitp507
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

# 2. Вшитые учетные данные администратора для группы МНОК / 5 этаж / 518Т
$EmbeddedUser = "admin"
$EmbeddedPass = "oitp507"

if (-not $Credential) {
    $secPass = ConvertTo-SecureString $EmbeddedPass -AsPlainText -Force
    $Credential = New-Object System.Management.Automation.PSCredential($EmbeddedUser, $secPass)
}

$GroupName = "МНОК / 5 этаж / 518Т"
$Token = "wm_tok_071feaacce3b7ef1"

$Devices = @(
    @{ IP = "172.16.43.88"; Name = "PC15-A2-CC518" },
    @{ IP = "172.16.42.75"; Name = "PC07-A2-CC518" },
    @{ IP = "172.16.42.0"; Name = "PC09-A2-CC518" },
    @{ IP = "172.16.41.80"; Name = "PC11-A2-CC518" },
    @{ IP = "172.16.41.34"; Name = "PC06-A2-CC518" },
    @{ IP = "172.16.40.233"; Name = "PC02-A2-CC518" },
    @{ IP = "172.16.42.239"; Name = "PC05-A2-CC518" },
    @{ IP = "172.16.42.73"; Name = "PC12-A2-CC518" },
    @{ IP = "172.16.42.3"; Name = "PC01-A2-CC518" },
    @{ IP = "172.16.42.72"; Name = "PC17-A2-CC518" },
    @{ IP = "172.16.43.38"; Name = "PC12-A2-CC333" },
    @{ IP = "172.16.245.185"; Name = "PC04-A2-CC518" },
    @{ IP = "172.16.42.1"; Name = "PC14-A2-CC518" },
    @{ IP = "172.16.242.216"; Name = "PC13-A2-CC518" }
)

Execute-GroupUpdate `
    -GroupName $GroupName `
    -Token $Token `
    -Devices $Devices `
    -ServerUrl $ServerUrl `
    -Credential $Credential `
    -LocalInstall:$LocalInstall `
    -PingOnly:$PingOnly
