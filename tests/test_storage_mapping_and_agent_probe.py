import pytest
import subprocess
from pathlib import Path
from backend.app.core.config import settings

def test_version_bumped_to_2_9_15():
    assert settings.LATEST_AGENT_VERSION == "2.9.15"

def test_installer_has_nvme_and_smart_support():
    installer_path = Path("agent/standalone_installer.ps1")
    assert installer_path.exists()
    content = installer_path.read_text(encoding="utf-8")

    # 1. Must have version 2.9.15
    assert "$AgentVersion = '2.9.15'" in content

    # 2. Live disks must include healthPercent and temperatureC
    assert "healthPercent" in content
    assert "temperatureC" in content

    # 3. Enhanced NVMe / SSD detection for models like SX6000PNP, ADATA, etc.
    assert "SX6000" in content or "Get-PhysicalDisk" in content or "SX" in content

def test_installer_powershell_ast_syntax():
    installer_path = Path("agent/standalone_installer.ps1")
    content = installer_path.read_text(encoding="utf-8")
    
    ps_cmd = [
        "powershell.exe",
        "-NoProfile",
        "-Command",
        """
        $code = Get-Content -Raw -Path 'agent/standalone_installer.ps1' -Encoding UTF8
        $tokens = $null
        $errors = $null
        $ast = [System.Management.Automation.Language.Parser]::ParseInput($code, [ref]$tokens, [ref]$errors)
        if ($errors -and $errors.Count -gt 0) {
            $errors | ForEach-Object { Write-Error $_.Message }
            exit 1
        }
        exit 0
        """
    ]
    res = subprocess.run(ps_cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"PowerShell AST syntax errors: {res.stderr}"
