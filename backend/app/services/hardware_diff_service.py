from typing import Dict, Any, List, Optional
from datetime import datetime

class HardwareDiffService:
    @staticmethod
    def compare_specs(baseline_spec: Dict[str, Any], current_spec: Dict[str, Any], device_id: str) -> List[Dict[str, Any]]:
        """
        Compare current hardware snapshot with approved baseline and generate diff items safely.
        Avoids false positives when partial hardware snapshots are sent.
        """
        if not baseline_spec or not current_spec:
            return []

        changes = []
        
        # 1. Compare RAM (Total capacity, slot count, and individual modules)
        if "ram" in baseline_spec and "ram" in current_spec:
            base_ram = baseline_spec.get("ram", {}) or {}
            curr_ram = current_spec.get("ram", {}) or {}
            base_ram_total = int(base_ram.get("totalGb") or 0)
            curr_ram_total = int(curr_ram.get("totalGb") or 0)
            base_slots = base_ram.get("slots", []) or []
            curr_slots = curr_ram.get("slots", []) or []
            
            base_slot_count = len(base_slots)
            curr_slot_count = len(curr_slots)

            if base_ram_total > 0 and curr_ram_total > 0:
                if curr_ram_total < base_ram_total or (base_slot_count > 0 and curr_slot_count > 0 and curr_slot_count < base_slot_count):
                    changes.append({
                        "id": f"HWC-{device_id}-RAM-REM",
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
                elif curr_ram_total > base_ram_total or (base_slot_count > 0 and curr_slot_count > 0 and curr_slot_count > base_slot_count):
                    changes.append({
                        "id": f"HWC-{device_id}-RAM-ADD",
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

        # 2. Compare Disks (by serial numbers) - only if storage list is populated in BOTH baseline & current
        base_storage = baseline_spec.get("storage", []) or []
        curr_storage = current_spec.get("storage", []) or []

        if isinstance(base_storage, list) and isinstance(curr_storage, list) and len(base_storage) > 0 and len(curr_storage) > 0:
            base_disks = {d.get("serialNumber"): d for d in base_storage if isinstance(d, dict) and d.get("serialNumber") and not str(d.get("serialNumber")).startswith("DISK-SN-")}
            curr_disks = {d.get("serialNumber"): d for d in curr_storage if isinstance(d, dict) and d.get("serialNumber") and not str(d.get("serialNumber")).startswith("DISK-SN-")}
            
            if base_disks and curr_disks:
                for sn, d in base_disks.items():
                    if sn not in curr_disks:
                        changes.append({
                            "id": f"HWC-{device_id}-DISK-REM-{sn[:8]}",
                            "deviceId": device_id,
                            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                            "component": "Storage",
                            "changeType": "REMOVED",
                            "severity": "Critical",
                            "previousValue": f"{d.get('model', 'Накопитель')} (S/N: {sn})",
                            "currentValue": "Отсутствует / Извлечен",
                            "acknowledged": False,
                            "diffStatus": "MISMATCH",
                        })
                        
                for sn, d in curr_disks.items():
                    if sn not in base_disks:
                        changes.append({
                            "id": f"HWC-{device_id}-DISK-ADD-{sn[:8]}",
                            "deviceId": device_id,
                            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                            "component": "Storage",
                            "changeType": "ADDED",
                            "severity": "Warning",
                            "previousValue": "Отсутствует",
                            "currentValue": f"{d.get('model', 'Накопитель')} (S/N: {sn})",
                            "acknowledged": False,
                            "diffStatus": "MISMATCH",
                        })

        # 3. Compare GPU - only if GPUs list is populated in BOTH baseline & current
        base_gpus_raw = baseline_spec.get("gpus", []) or []
        curr_gpus_raw = current_spec.get("gpus", []) or []

        if isinstance(base_gpus_raw, list) and isinstance(curr_gpus_raw, list) and len(base_gpus_raw) > 0 and len(curr_gpus_raw) > 0:
            base_gpus = sorted([g.get("model") for g in base_gpus_raw if isinstance(g, dict) and g.get("model") and "Basic" not in g.get("model")])
            curr_gpus = sorted([g.get("model") for g in curr_gpus_raw if isinstance(g, dict) and g.get("model") and "Basic" not in g.get("model")])
            
            if base_gpus and curr_gpus and base_gpus != curr_gpus:
                changes.append({
                    "id": f"HWC-{device_id}-GPU",
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

