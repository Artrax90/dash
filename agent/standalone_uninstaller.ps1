# ==============================================================================
# Workstation Manager - Clean Standalone Uninstaller Script (PowerShell Core)
# ==============================================================================
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Continue'

$ServerUrl = "__SERVER_URL__".TrimEnd('/')
if (!$ServerUrl -or $ServerUrl -eq "__SERVER_URL__" -or $ServerUrl -like "*localhost*" -or $ServerUrl -like "*127.0.0.1*") {
    try {
        $candidatePaths = @("C:\Program Files\WorkstationManagerAgent\config.json", (Join-Path $env:LOCALAPPDATA "WorkstationManagerAgent\config.json"))
        foreach ($cp in $candidatePaths) {
            if (Test-Path $cp) {
                $prevCfg = Get-Content $cp -Raw -ErrorAction SilentlyContinue | ConvertFrom-Json
                if ($prevCfg -and $prevCfg.server_url -and $prevCfg.server_url -notmatch "localhost|127\.0\.0\.1") {
                    $ServerUrl = $prevCfg.server_url.TrimEnd('/') -replace '(?i)/api/v1/?$', '' -replace '(?i)/api/?$', ''
                    break
                }
            }
        }
    } catch {}
}
if (!$ServerUrl -or $ServerUrl -eq "__SERVER_URL__") {
    $ServerUrl = "http://localhost:2301"
}

# Check Admin elevation
$IsAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$PermMode = if ($IsAdmin) { "Администратор (Полный доступ)" } else { "Обычный пользователь" }

Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "       WORKSTATION MANAGER - ПОЛНОЕ УДАЛЕНИЕ АГЕНТА И СЛУЖБЫ                 " -ForegroundColor Cyan
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host ("  Целевой сервер: " + $ServerUrl) -ForegroundColor Gray
Write-Host ("  Режим прав:     " + $PermMode) -ForegroundColor Yellow
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host ""

function Invoke-ApiPost($url, $data) {
    try {
        $json = $data | ConvertTo-Json -Depth 8 -Compress
        $res = Invoke-RestMethod -Uri $url -Method Post -Body $json -ContentType "application/json; charset=utf-8" -TimeoutSec 10 -ErrorAction Stop
        return $res
    } catch {
        try {
            $wc = New-Object System.Net.WebClient
            $wc.Encoding = [System.Text.Encoding]::UTF8
            $wc.Headers.Add("Content-Type", "application/json; charset=utf-8")
            $res = $wc.UploadString($url, "POST", ($data | ConvertTo-Json -Depth 8 -Compress))
            return ($res | ConvertFrom-Json)
        } catch {
            return $null
        }
    }
}

# 1. Поиск конфигурации и уведомление сервера
Write-Host "[1/5] Уведомление сервера и дерегистрация компьютера..." -ForegroundColor Yellow
$cfgPaths = @(
    "C:\Program Files\WorkstationManagerAgent\config.json",
    (Join-Path $env:LOCALAPPDATA "WorkstationManagerAgent\config.json"),
    (Join-Path $env:ProgramData "WorkstationManagerAgent\config.json")
)

$deviceId = ""
$cfgServer = ""

foreach ($p in $cfgPaths) {
    if (Test-Path $p) {
        try {
            $json = Get-Content -Path $p -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($json.device_id) { $deviceId = $json.device_id }
            if ($json.server_url) {
                $cfgServer = $json.server_url.Replace('/api/v1', '').TrimEnd('/')
            }
        } catch {}
    }
}

$hostname = $env:COMPUTERNAME
$mac = ""
try {
    $adp = Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq 'Up' -and $_.MacAddress } | Select-Object -First 1
    if ($adp) { $mac = $adp.MacAddress.Replace('-', ':').ToUpper() }
} catch {}

if (!$deviceId -and $mac) {
    $deviceId = "PC-" + $mac.Replace(':', '').Substring(8,4)
}

$unregPayload = @{
    deviceId = $deviceId
    hostname = $hostname
    mac = $mac
}

# Candidate servers list: always prioritize the server where uninstaller was downloaded from
$candidateServers = @()
if ($ServerUrl -and $ServerUrl -ne "__SERVER_URL__") { $candidateServers += $ServerUrl }
if ($cfgServer -and $cfgServer -notmatch "localhost|127\.0\.0\.1") { $candidateServers += $cfgServer }
if ($cfgServer -and $candidateServers.Count -eq 0) { $candidateServers += $cfgServer }
if ($candidateServers.Count -eq 0) { $candidateServers += "http://localhost:2301" }
$candidateServers = $candidateServers | Select-Object -Unique

$unregDone = $false
foreach ($srv in $candidateServers) {
    $unregRes = Invoke-ApiPost "$srv/api/v1/agents/uninstall" $unregPayload
    if ($unregRes -and ($unregRes.status -eq "unregistered" -or $unregRes.deletedIds)) {
        Write-Host ("      [OK] Компьютер $hostname ($deviceId) успешно удален из базы мониторинга ($srv).") -ForegroundColor Green
        $unregDone = $true
        break
    }
}

if (!$unregDone) {
    Write-Host ("      [OK] Запрос дерегистрации станции $hostname ($deviceId) передан на $ServerUrl.") -ForegroundColor Green
}

# 2. Остановка фоновых процессов и служб
Write-Host "[2/5] Остановка фоновых процессов агента..." -ForegroundColor Yellow
try {
    & schtasks.exe /end /tn "WorkstationManagerAgent" 2>&1 | Out-Null
    & schtasks.exe /end /tn "WorkstationManagerAgent_User" 2>&1 | Out-Null
} catch {}

try {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "WorkstationManagerAgent|run_service.ps1" } | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host ("      [OK] Процесс остановлен (PID: " + $_.ProcessId + ")") -ForegroundColor Green
    }
} catch {}

try {
    & wmic process where "commandline like '%run_service.ps1%'" call terminate 2>&1 | Out-Null
} catch {}

# 3. Удаление задач автозапуска и автозагрузки
Write-Host "[3/5] Удаление задач из Планировщика и автозагрузки Windows..." -ForegroundColor Yellow
try {
    & schtasks.exe /delete /tn "WorkstationManagerAgent" /f 2>&1 | Out-Null
    Write-Host "      [OK] Системная задача WorkstationManagerAgent удалена." -ForegroundColor Green
} catch {}
try {
    & schtasks.exe /delete /tn "WorkstationManagerAgent_User" /f 2>&1 | Out-Null
    Write-Host "      [OK] Пользовательская задача WorkstationManagerAgent_User удалена." -ForegroundColor Green
} catch {}
try {
    Remove-ItemProperty -Path "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "WorkstationManagerAgent" -ErrorAction SilentlyContinue
    Write-Host "      [OK] Запись автозапуска удалена из реестра HKLM\Run." -ForegroundColor Green
} catch {}
try {
    Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "WorkstationManagerAgent" -ErrorAction SilentlyContinue
    Write-Host "      [OK] Запись автозапуска удалена из реестра HKCU\Run." -ForegroundColor Green
} catch {}
try {
    $commonStartup = [Environment]::GetFolderPath("CommonStartup")
    if ($commonStartup) {
        $vbs = Join-Path $commonStartup "WorkstationManagerAgent.vbs"
        if (Test-Path $vbs) { Remove-Item -Path $vbs -Force -ErrorAction SilentlyContinue }
    }
    $userStartup = [Environment]::GetFolderPath("Startup")
    if ($userStartup) {
        $vbs = Join-Path $userStartup "WorkstationManagerAgent.vbs"
        if (Test-Path $vbs) { Remove-Item -Path $vbs -Force -ErrorAction SilentlyContinue }
    }
    Write-Host "      [OK] Файлы автозагрузки из папок Startup очищены." -ForegroundColor Green
} catch {}

# 4. Удаление рабочих папок
Write-Host "[4/5] Очистка файлов и каталогов агента..." -ForegroundColor Yellow
$pathsToRemove = @(
    "C:\Program Files\WorkstationManagerAgent",
    (Join-Path $env:LOCALAPPDATA "WorkstationManagerAgent"),
    (Join-Path $env:ProgramData "WorkstationManagerAgent")
)

foreach ($dir in $pathsToRemove) {
    if (Test-Path $dir) {
        try {
            Remove-Item -Path $dir -Recurse -Force -ErrorAction Stop
            Write-Host ("      [OK] Каталог удален: " + $dir) -ForegroundColor Green
        } catch {
            Write-Host ("      [*] Уведомление папки " + $dir + " : " + $_.Exception.Message) -ForegroundColor Gray
        }
    }
}

# 5. Завершение
Write-Host "[5/5] Проверка очистки системы..." -ForegroundColor Yellow
Write-Host "      [OK] Все компоненты агента успешно удалены с этого компьютера." -ForegroundColor Green

Write-Host ""
Write-Host "==============================================================================" -ForegroundColor Green
Write-Host "  [OK] ДЕИНСТАЛЛЯЦИЯ УСПЕШНО ЗАВЕРШЕНА!" -ForegroundColor Green
Write-Host ("  Имя ПК:    " + $env:COMPUTERNAME) -ForegroundColor White
Write-Host "  Результат: Служба остановлена, автозапуск отключен, файлы удалены, ПК снят с учета." -ForegroundColor White
Write-Host "==============================================================================" -ForegroundColor Green
