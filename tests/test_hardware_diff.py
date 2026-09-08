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
