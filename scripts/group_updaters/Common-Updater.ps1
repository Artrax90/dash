<#
.SYNOPSIS
    Northstar Ops / Workstation Manager - Движок удаленного и локального обновления агентов по группам
#>

param(
    [string]$ServerUrl = "http://172.19.33.68:2301",
    [pscredential]$Credential = $null
)

function Resolve-EffectiveServerUrl([string]$srv) {
    if (-not $srv) { $srv = "http://172.19.33.68:2301" }
    $srv = $srv.TrimEnd('/')
    $candidates = @($srv, "http://172.19.33.68:2301", "http://192.168.1.109:2301")
    $gw = (Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty NextHop -First 1)
    if ($gw) { $candidates += "http://${gw}:2301" }

    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    foreach ($c in $candidates) {
        if (-not $c) { continue }
        try {
            $req = [System.Net.WebRequest]::Create("$c/api/v1/agents/version-info")
            $req.Timeout = 1500
            $req.Proxy = $null
            $res = $req.GetResponse()
            $res.Close()
            return $c
        } catch {}
    }
    return $srv
}

function Invoke-RemoteAgentUpdate {
    param(
        [string]$IP,
        [string]$PCName,
        [string]$GroupName,
        [string]$Token,
        [string]$ServerUrl,
        [pscredential]$Credential = $null
    )

    $result = @{
        IP = $IP
        PCName = $PCName
        Ping = $false
        Status = "Unknown"
        Details = ""
    }

    # 1. Быстрая проверка ICMP пинга
    $pingOk = $false
    try {
        $p = New-Object System.Net.NetworkInformation.Ping
        $reply = $p.Send($IP, 1200)
        if ($reply.Status -eq [System.Net.NetworkInformation.IPStatus]::Success) {
            $pingOk = $true
        }
    } catch {}

    if (-not $pingOk) {
        $result.Status = "OFFLINE"
        $result.Details = "Хост недоступен по сети (ICMP timeout)"
        return $result
    }
    $result.Ping = $true

    # Формируем команду тихого обновления агента
    $psCmd = 'powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $u = \"' + $ServerUrl + '/install.ps1?token=' + $Token + '\"; $s = (New-Object Net.WebClient).DownloadString($u); Invoke-Expression $s"'

    # 2. Попытка через WMI (Win32_Process.Create) - самый универсальный корпоративный способ
    try {
        if ($Credential) {
            $opt = New-Object System.Management.ConnectionOptions
            $opt.Username = $Credential.UserName
            $opt.Password = $Credential.Password
            $scope = New-Object System.Management.ManagementScope("\\$IP\root\cimv2", $opt)
            $scope.Connect()
            $wmi = [wmiclass]"\\$IP\root\cimv2:Win32_Process"
            $wmi.Scope = $scope
        } else {
            $wmi = [wmiclass]"\\$IP\root\cimv2:Win32_Process"
        }

        $res = $wmi.Create($psCmd)
        if ($res -and $res.ReturnValue -eq 0) {
            $result.Status = "SUCCESS_WMI"
            $result.Details = "Успешно запущен процесс обновления (PID: $($res.ProcessId))"
            return $result
        } elseif ($res) {
            $wmiErr = "WMI ReturnValue=$($res.ReturnValue)"
        }
    } catch {
        $wmiErr = $_.Exception.Message
    }

    # 3. Попытка через WinRM (Invoke-Command)
    try {
        $icParams = @{
            ComputerName = $IP
            ScriptBlock = {
                param($srv, $tok)
                [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
                $u = "$srv/install.ps1?token=$tok"
                $code = (New-Object Net.WebClient).DownloadString($u)
                Invoke-Expression $code
            }
            ArgumentList = @($ServerUrl, $Token)
            ErrorAction = 'Stop'
        }
        if ($Credential) { $icParams.Credential = $Credential }
        Invoke-Command @icParams | Out-Null
        $result.Status = "SUCCESS_WINRM"
        $result.Details = "Успешно выполнено через WinRM"
        return $result
    } catch {
        $winrmErr = $_.Exception.Message
    }

    # 4. Если прямой удаленный вызов заблокирован правами / политиками
    $result.Status = "AUTH_OR_RPC_BLOCKED"
    $result.Details = "В сети, но требуется запуск от доменного админа (WMI: $wmiErr; WinRM: $winrmErr)"
    return $result
}

function Execute-GroupUpdate {
    param(
        [string]$GroupName,
        [string]$Token,
        [array]$Devices,
        [string]$ServerUrl = "http://172.19.33.68:2301",
        [pscredential]$Credential = $null,
        [switch]$LocalInstall,
        [switch]$PingOnly
    )

    Clear-Host
    Write-Host "================================================================================" -ForegroundColor Cyan
    Write-Host "   WORKSTATION MANAGER - ОБНОВЛЕНИЕ АГЕНТОВ ДЛЯ ГРУППЫ" -ForegroundColor Cyan
    Write-Host "   Группа: $GroupName" -ForegroundColor Yellow
    Write-Host "   Токен:  $Token" -ForegroundColor DarkGray
    Write-Host "================================================================================" -ForegroundColor Cyan

    $effServer = Resolve-EffectiveServerUrl $ServerUrl
    Write-Host "[*] Целевой сервер: $effServer" -ForegroundColor Green
    Write-Host "[*] Компьютеров в группе: $($Devices.Count)" -ForegroundColor Green
    Write-Host ""

    # Если запрошена локальная установка на этом конкретном ПК
    if ($LocalInstall) {
        Write-Host "[*] Локальная установка/обновление агента для группы '$GroupName'..." -ForegroundColor Yellow
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            $url = "$effServer/install.ps1?token=$Token"
            Write-Host "[*] Загрузка установщика: $url" -ForegroundColor DarkGray
            $script = (New-Object Net.WebClient).DownloadString($url)
            Invoke-Expression $script
            Write-Host "[OK] Локальное обновление успешно выполнено!" -ForegroundColor Green
        } catch {
            Write-Host "[ERR] Ошибка локальной установки: $($_.Exception.Message)" -ForegroundColor Red
        }
        return
    }

    if ($PingOnly) {
        Write-Host "[*] Режим проверки связи (Ping Only):" -ForegroundColor Yellow
    } else {
        Write-Host "[*] Запуск удаленного обновления станций..." -ForegroundColor Yellow
    }

    $results = @()
    $idx = 1
    foreach ($dev in $Devices) {
        $ip = $dev.IP
        $name = $dev.Name
        Write-Host " [$idx/$($Devices.Count)] Опрос $name ($ip)... " -NoNewline -ForegroundColor White

        if ($PingOnly) {
            $pOk = $false
            try {
                $p = New-Object System.Net.NetworkInformation.Ping
                $reply = $p.Send($ip, 1200)
                if ($reply.Status -eq [System.Net.NetworkInformation.IPStatus]::Success) { $pOk = $true }
            } catch {}
            if ($pOk) {
                Write-Host "[В СЕТИ]" -ForegroundColor Green
                $results += [PSCustomObject]@{ IP = $ip; Name = $name; Status = "ONLINE"; Details = "Хост доступен" }
            } else {
                Write-Host "[ОФФЛАЙН]" -ForegroundColor DarkGray
                $results += [PSCustomObject]@{ IP = $ip; Name = $name; Status = "OFFLINE"; Details = "Не отвечает на пинг" }
            }
        } else {
            $res = Invoke-RemoteAgentUpdate -IP $ip -PCName $name -GroupName $GroupName -Token $Token -ServerUrl $effServer -Credential $Credential
            if ($res.Status -like "SUCCESS*") {
                Write-Host "[ОБНОВЛЕНИЕ ЗАПУЩЕНО]" -ForegroundColor Green
            } elseif ($res.Status -eq "OFFLINE") {
                Write-Host "[ВЫКЛЮЧЕН / ОФФЛАЙН]" -ForegroundColor DarkGray
            } else {
                Write-Host "[ТРЕБУЕТ ДОСТУП]" -ForegroundColor Yellow
            }
            $results += [PSCustomObject]@{
                IP = $ip
                Name = $name
                Status = $res.Status
                Details = $res.Details
            }
        }
        $idx++
    }

    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Cyan
    Write-Host "                             СВОДНЫЙ ОТЧЕТ ПО ГРУППЕ                            " -ForegroundColor Cyan
    Write-Host "================================================================================" -ForegroundColor Cyan
    $results | Format-Table -AutoSize -Property Name, IP, Status, Details

    $succCount = ($results | Where-Object { $_.Status -like "SUCCESS*" -or $_.Status -eq "ONLINE" }).Count
    $offCount = ($results | Where-Object { $_.Status -eq "OFFLINE" }).Count
    $otherCount = $results.Count - $succCount - $offCount

    Write-Host "Итог: Обработано $($results.Count) станций. Успешно/В сети: $succCount, Оффлайн: $offCount, Требуют доступа: $otherCount" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Подсказка: Для станций, где заблокирован удаленный RPC/WMI, можно:" -ForegroundColor DarkYellow
    Write-Host "  1. Запустить этот же скрипт с флагом -Credential (Get-Credential) от имени доменного админа;" -ForegroundColor DarkYellow
    Write-Host "  2. Или запустить скрипт прямо на целевом ПК с параметром -LocalInstall;" -ForegroundColor DarkYellow
    Write-Host "  3. Или в 1 клик нажать «Обновить агент» в веб-панели Northstar Ops, когда ПК выйдет в сеть." -ForegroundColor DarkYellow
    Write-Host ""
}
