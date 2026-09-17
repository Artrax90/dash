<#
.SYNOPSIS
    Northstar Ops / Workstation Manager - Движок удаленного и локального обновления агентов по группам
#>

param(
    [string]$ServerUrl = "http://172.19.33.68:2301",
    [pscredential]$Credential = $null
)

function Test-TcpPortQuick([string]$hostOrIp, [int]$port, [int]$timeoutMs = 400) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $ar = $tcp.BeginConnect($hostOrIp, $port, $null, $null)
        $wait = $ar.AsyncWaitHandle.WaitOne($timeoutMs, $false)
        if (-not $wait) {
            $tcp.Close()
            return $false
        }
        $tcp.EndConnect($ar)
        $tcp.Close()
        return $true
    } catch {
        return $false
    }
}

function Resolve-EffectiveServerUrl([string]$srv) {
    if (-not $srv) { $srv = "http://172.19.33.68:2301" }
    $srv = $srv.TrimEnd('/')
    
    $candidates = @($srv, "http://172.19.33.68:2301", "http://192.168.1.109:2301")
    $gw = (Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty NextHop -First 1)
    if ($gw) { $candidates += "http://${gw}:2301" }

    foreach ($c in $candidates) {
        if (-not $c) { continue }
        try {
            $u = [System.Uri]$c
            if (Test-TcpPortQuick $u.Host $u.Port 350) {
                return $c
            }
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

    # 1. Быстрая проверка доступности (ICMP пинг 500 мс)
    $pingOk = $false
    try {
        $p = New-Object System.Net.NetworkInformation.Ping
        $reply = $p.Send($IP, 500)
        if ($reply.Status -eq [System.Net.NetworkInformation.IPStatus]::Success) {
            $pingOk = $true
        }
    } catch {}

    if (-not $pingOk) {
        # Если ICMP закрыт файрволом, проверим порт 135 (RPC) или 5985 (WinRM) или 445 (SMB)
        if (Test-TcpPortQuick $IP 135 400 -or Test-TcpPortQuick $IP 445 400 -or Test-TcpPortQuick $IP 5985 400) {
            $pingOk = $true
        }
    }

    if (-not $pingOk) {
        $result.Status = "OFFLINE"
        $result.Details = "Хост недоступен по сети (нет ответа на пинг/порты)"
        return $result
    }
    $result.Ping = $true

    # Формируем чистую команду тихого обновления агента
    $psCmd = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -Command `"[Net.ServicePointManager]::SecurityProtocol = 3072; `$u = '$ServerUrl/install.ps1?token=$Token'; (New-Object Net.WebClient).DownloadString(`$u) | Invoke-Expression`""

    $plainUser = if ($Credential) { $Credential.UserName } else { "" }
    $plainPass = if ($Credential) { [System.Net.NetworkCredential]::new("", $Credential.Password).Password } else { "" }

    # Список кандидатов логинов: admin, .\admin, IP\admin, а также Administrator / Администратор
    $userCandidates = @()
    if ($plainUser) {
        $userCandidates += @($plainUser, "$IP\$plainUser", ".\$plainUser")
        if ($plainUser -like "*admin*") {
            $userCandidates += @("Administrator", "$IP\Administrator", ".\Administrator", "Администратор", "$IP\Администратор")
        }
    }
    $userCandidates = $userCandidates | Select-Object -Unique

    $errs = @()

    # 2. МЕТОД: Планировщик заданий (schtasks.exe) с запуском от имени NT AUTHORITY\SYSTEM
    # Обходит фильтрацию токенов Remote UAC для локальных администраторов
    if ($plainUser -and $plainPass) {
        foreach ($uCandidate in $userCandidates) {
            try {
                $taskName = "WM_OTA_Update"
                $trArg = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -Command `"[Net.ServicePointManager]::SecurityProtocol = 3072; `$u = '$ServerUrl/install.ps1?token=$Token'; (New-Object Net.WebClient).DownloadString(`$u) | Invoke-Expression`""
                
                $createOut = & schtasks.exe /Create /S $IP /U $uCandidate /P $plainPass /SC ONCE /ST "23:59" /TN $taskName /TR $trArg /RU "SYSTEM" /RL HIGHEST /F 2>&1
                $createStr = ($createOut | Out-String).Trim()
                
                if ($createStr -match "SUCCESS" -or $createStr -match "УСПЕШНО" -or $LASTEXITCODE -eq 0) {
                    & schtasks.exe /Run /S $IP /U $uCandidate /P $plainPass /TN $taskName 2>&1 | Out-Null
                    Start-Sleep -Milliseconds 600
                    & schtasks.exe /Delete /S $IP /U $uCandidate /P $plainPass /TN $taskName /F 2>&1 | Out-Null
                    
                    $result.Status = "SUCCESS_SCHTASKS"
                    $result.Details = "Успешно запущено через Планировщик (SYSTEM, пользователь $uCandidate)"
                    return $result
                } else {
                    $errs += "SchTasks ($uCandidate): $createStr"
                }
            } catch {
                $errs += "SchTasks ($uCandidate): $($_.Exception.Message)"
            }
        }
    }

    # 3. МЕТОД: WinRM (Invoke-Command)
    if ($plainUser -and $plainPass) {
        foreach ($uCandidate in $userCandidates) {
            try {
                $sec = ConvertTo-SecureString $plainPass -AsPlainText -Force
                $cObj = New-Object System.Management.Automation.PSCredential($uCandidate, $sec)
                $so = New-PSSessionOption -OpenTimeout 2500 -OperationTimeout 3500
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
                    Credential = $cObj
                    SessionOption = $so
                    ErrorAction = 'Stop'
                }
                Invoke-Command @icParams | Out-Null
                $result.Status = "SUCCESS_WINRM"
                $result.Details = "Успешно выполнено через WinRM ($uCandidate)"
                return $result
            } catch {
                $errs += "WinRM ($uCandidate): $($_.Exception.Message)"
            }
        }
    }

    # 4. МЕТОД: WMI (ManagementClass с явным Scope и ConnectionOptions)
    if ($plainUser -and $plainPass) {
        foreach ($uCandidate in $userCandidates) {
            try {
                $sec = ConvertTo-SecureString $plainPass -AsPlainText -Force
                $opt = New-Object System.Management.ConnectionOptions
                $opt.Username = $uCandidate
                $opt.SecurePassword = $sec
                $opt.EnablePrivileges = $true
                $opt.Impersonation = [System.Management.ImpersonationLevel]::Impersonate
                $opt.Authentication = [System.Management.AuthenticationLevel]::PacketPrivacy
                $opt.Timeout = [TimeSpan]::FromSeconds(3)

                $scope = New-Object System.Management.ManagementScope("\\$IP\root\cimv2", $opt)
                $scope.Connect()

                $processClass = New-Object System.Management.ManagementClass($scope, (New-Object System.Management.ManagementPath("Win32_Process")), $null)
                $inParams = $processClass.GetMethodParameters("Create")
                $inParams["CommandLine"] = $psCmd
                $outParams = $processClass.InvokeMethod("Create", $inParams, $null)

                $retVal = [int]$outParams["ReturnValue"]
                if ($retVal -eq 0) {
                    $pidVal = $outParams["ProcessId"]
                    $result.Status = "SUCCESS_WMI"
                    $result.Details = "Успешно запущен процесс обновления (PID: $pidVal, пользователь: $uCandidate)"
                    return $result
                } else {
                    $errs += "WMI ($uCandidate): ReturnCode=$retVal"
                }
            } catch {
                $errs += "WMI ($uCandidate): $($_.Exception.Message)"
            }
        }
    }

    # 5. МЕТОД: Нативная утилита wmic.exe
    if ($plainUser -and $plainPass) {
        foreach ($uCandidate in $userCandidates) {
            try {
                $wmicOut = & wmic.exe /node:"$IP" /user:"$uCandidate" /password:"$plainPass" process call create "$psCmd" 2>&1
                $wmicStr = ($wmicOut | Out-String)
                if ($wmicStr -match "ReturnValue\s*=\s*0" -or $wmicStr -match "ProcessId\s*=\s*(\d+)") {
                    $result.Status = "SUCCESS_WMIC"
                    $result.Details = "Успешно запущен через wmic.exe ($uCandidate)"
                    return $result
                } else {
                    $errs += "WMIC ($uCandidate): $($wmicStr.Trim())"
                }
            } catch {}
        }
    }

    # 6. Если все удаленные методы отклонены
    $result.Status = "AUTH_OR_RPC_BLOCKED"
    $cleanErr = ($errs | Select-Object -First 2) -join " | "
    $result.Details = if ($cleanErr) { $cleanErr } else { "Отказ в доступе (Remote UAC / Firewall)" }
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

    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Cyan
    Write-Host "   WORKSTATION MANAGER - ОБНОВЛЕНИЕ АГЕНТОВ ДЛЯ ГРУППЫ" -ForegroundColor Cyan
    Write-Host "   Группа: $GroupName" -ForegroundColor Yellow
    Write-Host "   Токен:  $Token" -ForegroundColor DarkGray
    if ($Credential) {
        Write-Host "   Учетная запись: $($Credential.UserName) (пароль передан)" -ForegroundColor Green
    }
    Write-Host "================================================================================" -ForegroundColor Cyan

    # Настройка WinRM TrustedHosts для исключения блокировки подключений по IP
    try {
        if ((Get-Service WinRM -ErrorAction SilentlyContinue).Status -ne "Running") {
            Start-Service WinRM -ErrorAction SilentlyContinue
        }
        Set-Item -Path WSMan:\localhost\Client\TrustedHosts -Value '*' -Force -ErrorAction SilentlyContinue
    } catch {}

    Write-Host "[*] Поиск активного сервера... " -NoNewline -ForegroundColor White
    $effServer = Resolve-EffectiveServerUrl $ServerUrl
    Write-Host "[OK: $effServer]" -ForegroundColor Green
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
        Write-Host "[*] Режим проверки связи (Ping Only):`n" -ForegroundColor Yellow
    } else {
        Write-Host "[*] Запуск удаленного обновления станций:`n" -ForegroundColor Yellow
    }

    $results = @()
    $idx = 1
    foreach ($dev in $Devices) {
        $ip = $dev.IP
        $name = $dev.Name
        Write-Host (" [{0,2}/{1,2}] {2,-16} ({3,-15}) ... " -f $idx, $Devices.Count, $name, $ip) -NoNewline -ForegroundColor White

        if ($PingOnly) {
            $pOk = $false
            try {
                $p = New-Object System.Net.NetworkInformation.Ping
                $reply = $p.Send($ip, 500)
                if ($reply.Status -eq [System.Net.NetworkInformation.IPStatus]::Success) { $pOk = $true }
            } catch {}
            if ($pOk) {
                Write-Host "[В СЕТИ]" -ForegroundColor Green
                $results += [PSCustomObject]@{ IP = $ip; Name = $name; Status = "ONLINE"; Details = "Хост доступен" }
            } else {
                Write-Host "[ВЫКЛЮЧЕН / ОФФЛАЙН]" -ForegroundColor DarkGray
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
                Write-Host ("       Причина: " + $res.Details) -ForegroundColor DarkYellow
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

    Write-Host ("Итог: Всего: {0}, Успешно запущено: {1}, Выключено/Оффлайн: {2}, Требуют доступа/RPC: {3}" -f $results.Count, $succCount, $offCount, $otherCount) -ForegroundColor Cyan
    Write-Host ""
    if ($otherCount -gt 0) {
        Write-Host "Политика Remote UAC или Windows Firewall на машинах блокирует удаленный запуск." -ForegroundColor Yellow
        Write-Host "Команда для обновления прямо на ПК (вставить в PowerShell):" -ForegroundColor White
        Write-Host "  powershell -ep bypass -c `"irm $effServer/install.ps1?token=$Token | iex`"" -ForegroundColor Green
    }
    Write-Host ""
}
