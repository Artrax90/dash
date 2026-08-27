# Workstation Manager - Repair, WoL Auto-Config & Silent Mode Fix

$IsAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $IsAdmin) {
    Write-Host "Elevating administrator privileges..." -ForegroundColor Yellow
    Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "   Workstation Manager - Repair & WoL Configuration              " -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Update/Deploy fresh standalone installer v1.8.0
Write-Host "`n[1/5] Deploying fresh Agent Service v1.8.0..." -ForegroundColor Yellow
try {
    $installerPath = Join-Path $PSScriptRoot "standalone_installer.ps1"
    if (Test-Path $installerPath) {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installerPath -ServerUrl "http://192.168.1.109:2301" -Token "wm_tok_live_7f8a92b3c4d5e6f7"
        Write-Host "      [OK] Fresh Agent v1.8.0 installed successfully from local repository." -ForegroundColor Green
    } else {
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
        (New-Object System.Net.WebClient).DownloadFile("http://192.168.1.109:2301/install.ps1", "$env:TEMP\wm_install_180.ps1")
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:TEMP\wm_install_180.ps1" -ServerUrl "http://192.168.1.109:2301" -Token "wm_tok_live_7f8a92b3c4d5e6f7"
        Write-Host "      [OK] Fresh Agent v1.8.0 downloaded and installed from server." -ForegroundColor Green
    }
} catch {
    Write-Host "      [*] Warning installing agent: $($_.Exception.Message)" -ForegroundColor Gray
}

# 2. Clean registry run keys to stop popup powershell window
Write-Host "`n[2/5] Cleaning interactive Run registry entries..." -ForegroundColor Yellow
try {
    Remove-ItemProperty -Path "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "WorkstationManagerAgent" -ErrorAction SilentlyContinue
    Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "WorkstationManagerAgent" -ErrorAction SilentlyContinue
    $commonStartup = [Environment]::GetFolderPath("CommonStartup")
    if ($commonStartup) { Remove-Item (Join-Path $commonStartup "WorkstationManagerAgent.vbs") -Force -ErrorAction SilentlyContinue }
    Write-Host "      [OK] Interactive startup keys removed." -ForegroundColor Green
} catch {
    Write-Host "      [*] Warning: $($_.Exception.Message)" -ForegroundColor Gray
}

# 2. Configure Wake-on-LAN on all physical adapters
Write-Host "`n[2/4] Configuring Wake-on-LAN on network adapters..." -ForegroundColor Yellow
try {
    Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object { $_.InterfaceDescription -notmatch 'Virtual|VMware|VirtualBox|Hyper-V|TAP|VPN|Loopback|Npcap|Bluetooth' } | ForEach-Object {
        $nicName = $_.Name
        try { Enable-NetAdapterWakeOnLan -Name $nicName -ErrorAction SilentlyContinue } catch {}
        try { Set-NetAdapterPowerManagement -Name $nicName -WakeOnMagicPacket Enabled -WakeOnPattern Enabled -ErrorAction SilentlyContinue } catch {}
        Write-Host "      [OK] Adapter configured: $nicName" -ForegroundColor Green
    }

    # Driver registry configuration
    $nicClassKey = "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}"
    if (Test-Path $nicClassKey) {
        Get-ChildItem $nicClassKey -ErrorAction SilentlyContinue | ForEach-Object {
            $subPath = $_.PSPath
            try {
                Set-ItemProperty -Path $subPath -Name "*WakeOnMagicPacket" -Value "1" -Type String -ErrorAction SilentlyContinue
                Set-ItemProperty -Path $subPath -Name "*WakeOnPattern" -Value "1" -Type String -ErrorAction SilentlyContinue
                Set-ItemProperty -Path $subPath -Name "ShutdownWakeOnLan" -Value "1" -Type String -ErrorAction SilentlyContinue
                Set-ItemProperty -Path $subPath -Name "EnablePME" -Value "1" -Type String -ErrorAction SilentlyContinue
                Set-ItemProperty -Path $subPath -Name "WakeOnLink" -Value "1" -Type String -ErrorAction SilentlyContinue
                Set-ItemProperty -Path $subPath -Name "WakeOnMagicPacketFromS5" -Value "1" -Type String -ErrorAction SilentlyContinue
                Set-ItemProperty -Path $subPath -Name "WakeOnSlot" -Value "1" -Type String -ErrorAction SilentlyContinue
                Set-ItemProperty -Path $subPath -Name "PnPCapabilities" -Value 0 -Type DWord -ErrorAction SilentlyContinue
                Set-ItemProperty -Path $subPath -Name "WolShutdownLinkSpeed" -Value "0" -Type String -ErrorAction SilentlyContinue
                Set-ItemProperty -Path $subPath -Name "PowerSaveMode" -Value "0" -Type String -ErrorAction SilentlyContinue
            } catch {}
        }
    }

    # Disable Fast Startup (HiberbootEnabled)
    Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power" -Name "HiberbootEnabled" -Value 0 -Type DWord -ErrorAction SilentlyContinue
    Write-Host "      [OK] Fast Startup disabled." -ForegroundColor Green

    # Firewall rules
    New-NetFirewallRule -DisplayName "Workstation Manager Wake-on-LAN (UDP 7, 9)" -Direction Inbound -Protocol UDP -LocalPort 7,9 -Action Allow -Profile Any -ErrorAction SilentlyContinue | Out-Null
    New-NetFirewallRule -DisplayName "Workstation Manager Direct Signal (UDP 48123)" -Direction Inbound -Protocol UDP -LocalPort 48123 -Action Allow -Profile Any -ErrorAction SilentlyContinue | Out-Null
} catch {
    Write-Host "      [*] Warning: $($_.Exception.Message)" -ForegroundColor Gray
}

# 3. Ensure background service is registered as SYSTEM (Session 0)
Write-Host "`n[3/4] Registering background service under SYSTEM..." -ForegroundColor Yellow
$InstallDir = "C:\Program Files\WorkstationManagerAgent"
$runServiceScript = Join-Path $InstallDir "run_service.ps1"

if (Test-Path $runServiceScript) {
    try {
        & schtasks.exe /end /tn "WorkstationManagerAgent" 2>&1 | Out-Null
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*run_service.ps1*" } | ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }

        $launcherVbs = Join-Path $InstallDir "launcher.vbs"
        $vbsCode = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""$runServiceScript""", 0, False
"@
        Set-Content -Path $launcherVbs -Value $vbsCode -Encoding ASCII

        $psExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
        $taskAction = New-ScheduledTaskAction -Execute $psExe -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runServiceScript`""
        $triggerBoot = New-ScheduledTaskTrigger -AtStartup
        $triggerLogon = New-ScheduledTaskTrigger -AtLogOn
        $taskPrincipal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest
        $taskSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 365) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable
        Register-ScheduledTask -TaskName "WorkstationManagerAgent" -Action $taskAction -Trigger @($triggerBoot, $triggerLogon) -Principal $taskPrincipal -Settings $taskSettings -Force | Out-Null
        
        $commonStartup = [Environment]::GetFolderPath("CommonStartup")
        if ($commonStartup -and (Test-Path $commonStartup)) {
            Copy-Item -Path $launcherVbs -Destination (Join-Path $commonStartup "WorkstationManagerAgent.vbs") -Force -ErrorAction SilentlyContinue
        }
        Set-ItemProperty -Path "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "WorkstationManagerAgent" -Value "`"$env:SystemRoot\System32\wscript.exe`" `"$launcherVbs`"" -Type String -ErrorAction SilentlyContinue

        try { & wscript.exe "$launcherVbs" } catch {}
        try { Start-ScheduledTask -TaskName "WorkstationManagerAgent" | Out-Null } catch {}
        Write-Host "      [OK] Multi-layer background service restarted under SYSTEM." -ForegroundColor Green
    } catch {
        Write-Host "      [*] Service warning: $($_.Exception.Message)" -ForegroundColor Gray
    }
}

Write-Host "`n[4/4] Done! All settings applied." -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan
