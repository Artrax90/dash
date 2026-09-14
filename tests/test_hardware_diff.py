import pytest
from backend.app.services.hardware_diff_service import hardware_diff_service

def test_usb_flash_drive_does_not_trigger_hardware_mismatch():
    base_spec = {
        "storage": [
            {
                "id": "disk-0",
                "model": "Samsung SSD 980 PRO 1TB",
                "serialNumber": "S5GXNF0R123456",
                "capacityGb": 1000,
                "busType": "NVMe",
                "isRemovable": False,
            }
        ]
    }

    # Current spec with USB flash drive inserted
    curr_spec_with_usb = {
        "storage": [
            {
                "id": "disk-0",
                "model": "Samsung SSD 980 PRO 1TB",
                "serialNumber": "S5GXNF0R123456",
                "capacityGb": 1000,
                "busType": "NVMe",
                "isRemovable": False,
            },
            {
                "id": "disk-1",
                "model": "Kingston DataTraveler 3.0 USB Device",
                "serialNumber": "00187D0958EE",
                "capacityGb": 32,
                "busType": "USB",
                "isRemovable": True,
                "mediaType": "Removable Media",
            }
        ]
    }

    changes = hardware_diff_service.compare_specs(base_spec, curr_spec_with_usb, "DEV-001")
    
    # USB insertions must NOT be marked as MISMATCH!
    mismatches = [c for c in changes if c.get("diffStatus") == "MISMATCH"]
    assert len(mismatches) == 0, f"Expected 0 mismatches for USB drive, got {mismatches}"
    
    # If reported as a change, it should be marked with diffStatus INFO and severity Info
    usb_changes = [c for c in changes if c.get("isUsb") or c.get("component") == "USB-накопитель"]
    for c in usb_changes:
        assert c.get("diffStatus") != "MISMATCH", "USB change must not be MISMATCH"
        assert c.get("severity") == "Info", "USB change severity must be Info"

def test_internal_disk_removal_triggers_critical_mismatch():
    base_spec = {
        "storage": [
            {
                "id": "disk-0",
                "model": "Samsung SSD 980 PRO 1TB",
                "serialNumber": "S5GXNF0R123456",
                "capacityGb": 1000,
                "busType": "NVMe",
                "isRemovable": False,
            }
        ]
    }
    curr_spec_missing_disk = {
        "storage": [
            {
                "id": "disk-1",
                "model": "Kingston DataTraveler 3.0",
                "serialNumber": "00187D0958EE",
                "capacityGb": 32,
                "busType": "USB",
                "isRemovable": True,
            }
        ]
    }
    changes = hardware_diff_service.compare_specs(base_spec, curr_spec_missing_disk, "DEV-001")
    disk_mismatches = [c for c in changes if c.get("diffStatus") == "MISMATCH" and c.get("component") == "Storage"]
    assert len(disk_mismatches) == 1
    assert disk_mismatches[0]["changeType"] == "REMOVED"
    assert disk_mismatches[0]["severity"] == "Critical"

def test_multiple_network_adapters_diff_generates_unique_ids():
    base_spec = {
        "network": [
            {"name": "vEthernet (Default Switch)", "mac": "00:15:5D:85:08:62"},
            {"name": "Беспроводная сеть", "mac": "E4:0D:36:A5:64:00"},
            {"name": "Ethernet", "mac": "00:58:3F:15:1E:FE"},
        ]
    }
    curr_spec = {
        "network": [
            {"name": "Ethernet", "mac": "00:58:3F:15:1E:FE"}
        ]
    }
    changes = hardware_diff_service.compare_specs(base_spec, curr_spec, "PC-1EFE")
    assert len(changes) == 2
    ids = [c["id"] for c in changes]
    assert len(set(ids)) == len(ids), f"Duplicate change IDs generated: {ids}"
    for cid in ids:
        assert len(cid) <= 100, f"ID exceeded 100 chars limit: {cid}"

def test_multiple_pci_devices_diff_generates_unique_ids():
    base_spec = {
        "pciDevices": [
            {"name": "NVIDIA GeForce RTX 4080", "deviceId": "PCI\\VEN_10DE&DEV_2704"},
            {"name": "Intel Wi-Fi 6E AX211", "deviceId": "PCI\\VEN_8086&DEV_7AF0"},
        ]
    }
    curr_spec = {
        "pciDevices": []
    }
    changes = hardware_diff_service.compare_specs(base_spec, curr_spec, "PC-TEST")
    assert len(changes) == 2
    ids = [c["id"] for c in changes]
    assert len(set(ids)) == len(ids)
    for cid in ids:
        assert len(cid) <= 100

def test_scoped_admin_group_path_resolution():
    from backend.app.core.scope import is_path_in_scope

    allowed_groups = ["мнок"]

    # Target path inside allowed building scope
    assert is_path_in_scope("МНОК / 4 / 443Т", allowed_groups) is True
    assert is_path_in_scope("МНОК / 1 этаж / 101", allowed_groups) is True
    assert is_path_in_scope("МНОК", allowed_groups) is True

    # Target path outside allowed scope
    assert is_path_in_scope("Главный корпус / 4 / 443Т", allowed_groups) is False
    assert is_path_in_scope("Учебный корпус / 2 этаж / 205", allowed_groups) is False


