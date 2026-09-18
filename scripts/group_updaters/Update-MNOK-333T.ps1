<#
.SYNOPSIS
    Workstation Manager - Обновление агентов группы "МНОК / 3 этаж / 333Т"
.DESCRIPTION
    Токен: wm_tok_662a7290c2bcec36
    Компьютеров в группе: 11
    Учетные данные: admin / oitp507
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

# 2. Вшитые учетные данные администратора для группы МНОК / 3 этаж / 333Т
$EmbeddedUser = "admin"
$EmbeddedPass = "oitp507"

if (-not $Credential) {
    $secPass = ConvertTo-SecureString $EmbeddedPass -AsPlainText -Force
    $Credential = New-Object System.Management.Automation.PSCredential($EmbeddedUser, $secPass)
}

$GroupName = "МНОК / 3 этаж / 333Т"
$Token = "wm_tok_662a7290c2bcec36"

$Devices = @(
    @{ IP = "172.16.248.87"; Name = "PC09-A2-CC333" },
    @{ IP = "172.16.219.31"; Name = "PC10-A2-CC333" },
    @{ IP = "172.16.40.195"; Name = "PC05-A2-CC333" },
    @{ IP = "172.16.40.229"; Name = "PC11-A2-CC333" },
    @{ IP = "172.16.42.111"; Name = "PC14-A2-CC333" },
    @{ IP = "172.16.43.89"; Name = "PC03-A2-CC333" },
    @{ IP = "172.16.42.6"; Name = "PC01-A2-CC333" },
    @{ IP = "172.16.43.253"; Name = "PC04-A2-CC333" },
    @{ IP = "172.16.42.50"; Name = "PC08-A2-CC333" },
    @{ IP = "172.16.43.103"; Name = "PC02-A2-CC333" },
    @{ IP = "172.16.42.180"; Name = "PC13-A2-CC333" }
)

Execute-GroupUpdate `
    -GroupName $GroupName `
    -Token $Token `
    -Devices $Devices `
    -ServerUrl $ServerUrl `
    -Credential $Credential `
    -LocalInstall:$LocalInstall `
    -PingOnly:$PingOnly
