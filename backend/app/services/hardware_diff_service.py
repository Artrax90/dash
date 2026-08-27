from typing import Dict, Any, List, Optional
from datetime import datetime

class HardwareDiffService:
    @staticmethod
    def compare_specs(baseline_spec: Dict[str, Any], current_spec: Dict[str, Any], device_id: str) -> List[Dict[str, Any]]:
        """
        Compare current hardware snapshot with approved baseline and generate diff items.
        """
        changes = []
        
        # 1. Compare RAM (Total capacity, slot count, and individual modules)
        base_ram = baseline_spec.get("ram", {}) if baseline_spec else {}
        curr_ram = current_spec.get("ram", {}) if current_spec else {}
        base_ram_total = base_ram.get("totalGb", 0)
        curr_ram_total = curr_ram.get("totalGb", 0)
        base_slots = base_ram.get("slots", []) or []
        curr_slots = curr_ram.get("slots", []) or []
        
        base_slot_count = len(base_slots)
        curr_slot_count = len(curr_slots)

        if (curr_ram_total < base_ram_total and base_ram_total > 0) or (base_slot_count > 0 and curr_slot_count < base_slot_count):
            changes.append({
                "id": f"HWC-{int(datetime.utcnow().timestamp())}-RAM-REM",
                "deviceId": device_id,
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "component": "RAM",
                "changeType": "REMOVED",
                "severity": "Critical",
                "previousValue": f"{base_ram_total} GB ({base_slot_count} модуля)" if base_slot_count > 0 else f"{base_ram_total} GB",
                "currentValue": f"{curr_ram_total} GB ({curr_slot_count} модуля)" if curr_slot_count > 0 else f"{curr_ram_total} GB",
                "acknowledged": False,
                "diffStatus": "MISMATCH",
            })
        elif (curr_ram_total > base_ram_total and base_ram_total > 0) or (base_slot_count > 0 and curr_slot_count > base_slot_count):
            changes.append({
                "id": f"HWC-{int(datetime.utcnow().timestamp())}-RAM-ADD",
                "deviceId": device_id,
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "component": "RAM",
                "changeType": "ADDED",
                "severity": "Info",
                "previousValue": f"{base_ram_total} GB ({base_slot_count} модуля)" if base_slot_count > 0 else f"{base_ram_total} GB",
                "currentValue": f"{curr_ram_total} GB ({curr_slot_count} модуля)" if curr_slot_count > 0 else f"{curr_ram_total} GB",
                "acknowledged": False,
                "diffStatus": "MISMATCH",
            })
        elif curr_ram_total != base_ram_total and base_ram_total > 0:
            changes.append({
                "id": f"HWC-{int(datetime.utcnow().timestamp())}-RAM-MOD",
                "deviceId": device_id,
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "component": "RAM",
                "changeType": "MODIFIED",
                "severity": "Warning",
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
