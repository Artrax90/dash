<#
.SYNOPSIS
    Northstar Ops / Workstation Manager - Движок удаленного обновления агентов
.DESCRIPTION
    Многоуровневый каскадный удаленный запуск:
    1. SCHTASKS.EXE (Планировщик заданий) с правильным экранированием /TR и fallback
    2. WMI (ManagementClass с явным Scope, ConnectionOptions и PacketPrivacy)
    3. WinRM (Invoke-Command) с автонастройкой TrustedHosts
    4. SC.EXE (Service Control Manager через SMB/IPC$)
    
    Оптимизация: проверка портов (135, 445, 5985) перед вызовом для исключения зависаний.
#>

function Test-TcpPortQuick([string]$hostOrIp, [int]$port, [int]$timeoutMs = 350) {
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

    # 1. Быстрая проверка доступности по сети (ICMP или открытые порты 135/445/5985/3389)
    $pingOk = $false
    try {
        $p = New-Object System.Net.NetworkInformation.Ping
        $reply = $p.Send($IP, 400)
        if ($reply.Status -eq [System.Net.NetworkInformation.IPStatus]::Success) {
            $pingOk = $true
        }
    } catch {}

    $port135 = Test-TcpPortQuick $IP 135 300
    $port445 = Test-TcpPortQuick $IP 445 300
    $port5985 = Test-TcpPortQuick $IP 5985 300
    $port3389 = Test-TcpPortQuick $IP 3389 300

    if (-not $pingOk) {
        if ($port135 -or $port445 -or $port5985 -or $port3389) {
            $pingOk = $true
        }
    }

    if (-not $pingOk) {
        $result.Status = "OFFLINE"
        $result.Details = "Хост недоступен по сети (нет ответа на пинг и порты 135/445/3389)"
        return $result
    }
    $result.Ping = $true

    $plainUser = if ($Credential) { $Credential.UserName } else { "" }
    $plainPass = if ($Credential) { [System.Net.NetworkCredential]::new("", $Credential.Password).Password } else { "" }

    if (-not $plainPass) {
        $result.Status = "ACCESS_DENIED"
        $result.Details = "Учетные данные не переданы"
        return $result
    }

    # Список кандидатов: admin, .\admin, Administrator (только целевые, без раздувания таймаутов)
    $userCandidates = @($plainUser, ".\$plainUser")
    if ($plainUser -like "*admin*") {
        $userCandidates += @("Administrator", ".\Administrator")
    }
    $userCandidates = $userCandidates | Select-Object -Unique

    $installUrl = "$ServerUrl/install.ps1?token=$Token"
    # Валидное экранирование для /TR в schtasks.exe (без '=' снаружи кавычек, длина < 260 символов)
    $schTrArg = "\`"powershell.exe\`" -ExecutionPolicy Bypass -Command \`"irm '$installUrl' | iex\`""
    $wmiCmd = "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -Command `"irm '$installUrl' | iex`""

    $errs = @()

    foreach ($uCandidate in $userCandidates) {
        # --- ВЕКТОР 1: SCHTASKS.EXE (Планировщик заданий) ---
        # Выполняем только если порт 135 (RPC) или 445 (SMB) открыт
        if ($port135 -or $port445) {
            try {
                $taskName = "WM_OTA_Task"
                # Попытка 1: Запуск от имени SYSTEM (наивысшие привилегии)
                $schCreate = & schtasks.exe /Create /S $IP /U $uCandidate /P $plainPass /SC ONCE /ST "23:59" /TN $taskName /TR $schTrArg /RU "SYSTEM" /RL HIGHEST /F 2>&1
                $schStr = ($schCreate | Out-String).Trim()

                # Попытка 2: Если SYSTEM отклонен политикой UAC, создаем задачу от имени самого пользователя
                if ($schStr -notmatch "SUCCESS|УСПЕШНО" -and $LASTEXITCODE -ne 0) {
                    $schCreate = & schtasks.exe /Create /S $IP /U $uCandidate /P $plainPass /SC ONCE /ST "23:59" /TN $taskName /TR $schTrArg /F 2>&1
                    $schStr = ($schCreate | Out-String).Trim()
                }

                if ($schStr -match "SUCCESS|УСПЕШНО" -or $LASTEXITCODE -eq 0) {
                    & schtasks.exe /Run /S $IP /U $uCandidate /P $plainPass /TN $taskName 2>&1 | Out-Null
                    Start-Sleep -Milliseconds 500
                    & schtasks.exe /Delete /S $IP /U $uCandidate /P $plainPass /TN $taskName /F 2>&1 | Out-Null

                    $result.Status = "SUCCESS_SCHTASKS"
                    $result.Details = "Запущен процесс обновления через Планировщик ($uCandidate)"
                    return $result
                } else {
                    $cleanSch = ($schStr -replace "[\r\n]+", " ")
                    $errs += "SchTasks ($uCandidate): $cleanSch"
                }
            } catch {
                $errs += "SchTasks ($uCandidate): $($_.Exception.Message)"
            }
        }

        # --- ВЕКТОР 2: WMI (ManagementScope / Win32_Process) ---
        # Выполняем только если порт 135 открыт
        if ($port135) {
            try {
                $sec = ConvertTo-SecureString $plainPass -AsPlainText -Force
                $opt = New-Object System.Management.ConnectionOptions
                $opt.Username = $uCandidate
                $opt.SecurePassword = $sec
                $opt.EnablePrivileges = $true
                $opt.Impersonation = [System.Management.ImpersonationLevel]::Impersonate
                $opt.Authentication = [System.Management.AuthenticationLevel]::PacketPrivacy
                $opt.Timeout = [TimeSpan]::FromSeconds(2.5)

                $scope = New-Object System.Management.ManagementScope("\\$IP\root\cimv2", $opt)
                $scope.Connect()

                $processClass = New-Object System.Management.ManagementClass($scope, (New-Object System.Management.ManagementPath("Win32_Process")), $null)
                $inParams = $processClass.GetMethodParameters("Create")
                $inParams["CommandLine"] = $wmiCmd
                $outParams = $processClass.InvokeMethod("Create", $inParams, $null)

                $retVal = [int]$outParams["ReturnValue"]
                if ($retVal -eq 0) {
                    $pidVal = $outParams["ProcessId"]
                    $result.Status = "SUCCESS_WMI"
                    $result.Details = "Успешно запущен процесс WMI (PID: $pidVal, $uCandidate)"
                    return $result
                } else {
                    $errs += "WMI ($uCandidate): ReturnCode=$retVal"
                }
            } catch {
                $errs += "WMI ($uCandidate): $($_.Exception.Message)"
            }
        }

        # --- ВЕКТОР 3: WinRM (Invoke-Command) ---
        if ($port5985) {
            try {
                $sec = ConvertTo-SecureString $plainPass -AsPlainText -Force
                $cObj = New-Object System.Management.Automation.PSCredential($uCandidate, $sec)
                $so = New-PSSessionOption -OpenTimeout 2000 -OperationTimeout 3000
                $icParams = @{
                    ComputerName = $IP
                    ScriptBlock = {
                        param($url)
                        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
                        (New-Object Net.WebClient).DownloadString($url) | Invoke-Expression
                    }
                    ArgumentList = @($installUrl)
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

        # --- ВЕКТОР 4: SC.EXE (Service Control Manager через SMB) ---
        if ($port445) {
            try {
                & net.exe use "\\$IP\IPC$" /user:"$uCandidate" "$plainPass" 2>&1 | Out-Null
                $svcName = "WMAgentUpdate"
                $scCmd = "cmd.exe /c start /b powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -Command `"irm '$installUrl' | iex`""
                $scCreate = & sc.exe "\\$IP" create $svcName binPath= $scCmd start= demand 2>&1
                $scStr = ($scCreate | Out-String).Trim()

                if ($scStr -match "SUCCESS" -or $scStr -match "УСПЕХ" -or $LASTEXITCODE -eq 0 -or $scStr -match "1073") {
                    & sc.exe "\\$IP" start $svcName 2>&1 | Out-Null
                    Start-Sleep -Milliseconds 400
                    & sc.exe "\\$IP" delete $svcName 2>&1 | Out-Null
                    & net.exe use "\\$IP\IPC$" /delete /y 2>&1 | Out-Null

                    $result.Status = "SUCCESS_SC"
                    $result.Details = "Запущен процесс обновления через SC.EXE ($uCandidate)"
                    return $result
                } else {
                    $cleanSc = ($scStr -replace "[\r\n]+", " ")
                    $errs += "SC ($uCandidate): $cleanSc"
                }
            } catch {
                $errs += "SC ($uCandidate): $($_.Exception.Message)"
            }
        }
    }

    # Если все активные порты/векторы отклонены
    $result.Status = "ACCESS_DENIED"
    $cleanErr = ($errs | Select-Object -First 2) -join " | "
    $result.Details = if ($cleanErr) { $cleanErr } else { "Отказано в доступе (порты RPC/SMB закрыты или учетка отклонена)" }
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
    Write-Host "   WORKSTATION MANAGER - УДАЛЕННОЕ ОБНОВЛЕНИЕ АГЕНТОВ (MULTI-VECTOR)" -ForegroundColor Cyan
    Write-Host "   Группа: $GroupName" -ForegroundColor Yellow
    Write-Host "   Токен:  $Token" -ForegroundColor DarkGray
    if ($Credential) {
        Write-Host "   Учетная запись: $($Credential.UserName) (пароль передан)" -ForegroundColor Green
    } else {
        Write-Host "   Учетная запись: [НЕТ / АНОНИМНО]" -ForegroundColor Red
    }
    Write-Host "================================================================================" -ForegroundColor Cyan

    # 1. Автонастройка WinRM TrustedHosts на локальной машине для исключения блокировок IP
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
    Write-Host "[*] Методы удаленного развертывания: SCHTASKS -> WMI -> WinRM -> SC.EXE" -ForegroundColor DarkCyan
    Write-Host ""

    if ($LocalInstall) {
        Write-Host "[*] Локальная установка/обновление агента для группы '$GroupName'..." -ForegroundColor Yellow
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            $url = "$effServer/install.ps1?token=$Token"
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
                $reply = $p.Send($ip, 400)
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
                Write-Host ("       Метод: " + $res.Details) -ForegroundColor DarkGreen
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

    Write-Host ("Итог: Всего: {0}, Успешно запущено: {1}, Выключено/Оффлайн: {2}, Ошибок доступа: {3}" -f $results.Count, $succCount, $offCount, $otherCount) -ForegroundColor Cyan
    Write-Host ""
}
