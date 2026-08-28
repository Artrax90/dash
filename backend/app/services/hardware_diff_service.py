from typing import Dict, Any, List, Optional
from datetime import datetime

class HardwareDiffService:
    @staticmethod
    def compare_specs(prev_spec: Dict[str, Any], current_spec: Dict[str, Any], device_id: str) -> List[Dict[str, Any]]:
        """
        Compare current hardware snapshot with previous snapshot (or baseline) and generate diff items.
        Triggers an alert on every hardware transition (e.g. RAM removed, RAM restored/added, Disk removed, Disk added).
        """
        if not prev_spec or not current_spec:
            return []

        changes = []
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        ts_suffix = int(datetime.utcnow().timestamp() * 1000) % 1000000
        
        # 1. Compare RAM (Total capacity, slot count, and individual modules)
        if "ram" in prev_spec and "ram" in current_spec:
            base_ram = prev_spec.get("ram", {}) or {}
            curr_ram = current_spec.get("ram", {}) or {}
            base_slots = base_ram.get("slots", []) or []
            curr_slots = curr_ram.get("slots", []) or []
            
            base_ram_total = int(base_ram.get("totalGb") or 0)
            if base_ram_total == 0 and base_slots:
                base_ram_total = sum(int(s.get("sizeGb") or s.get("capacityGb") or 0) for s in base_slots if isinstance(s, dict))
                
            curr_ram_total = int(curr_ram.get("totalGb") or 0)
            if curr_ram_total == 0 and curr_slots:
                curr_ram_total = sum(int(s.get("sizeGb") or s.get("capacityGb") or 0) for s in curr_slots if isinstance(s, dict))

            base_slot_count = len(base_slots)
            curr_slot_count = len(curr_slots)

            # Detect RAM removed (less capacity or fewer sticks)
            if (base_ram_total > 0 and curr_ram_total > 0 and curr_ram_total < base_ram_total) or \
               (base_slot_count > 0 and curr_slot_count > 0 and curr_slot_count < base_slot_count) or \
               (base_slot_count > 0 and curr_slot_count == 0 and base_ram_total > 0):
                changes.append({
                    "id": f"HWC-{device_id}-RAM-REM-{ts_suffix}",
                    "deviceId": device_id,
                    "timestamp": now_str,
                    "component": "RAM",
                    "changeType": "REMOVED",
                    "severity": "Critical",
                    "previousValue": f"{base_ram_total} GB ({base_slot_count} мод.)" if base_slot_count > 0 else f"{base_ram_total} GB",
                    "currentValue": f"{curr_ram_total} GB ({curr_slot_count} мод.)" if curr_slot_count > 0 else f"{curr_ram_total} GB",
                    "description": f"Извлечена оперативная память: {base_ram_total} GB ({base_slot_count} мод.) -> {curr_ram_total} GB ({curr_slot_count} мод.)",
                    "acknowledged": False,
                    "diffStatus": "MISMATCH",
                })
            # Detect RAM added or restored (more capacity or more sticks)
            elif (base_ram_total > 0 and curr_ram_total > 0 and curr_ram_total > base_ram_total) or \
                 (base_slot_count > 0 and curr_slot_count > 0 and curr_slot_count > base_slot_count) or \
                 (base_slot_count == 0 and curr_slot_count > 0 and curr_ram_total > 0):
                changes.append({
                    "id": f"HWC-{device_id}-RAM-ADD-{ts_suffix}",
                    "deviceId": device_id,
                    "timestamp": now_str,
                    "component": "RAM",
                    "changeType": "ADDED",
                    "severity": "Warning",
                    "previousValue": f"{base_ram_total} GB ({base_slot_count} мод.)" if base_slot_count > 0 else f"{base_ram_total} GB",
                    "currentValue": f"{curr_ram_total} GB ({curr_slot_count} мод.)" if curr_slot_count > 0 else f"{curr_ram_total} GB",
                    "description": f"Установлена/возвращена оперативная память: {base_ram_total} GB ({base_slot_count} мод.) -> {curr_ram_total} GB ({curr_slot_count} мод.)",
                    "acknowledged": False,
                    "diffStatus": "MISMATCH",
                })
            # Detect RAM module replacement (same count & capacity, different serials)
            elif base_slot_count > 0 and base_slot_count == curr_slot_count and base_ram_total == curr_ram_total:
                base_sns = {s.get("serialNumber") for s in base_slots if isinstance(s, dict) and s.get("serialNumber") and not str(s.get("serialNumber")).startswith("RAM-")}
                curr_sns = {s.get("serialNumber") for s in curr_slots if isinstance(s, dict) and s.get("serialNumber") and not str(s.get("serialNumber")).startswith("RAM-")}
                if base_sns and curr_sns and base_sns != curr_sns:
                    changes.append({
                        "id": f"HWC-{device_id}-RAM-MOD-{ts_suffix}",
                        "deviceId": device_id,
                        "timestamp": now_str,
                        "component": "RAM",
                        "changeType": "REPLACED",
                        "severity": "Warning",
                        "previousValue": f"{base_ram_total} GB (S/N: {', '.join(base_sns)})",
                        "currentValue": f"{curr_ram_total} GB (S/N: {', '.join(curr_sns)})",
                        "description": f"Заменен модуль оперативной памяти: {', '.join(base_sns)} -> {', '.join(curr_sns)}",
                        "acknowledged": False,
                        "diffStatus": "MISMATCH",
                    })

        # 2. Compare Disks (by serial numbers) - only if storage list is populated in BOTH prev & current
        base_storage = prev_spec.get("storage", []) or []
        curr_storage = current_spec.get("storage", []) or []

        if isinstance(base_storage, list) and isinstance(curr_storage, list) and len(base_storage) > 0 and len(curr_storage) > 0:
            base_disks = {d.get("serialNumber"): d for d in base_storage if isinstance(d, dict) and d.get("serialNumber") and not str(d.get("serialNumber")).startswith("DISK-SN-")}
            curr_disks = {d.get("serialNumber"): d for d in curr_storage if isinstance(d, dict) and d.get("serialNumber") and not str(d.get("serialNumber")).startswith("DISK-SN-")}
            
            if base_disks and curr_disks:
                for sn, d in base_disks.items():
                    if sn not in curr_disks:
                        changes.append({
                            "id": f"HWC-{device_id}-DISK-REM-{sn[:8]}-{ts_suffix}",
                            "deviceId": device_id,
                            "timestamp": now_str,
                            "component": "Storage",
                            "changeType": "REMOVED",
                            "severity": "Critical",
                            "previousValue": f"{d.get('model', 'Накопитель')} (S/N: {sn})",
                            "currentValue": "Отсутствует / Извлечен",
                            "description": f"Извлечен накопитель: {d.get('model', 'Накопитель')} (S/N: {sn})",
                            "acknowledged": False,
                            "diffStatus": "MISMATCH",
                        })
                        
                for sn, d in curr_disks.items():
                    if sn not in base_disks:
                        changes.append({
                            "id": f"HWC-{device_id}-DISK-ADD-{sn[:8]}-{ts_suffix}",
                            "deviceId": device_id,
                            "timestamp": now_str,
                            "component": "Storage",
                            "changeType": "ADDED",
                            "severity": "Warning",
                            "previousValue": "Отсутствует",
                            "currentValue": f"{d.get('model', 'Накопитель')} (S/N: {sn})",
                            "description": f"Подключен новый накопитель: {d.get('model', 'Накопитель')} (S/N: {sn})",
                            "acknowledged": False,
                            "diffStatus": "MISMATCH",
                        })

        # 3. Compare GPU (Additions, Removals, Replacements)
        base_gpus_raw = prev_spec.get("gpus", []) or []
        curr_gpus_raw = current_spec.get("gpus", []) or []

        if isinstance(base_gpus_raw, list) and isinstance(curr_gpus_raw, list) and (len(base_gpus_raw) > 0 or len(curr_gpus_raw) > 0):
            base_gpus = sorted([g.get("model").strip() for g in base_gpus_raw if isinstance(g, dict) and g.get("model") and "Basic" not in g.get("model")])
            curr_gpus = sorted([g.get("model").strip() for g in curr_gpus_raw if isinstance(g, dict) and g.get("model") and "Basic" not in g.get("model")])
            
            if base_gpus != curr_gpus:
                if len(curr_gpus) > len(base_gpus):
                    added = [g for g in curr_gpus if g not in base_gpus] or curr_gpus
                    changes.append({
                        "id": f"HWC-{device_id}-GPU-ADD-{ts_suffix}",
                        "deviceId": device_id,
                        "timestamp": now_str,
                        "component": "GPU",
                        "changeType": "ADDED",
                        "severity": "Warning",
                        "previousValue": ", ".join(base_gpus) or "Отсутствует",
                        "currentValue": ", ".join(curr_gpus),
                        "description": f"Установлена дополнительная видеокарта: {', '.join(added)}",
                        "acknowledged": False,
                        "diffStatus": "MISMATCH",
                    })
                elif len(curr_gpus) < len(base_gpus):
                    removed = [g for g in base_gpus if g not in curr_gpus] or base_gpus
                    changes.append({
                        "id": f"HWC-{device_id}-GPU-REM-{ts_suffix}",
                        "deviceId": device_id,
                        "timestamp": now_str,
                        "component": "GPU",
                        "changeType": "REMOVED",
                        "severity": "Critical",
                        "previousValue": ", ".join(base_gpus),
                        "currentValue": ", ".join(curr_gpus) or "Отсутствует",
                        "description": f"Извлечена видеокарта: {', '.join(removed)}",
                        "acknowledged": False,
                        "diffStatus": "MISMATCH",
                    })
                else:
                    changes.append({
                        "id": f"HWC-{device_id}-GPU-MOD-{ts_suffix}",
                        "deviceId": device_id,
                        "timestamp": now_str,
                        "component": "GPU",
                        "changeType": "MODIFIED",
                        "severity": "Critical",
                        "previousValue": ", ".join(base_gpus) or "None",
                        "currentValue": ", ".join(curr_gpus) or "None",
                        "description": f"Замена видеокарты: {', '.join(base_gpus)} -> {', '.join(curr_gpus)}",
                        "acknowledged": False,
                        "diffStatus": "MISMATCH",
                    })

        # 4. Compare CPU (Processor replacement)
        base_cpu = prev_spec.get("cpu", {}) or {}
        curr_cpu = current_spec.get("cpu", {}) or {}
        base_cpu_model = (base_cpu.get("model") or "").strip()
        curr_cpu_model = (curr_cpu.get("model") or "").strip()

        if base_cpu_model and curr_cpu_model and base_cpu_model != curr_cpu_model:
            changes.append({
                "id": f"HWC-{device_id}-CPU-{ts_suffix}",
                "deviceId": device_id,
                "timestamp": now_str,
                "component": "CPU",
                "changeType": "MODIFIED",
                "severity": "Critical",
                "previousValue": base_cpu_model,
                "currentValue": curr_cpu_model,
                "description": f"Замена процессора: {base_cpu_model} -> {curr_cpu_model}",
                "acknowledged": False,
                "diffStatus": "MISMATCH",
            })

        # 5. Compare Motherboard (System board replacement)
        base_mb = prev_spec.get("motherboard", {}) or {}
        curr_mb = current_spec.get("motherboard", {}) or {}
        base_mb_model = (base_mb.get("model") or "").strip()
        curr_mb_model = (curr_mb.get("model") or "").strip()

        if base_mb_model and curr_mb_model and base_mb_model != curr_mb_model and base_mb_model not in ["Motherboard", "Default string", "To be filled by O.E.M."]:
            changes.append({
                "id": f"HWC-{device_id}-MB-{ts_suffix}",
                "deviceId": device_id,
                "timestamp": now_str,
                "component": "Motherboard",
                "changeType": "MODIFIED",
                "severity": "Critical",
                "previousValue": f"{base_mb.get('manufacturer', '')} {base_mb_model}".strip(),
                "currentValue": f"{curr_mb.get('manufacturer', '')} {curr_mb_model}".strip(),
                "description": f"Замена материнской платы: {base_mb_model} -> {curr_mb_model}",
                "acknowledged": False,
                "diffStatus": "MISMATCH",
            })

        # 6. Compare PCI / PCIe Expansion Devices (Network cards, capture cards, sound cards, NVMe controllers, adapters)
        base_pci = prev_spec.get("pciDevices") or prev_spec.get("pci_devices") or prev_spec.get("pci") or []
        curr_pci = current_spec.get("pciDevices") or current_spec.get("pci_devices") or current_spec.get("pci") or []

        def is_ignored_pci(p):
            if not p:
                return True
            name = str(p.get("name") or "").lower() if isinstance(p, dict) else str(p).lower()
            pclass = str(p.get("class") or "").lower() if isinstance(p, dict) else ""
            return any(ign in name or ign in pclass for ign in [
                "мост", "bridge", "root port", "root complex", "dma", "direct memory",
                "таймер", "timer", "interrupt", "чипсет", "chipset", "host cpu",
                "system board", "системн", "espi", "spi flash", "management engine",
                "smbus", "serial io", "sram", "system peripheral", "signal processing"
            ])

        base_pci_clean = [p for p in base_pci if not is_ignored_pci(p)] if isinstance(base_pci, list) else []
        curr_pci_clean = [p for p in curr_pci if not is_ignored_pci(p)] if isinstance(curr_pci, list) else []

        if base_pci_clean or curr_pci_clean:
            def pci_key(item):
                if isinstance(item, dict):
                    return (item.get("pnpDeviceId") or item.get("deviceId") or item.get("name") or "").strip().upper()
                return str(item).strip().upper()

            base_pci_dict = {pci_key(p): p for p in base_pci_clean if pci_key(p)}
            curr_pci_dict = {pci_key(p): p for p in curr_pci_clean if pci_key(p)}

            for k, p in base_pci_dict.items():
                if k not in curr_pci_dict:
                    name = p.get("name") if isinstance(p, dict) else str(p)
                    changes.append({
                        "id": f"HWC-{device_id}-PCI-REM-{ts_suffix}",
                        "deviceId": device_id,
                        "timestamp": now_str,
                        "component": "PCI Device",
                        "changeType": "REMOVED",
                        "severity": "Critical",
                        "previousValue": name,
                        "currentValue": "Отсутствует / Извлечено",
                        "description": f"Извлечено PCI-устройство: {name}",
                        "acknowledged": False,
                        "diffStatus": "MISMATCH",
                    })

            for k, p in curr_pci_dict.items():
                if k not in base_pci_dict:
                    name = p.get("name") if isinstance(p, dict) else str(p)
                    changes.append({
                        "id": f"HWC-{device_id}-PCI-ADD-{ts_suffix}",
                        "deviceId": device_id,
                        "timestamp": now_str,
                        "component": "PCI Device",
                        "changeType": "ADDED",
                        "severity": "Warning",
                        "previousValue": "Отсутствует",
                        "currentValue": name,
                        "description": f"Подключено новое PCI-устройство: {name}",
                        "acknowledged": False,
                        "diffStatus": "MISMATCH",
                    })

        # 7. Compare Network Adapters (Physical network cards, Wi-Fi, 10G cards)
        base_net = prev_spec.get("network") or []
        curr_net = current_spec.get("network") or []

        if isinstance(base_net, list) and isinstance(curr_net, list) and (len(base_net) > 0 or len(curr_net) > 0):
            def net_key(n):
                if isinstance(n, dict):
                    return (n.get("mac") or n.get("macAddress") or n.get("name") or "").strip().upper()
                return str(n).strip().upper()

            base_net_dict = {net_key(n): n for n in base_net if net_key(n) and "LOOPBACK" not in str(n).upper()}
            curr_net_dict = {net_key(n): n for n in curr_net if net_key(n) and "LOOPBACK" not in str(n).upper()}

            for k, n in base_net_dict.items():
                if k not in curr_net_dict:
                    name = n.get("name") if isinstance(n, dict) else str(n)
                    changes.append({
                        "id": f"HWC-{device_id}-NET-REM-{ts_suffix}",
                        "deviceId": device_id,
                        "timestamp": now_str,
                        "component": "Network",
                        "changeType": "REMOVED",
                        "severity": "Critical",
                        "previousValue": f"{name} ({k})",
                        "currentValue": "Отсутствует / Отключено",
                        "description": f"Отключен сетевой адаптер: {name} ({k})",
                        "acknowledged": False,
                        "diffStatus": "MISMATCH",
                    })

            for k, n in curr_net_dict.items():
                if k not in base_net_dict:
                    name = n.get("name") if isinstance(n, dict) else str(n)
                    changes.append({
                        "id": f"HWC-{device_id}-NET-ADD-{ts_suffix}",
                        "deviceId": device_id,
                        "timestamp": now_str,
                        "component": "Network",
                        "changeType": "ADDED",
                        "severity": "Warning",
                        "previousValue": "Отсутствует",
                        "currentValue": f"{name} ({k})",
                        "description": f"Подключен новый сетевой адаптер: {name} ({k})",
                        "acknowledged": False,
                        "diffStatus": "MISMATCH",
                    })

        return changes

hardware_diff_service = HardwareDiffService()

