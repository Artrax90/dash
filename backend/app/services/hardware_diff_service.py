from typing import Dict, Any, List, Optional
from datetime import datetime

class HardwareDiffService:
    @staticmethod
    def compare_specs(baseline_spec: Dict[str, Any], current_spec: Dict[str, Any], device_id: str) -> List[Dict[str, Any]]:
        """
        Compare current hardware snapshot with approved baseline and generate diff items.
        """
        changes = []
        
        # 1. Compare RAM
        base_ram = baseline_spec.get("ram", {})
        curr_ram = current_spec.get("ram", {})
        base_ram_total = base_ram.get("totalGb", 0)
        curr_ram_total = curr_ram.get("totalGb", 0)
        
        if curr_ram_total < base_ram_total:
            changes.append({
                "id": f"HWC-{int(datetime.utcnow().timestamp())}-RAM",
                "deviceId": device_id,
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "component": "RAM",
                "changeType": "REMOVED",
                "severity": "Critical",
                "previousValue": f"{base_ram_total} GB ({len(base_ram.get('slots', []))} slots)",
                "currentValue": f"{curr_ram_total} GB ({len(curr_ram.get('slots', []))} slots)",
                "acknowledged": False,
                "diffStatus": "MISMATCH",
            })
        elif curr_ram_total > base_ram_total:
            changes.append({
                "id": f"HWC-{int(datetime.utcnow().timestamp())}-RAM",
                "deviceId": device_id,
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "component": "RAM",
                "changeType": "ADDED",
                "severity": "Info",
                "previousValue": f"{base_ram_total} GB",
                "currentValue": f"{curr_ram_total} GB",
                "acknowledged": False,
                "diffStatus": "MISMATCH",
            })

        # 2. Compare Disks (by serial numbers)
        base_disks = {d.get("serialNumber"): d for d in baseline_spec.get("storage", []) if d.get("serialNumber")}
        curr_disks = {d.get("serialNumber"): d for d in current_spec.get("storage", []) if d.get("serialNumber")}
        
        for sn, d in base_disks.items():
            if sn not in curr_disks:
                changes.append({
                    "id": f"HWC-{int(datetime.utcnow().timestamp())}-DISK-REM",
                    "deviceId": device_id,
                    "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                    "component": "Storage",
                    "changeType": "REMOVED",
                    "severity": "Critical",
                    "previousValue": f"{d.get('model')} (S/N: {sn})",
                    "currentValue": "Missing / Removed",
                    "acknowledged": False,
                    "diffStatus": "MISMATCH",
                })
                
        for sn, d in curr_disks.items():
            if sn not in base_disks:
                changes.append({
                    "id": f"HWC-{int(datetime.utcnow().timestamp())}-DISK-ADD",
                    "deviceId": device_id,
                    "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                    "component": "Storage",
                    "changeType": "ADDED",
                    "severity": "Warning",
                    "previousValue": "None",
                    "currentValue": f"{d.get('model')} (S/N: {sn})",
                    "acknowledged": False,
                    "diffStatus": "MISMATCH",
                })

        # 3. Compare GPU
        base_gpus = [g.get("model") for g in baseline_spec.get("gpus", [])]
        curr_gpus = [g.get("model") for g in current_spec.get("gpus", [])]
        if base_gpus != curr_gpus:
            changes.append({
                "id": f"HWC-{int(datetime.utcnow().timestamp())}-GPU",
                "deviceId": device_id,
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "component": "GPU",
                "changeType": "MODIFIED",
                "severity": "Critical",
                "previousValue": ", ".join(base_gpus) or "None",
                "currentValue": ", ".join(curr_gpus) or "None",
                "acknowledged": False,
                "diffStatus": "MISMATCH",
            })

        return changes

hardware_diff_service = HardwareDiffService()
