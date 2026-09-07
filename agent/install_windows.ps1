# Workstation Manager Agent Windows Installer Script
param (
    [string]$ServerUrl = $env:WM_SERVER,
    [string]$Token = $env:WM_TOKEN
)

if (-not $ServerUrl -or $ServerUrl -eq "") {
    $ServerUrl = "__SERVER_URL_PLACEHOLDER__"
}
if (-not $Token -or $Token -eq "") {
    $Token = "__TOKEN_PLACEHOLDER__"
}

$ServerUrl = $ServerUrl.TrimEnd('/')

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " Installing Workstation Manager Background Agent " -ForegroundColor Cyan
Write-Host " Server: $ServerUrl" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# Determine best installation directory
$IsAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if ($IsAdmin) {
    $InstallDir = "C:\Program Files\WorkstationManagerAgent"
} else {
    $InstallDir = Join-Path $env:LOCALAPPDATA "WorkstationManagerAgent"
}

try {
    if (!(Test-Path $InstallDir)) {
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    }
} catch {
    $InstallDir = Join-Path $env:LOCALAPPDATA "WorkstationManagerAgent"
    if (!(Test-Path $InstallDir)) {
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    }
}

Write-Host "[*] Target Directory: $InstallDir" -ForegroundColor Gray

# 1. Save Config
$ConfigFile = Join-Path $InstallDir "config.json"
$Config = @{
    server_url = "$ServerUrl/api/v1"
    enrollment_token = $Token
    heartbeat_interval_seconds = 30
} | ConvertTo-Json

Set-Content -Path $ConfigFile -Value $Config -Encoding UTF8
Write-Host "[✓] Configuration saved to $ConfigFile" -ForegroundColor Green

# 2. Download Agent Code
$AgentScript = Join-Path $InstallDir "agent.py"
try {
    Write-Host "[*] Downloading agent payload from server..." -ForegroundColor Gray
    $AgentUrl = "$ServerUrl/agent.py"
    Invoke-WebRequest -Uri $AgentUrl -OutFile $AgentScript -UseBasicParsing -TimeoutSec 15
    Write-Host "[✓] Agent script downloaded to $AgentScript" -ForegroundColor Green
} catch {
    Write-Host "[!] WebRequest download failed ($($_)), attempting direct Python download..." -ForegroundColor Yellow
    try {
        & python -c "import urllib.request; urllib.request.urlretrieve('$AgentUrl', r'$AgentScript')"
        Write-Host "[✓] Agent script downloaded via Python." -ForegroundColor Green
    } catch {
        Write-Host "[!] Error downloading agent.py: $_" -ForegroundColor Red
    }
}

# 3. Register Startup Task
try {
    if ($IsAdmin) {
        & schtasks.exe /create /tn "WorkstationManagerAgent" /tr "pythonw.exe `"$AgentScript`"" /sc ONSTART /ru "SYSTEM" /f | Out-Null
        Write-Host "[✓] Background startup task registered (SYSTEM / ONSTART)" -ForegroundColor Green
    } else {
        & schtasks.exe /create /tn "WorkstationManagerAgent" /tr "pythonw.exe `"$AgentScript`"" /sc ONLOGON /f | Out-Null
        Write-Host "[✓] Background startup task registered (User / ONLOGON)" -ForegroundColor Green
    }
} catch {
    Write-Host "[*] Task registration notice: $_" -ForegroundColor Gray
}

# 4. Enable and activate Wake-on-LAN (WoL)
try {
    Get-NetAdapter -Physical -ErrorAction SilentlyContinue | ForEach-Object {
        try { Enable-NetAdapterWakeOnLan -Name $_.Name -ErrorAction SilentlyContinue } catch {}
        try { Set-NetAdapterPowerManagement -Name $_.Name -WakeOnMagicPacket Enabled -WakeOnPattern Enabled -ErrorAction SilentlyContinue } catch {}
        try { Set-NetAdapterAdvancedProperty -Name $_.Name -DisplayName "*Wake*" -DisplayValue "*Enabled*" -ErrorAction SilentlyContinue } catch {}
        try { Set-NetAdapterAdvancedProperty -Name $_.Name -DisplayName "*Magic*" -DisplayValue "*Enabled*" -ErrorAction SilentlyContinue } catch {}
        try { Set-NetAdapterAdvancedProperty -Name $_.Name -DisplayName "*Shutdown Wake-On-Lan*" -DisplayValue "*Enabled*" -ErrorAction SilentlyContinue } catch {}
    }
    if ($IsAdmin) {
        Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power" -Name "HiberbootEnabled" -Value 0 -ErrorAction SilentlyContinue
    }
    Write-Host "[✓] Wake-on-LAN (Magic Packet) activated on network adapters" -ForegroundColor Green
} catch {}

# 5. Start Agent Immediately
try {
    $p = Start-Process -FilePath "python.exe" -ArgumentList "`"$AgentScript`"" -WindowStyle Hidden -PassThru
    Write-Host "[✓] Workstation Manager Agent started in background! (PID: $($p.Id))" -ForegroundColor Green
} catch {
    Write-Host "[*] Starting agent directly in python..." -ForegroundColor Gray
    Start-Process -FilePath "python.exe" -ArgumentList "`"$AgentScript`""
}

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " Installation Complete! Workstation is now linked." -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan
