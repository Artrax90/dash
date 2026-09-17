<#
.SYNOPSIS
    Workstation Manager - Главный интерактивный пульт обновления агентов по группам
.DESCRIPTION
    Позволяет обновить любую выбранную группу или весь парк рабочих станций сразу.
#>

param(
    [string]$ServerUrl = "http://172.19.33.68:2301",
    [pscredential]$Credential = $null,
    [switch]$All,
    [switch]$PingOnly
)

$scriptDir = $PSScriptRoot
if (-not $scriptDir) { $scriptDir = "." }
$commonPath = Join-Path $scriptDir "Common-Updater.ps1"
if (Test-Path $commonPath) {
    . $commonPath
} else {
    Write-Error "Не найден файл Common-Updater.ps1 рядом со скриптом!"
    exit 1
}

# Реестр всех групп, токенов и компьютеров
$AllGroups = @(
    [PSCustomObject]@{
        Id = "GUK-111"
        Name = "ГУК / 1 этаж / 111"
        Token = "wm_tok_060f74580d9652d7"
        Script = "Update-GUK-111.ps1"
        Devices = @(
            @{ IP = "192.168.0.238"; Name = "DESKTOP-E8566AH" },
            @{ IP = "192.168.0.203"; Name = "DESKTOP-J8IDHQH" },
            @{ IP = "192.168.0.210"; Name = "PC01-A1-UIITTP-" }
        )
    },
    [PSCustomObject]@{
        Id = "MNOK-333T"
        Name = "МНОК / 3 этаж / 333Т"
        Token = "wm_tok_662a7290c2bcec36"
        Script = "Update-MNOK-333T.ps1"
        Devices = @(
            @{ IP = "172.16.248.87"; Name = "PC09-A2-CC333" },
            @{ IP = "172.16.219.31"; Name = "PC10-A2-CC333" },
            @{ IP = "172.16.40.195"; Name = "PC05-A2-CC333" },
            @{ IP = "172.16.40.229"; Name = "PC11-A2-CC333" },
            @{ IP = "172.16.42.111"; Name = "PC14-A2-CC333" },
            @{ IP = "172.16.43.89";  Name = "PC03-A2-CC333" },
            @{ IP = "172.16.42.6";   Name = "PC01-A2-CC333" },
            @{ IP = "172.16.43.253"; Name = "PC04-A2-CC333" },
            @{ IP = "172.16.42.50";  Name = "PC08-A2-CC333" },
            @{ IP = "172.16.43.103"; Name = "PC02-A2-CC333" },
            @{ IP = "172.16.42.180"; Name = "PC13-A2-CC333" }
        )
    },
    [PSCustomObject]@{
        Id = "MNOK-443T"
        Name = "МНОК / 4 этаж / 443Т"
        Token = "wm_tok_84b4480be512b7db"
        Script = "Update-MNOK-443T.ps1"
        Devices = @(
            @{ IP = "172.16.255.114"; Name = "PC04-A2-CC443" },
            @{ IP = "172.16.40.248";  Name = "PC14-A2-CC443" },
            @{ IP = "172.16.241.73";  Name = "PC11-A2-CC443" }
        )
    },
    [PSCustomObject]@{
        Id = "MNOK-444T"
        Name = "МНОК / 4 этаж / 444Т"
        Token = "wm_tok_c85c6b07cd5e5c3d"
        Script = "Update-MNOK-444T.ps1"
        Devices = @(
            @{ IP = "172.16.220.32";  Name = "PC12-A2-CC444" },
            @{ IP = "172.16.42.92";   Name = "PC11-A2-CC444" },
            @{ IP = "172.16.42.39";   Name = "PC13-A2-CC444" },
            @{ IP = "172.16.100.101"; Name = "PC02-A2-CC444" },
            @{ IP = "172.16.42.74";   Name = "PC09-A2-CC444" },
            @{ IP = "172.16.43.126";  Name = "PC06-A2-CC444" },
            @{ IP = "10.21.78.248";   Name = "PC08-A2-CC444" },
            @{ IP = "172.16.41.95";   Name = "PC04-A2-CC444" },
            @{ IP = "172.16.40.225";  Name = "PC05-A2-CC444" }
        )
    },
    [PSCustomObject]@{
        Id = "MNOK-518T"
        Name = "МНОК / 5 этаж / 518Т"
        Token = "wm_tok_071feaacce3b7ef1"
        Script = "Update-MNOK-518T.ps1"
        Devices = @(
            @{ IP = "172.16.43.88";   Name = "PC15-A2-CC518" },
            @{ IP = "172.16.42.75";   Name = "PC07-A2-CC518" },
            @{ IP = "172.16.42.0";    Name = "PC09-A2-CC518" },
            @{ IP = "172.16.41.80";   Name = "PC11-A2-CC518" },
            @{ IP = "172.16.41.34";   Name = "PC06-A2-CC518" },
            @{ IP = "172.16.40.233";  Name = "PC02-A2-CC518" },
            @{ IP = "172.16.42.239";  Name = "PC05-A2-CC518" },
            @{ IP = "172.16.42.73";   Name = "PC12-A2-CC518" },
            @{ IP = "172.16.42.3";    Name = "PC01-A2-CC518" },
            @{ IP = "172.16.42.72";   Name = "PC17-A2-CC518" },
            @{ IP = "172.16.43.38";   Name = "PC12-A2-CC333" },
            @{ IP = "172.16.245.185"; Name = "PC04-A2-CC518" },
            @{ IP = "172.16.42.1";    Name = "PC14-A2-CC518" },
            @{ IP = "172.16.242.216"; Name = "PC13-A2-CC518" }
        )
    },
    [PSCustomObject]@{
        Id = "CK-B4-512"
        Name = "ЦК B4 / 5 этаж / 512"
        Token = "wm_tok_2d20a75eef21e61d"
        Script = "Update-CK-B4-512.ps1"
        Devices = @(
            @{ IP = "172.16.223.145"; Name = "B4-512-15" },
            @{ IP = "172.16.221.6";   Name = "B4-512-18" },
            @{ IP = "172.16.45.217";  Name = "B4-512-01" },
            @{ IP = "172.16.47.143";  Name = "B4-512-17" },
            @{ IP = "172.16.46.58";   Name = "B4-512-28" }
        )
    },
    [PSCustomObject]@{
        Id = "CK-B4-513"
        Name = "ЦК B4 / 5 этаж / 513"
        Token = "wm_tok_a78863fc5308e95e"
        Script = "Update-CK-B4-513.ps1"
        Devices = @(
            @{ IP = "172.16.45.14";   Name = "B4-513-01" },
            @{ IP = "172.16.47.196";  Name = "B4-513-28" },
            @{ IP = "172.16.47.121";  Name = "B4-513-09" },
            @{ IP = "172.16.47.117";  Name = "B4-513-05" },
            @{ IP = "172.16.47.49";   Name = "B4-513-02" },
            @{ IP = "172.16.44.232";  Name = "B4-513-07" },
            @{ IP = "172.16.45.63";   Name = "B4-513-22" },
            @{ IP = "172.16.47.95";   Name = "B4-513-03" },
            @{ IP = "10.81.237.53";   Name = "B4-513-06" },
            @{ IP = "172.16.46.159";  Name = "B4-513-17" },
            @{ IP = "172.16.47.111";  Name = "B4-513-04" },
            @{ IP = "172.16.47.129";  Name = "B4-513-16" }
        )
    },
    [PSCustomObject]@{
        Id = "CK-B4-541"
        Name = "ЦК B4 / 5 этаж / 541"
        Token = "wm_tok_4470ec159a499f5f"
        Script = "Update-CK-B4-541.ps1"
        Devices = @(
            @{ IP = "172.16.110.207"; Name = "B4-541-01" },
            @{ IP = "172.16.44.128";  Name = "B4-541-02" }
        )
    },
    [PSCustomObject]@{
        Id = "Servers"
        Name = "Servers"
        Token = "wm_tok_f3a5231cc51af30d"
        Script = "Update-Servers.ps1"
        Devices = @(
            @{ IP = "192.168.0.237"; Name = "YEREMIN" },
            @{ IP = "192.168.0.233"; Name = "MEHANIZATOR1" }
        )
    },
    [PSCustomObject]@{
        Id = "MNOK-443"
        Name = "МНОК / 4 этаж / 443"
        Token = "wm_tok_8bd126283a901236"
        Script = "Update-MNOK-443.ps1"
        Devices = @()
    },
    [PSCustomObject]@{
        Id = "MNOK-444"
        Name = "МНОК / 4 этаж / 444"
        Token = "wm_tok_9dae52edee48d1b6"
        Script = "Update-MNOK-444.ps1"
        Devices = @()
    },
    [PSCustomObject]@{
        Id = "MNOK-446T"
        Name = "МНОК / 4 этаж / 446Т"
        Token = "wm_tok_8be3647c50f0d095"
        Script = "Update-MNOK-446T.ps1"
        Devices = @()
    },
    [PSCustomObject]@{
        Id = "MNOK-111"
        Name = "МНОК / 1 этаж / 111"
        Token = "wm_tok_06791590421adcf6"
        Script = "Update-MNOK-111.ps1"
        Devices = @()
    }
)

function Run-AllGroups([bool]$isPingOnly) {
    Write-Host "`n>>> ЗАПУСК ПО ВСЕМ ГРУППАМ ПАРКА <<<`n" -ForegroundColor Yellow
    foreach ($grp in $AllGroups) {
        if ($grp.Devices.Count -eq 0) { continue }
        Execute-GroupUpdate `
            -GroupName $grp.Name `
            -Token $grp.Token `
            -Devices $grp.Devices `
            -ServerUrl $ServerUrl `
            -Credential $Credential `
            -PingOnly:$isPingOnly
        Write-Host "`n------------------------------------------------------------`n"
    }
}

if ($All) {
    Run-AllGroups $PingOnly
    exit 0
}

# Интерактивное меню выбора
while ($true) {
    Clear-Host
    Write-Host "================================================================================" -ForegroundColor Cyan
    Write-Host "         WORKSTATION MANAGER - ПУЛЬТ УПРАВЛЕНИЯ ОБНОВЛЕНИЕМ ГРУПП               " -ForegroundColor Cyan
    Write-Host "================================================================================" -ForegroundColor Cyan
    Write-Host " Выберите группу компьютеров для запуска обновления агентов:`n" -ForegroundColor White

    for ($i = 0; $i -lt $AllGroups.Count; $i++) {
        $g = $AllGroups[$i]
        $numStr = " [{0,2}] " -f ($i + 1)
        $cntStr = "({0,2} ПК)" -f $g.Devices.Count
        Write-Host $numStr -NoNewline -ForegroundColor Green
        Write-Host ("{0,-30}" -f $g.Name) -NoNewline -ForegroundColor White
        Write-Host (" {0,-9} " -f $cntStr) -NoNewline -ForegroundColor DarkYellow
        Write-Host ("Токен: {0}" -f $g.Token) -ForegroundColor DarkGray
    }

    Write-Host "`n [ A ] " -NoNewline -ForegroundColor Yellow
    Write-Host "Обновить ВСЕ группы подряд (все 61 ПК)" -ForegroundColor Yellow

    Write-Host " [ P ] " -NoNewline -ForegroundColor Cyan
    Write-Host "Проверить связь (Ping) по всем группам" -ForegroundColor Cyan

    Write-Host " [ Q ] " -NoNewline -ForegroundColor Red
    Write-Host "Выход`n" -ForegroundColor Red

    $choice = Read-Host "Ваш выбор"
    $choice = $choice.Trim().ToUpper()

    if ($choice -eq "Q") {
        Write-Host "Завершение работы." -ForegroundColor Gray
        break
    } elseif ($choice -eq "A") {
        Run-AllGroups $false
        Read-Host "`nНажмите Enter для возврата в меню..."
    } elseif ($choice -eq "P") {
        Run-AllGroups $true
        Read-Host "`nНажмите Enter для возврата в меню..."
    } else {
        $selNum = 0
        if ([int]::TryParse($choice, [ref]$selNum) -and $selNum -ge 1 -and $selNum -le $AllGroups.Count) {
            $selGroup = $AllGroups[$selNum - 1]
            Execute-GroupUpdate `
                -GroupName $selGroup.Name `
                -Token $selGroup.Token `
                -Devices $selGroup.Devices `
                -ServerUrl $ServerUrl `
                -Credential $Credential `
                -PingOnly:$PingOnly
            Read-Host "`nНажмите Enter для возврата в меню..."
        } else {
            Write-Host "[!] Неверный ввод, попробуйте снова." -ForegroundColor Red
            Start-Sleep -Seconds 1
        }
    }
}
