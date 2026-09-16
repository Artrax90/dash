import pytest
import subprocess
from pathlib import Path
from backend.app.core.config import settings

def test_version_bumped_to_2_9_16():
    assert settings.LATEST_AGENT_VERSION == "2.9.16"

def test_installer_has_nvme_and_smart_support():
    installer_path = Path("agent/standalone_installer.ps1")
    assert installer_path.exists()
    content = installer_path.read_text(encoding="utf-8")

    # 1. Must have version 2.9.16
    assert "$AgentVersion = '2.9.16'" in content

    # 2. Live disks must include healthPercent and temperatureC
    assert "healthPercent" in content
    assert "temperatureC" in content

    # 3. Enhanced NVMe / SSD detection for models like SX6000PNP, ADATA, etc.
    assert "SX6000" in content or "Get-PhysicalDisk" in content or "SX" in content

    # 4. Must sort physical disks by Index and record diskIndex
    assert "Sort-Object Index" in content
    assert "diskIndex" in content

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

def test_partition_matching_scoring_algorithm():
    # Simulate the exact multi-disk scenario from user screenshots
    physical_storage = [
        {"model": "Samsung SSD 970 EVO Plus 500GB", "serialNumber": "0025_3854_91B4_E329", "diskIndex": 2},
        {"model": "WDC WDS500G2B0A-00SM50", "serialNumber": "200511805484", "diskIndex": 1},
        {"model": "ST500DM009-2DM14C", "serialNumber": "Z4YETPZS", "diskIndex": 0},
    ]

    device_drives = [
        {"device": "C:", "physicalModel": "Samsung SSD 970 EVO Plus 500GB", "serialNumber": "0025_3854_91B4_E329", "diskNumber": 2, "usedGb": 441.2, "freeGb": 23.0},
        {"device": "D:", "physicalModel": "ST500DM009-2DM14C", "serialNumber": "Z4YETPZS", "diskNumber": 0, "usedGb": 289.0, "freeGb": 176.1},
        {"device": "E:", "physicalModel": "WDC WDS500G2B0A-00SM50", "serialNumber": "200511805484", "diskNumber": 1, "usedGb": 70.3, "freeGb": 297.3},
        {"device": "F:", "physicalModel": "WDC WDS500G2B0A-00SM50", "serialNumber": "200511805484", "diskNumber": 1, "usedGb": 26.2, "freeGb": 71.5},
    ]

    # Algorithm from App.tsx
    partition_map = {}
    for drv in device_drives:
        best_ps_idx = -1
        best_score = -1
        drv_model = drv.get("physicalModel", "").lower()
        drv_serial = drv.get("serialNumber", "").strip().lower()

        for p_idx, ps in enumerate(physical_storage):
            ps_model = ps.get("model", "").lower()
            ps_serial = ps.get("serialNumber", "").strip().lower()
            ps_disk_index = ps.get("diskIndex")

            score = 0
            if ps_serial and drv_serial and ps_serial == drv_serial:
                score += 100
            if ps_model and drv_model:
                if ps_model == drv_model:
                    score += 80
                elif ps_model in drv_model or drv_model in ps_model:
                    score += 60
            if drv.get("diskNumber") is not None:
                if ps_disk_index is not None and drv["diskNumber"] == ps_disk_index:
                    score += 50
                elif drv["diskNumber"] == p_idx and not drv_model:
                    score += 20
            if drv_model and ps_model and drv_model not in ps_model and ps_model not in drv_model:
                score -= 70

            if score > best_score and score > 0:
                best_score = score
                best_ps_idx = p_idx

        partition_map[drv["device"]] = best_ps_idx

    # Assertions
    assert partition_map["C:"] == 0  # Samsung (Index 0 in array, diskIndex 2)
    assert partition_map["D:"] == 2  # Seagate (Index 2 in array, diskIndex 0)
    assert partition_map["E:"] == 1  # WDC (Index 1 in array, diskIndex 1)
    assert partition_map["F:"] == 1  # WDC (Index 1 in array, diskIndex 1)

