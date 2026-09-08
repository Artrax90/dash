import pytest
from backend.app.services.hardware_diff_service import hardware_diff_service, HardwareDiffService
from backend.app.services.alert_engine import AlertEngine

def test_remote_display_adapter_does_not_trigger_hardware_mismatch():
    base_spec = {
        "gpus": [
            {"model": "NVIDIA GeForce RTX 3060", "vendor": "NVIDIA", "memoryGb": 12}
        ]
    }

    # When connected via RDP, Windows adds "Microsoft Remote Display Adapter"
    curr_spec_rdp = {
        "gpus": [
            {"model": "NVIDIA GeForce RTX 3060", "vendor": "NVIDIA", "memoryGb": 12},
            {"model": "Microsoft Remote Display Adapter", "vendor": "Microsoft", "memoryGb": 0}
        ]
    }

    changes = hardware_diff_service.compare_specs(base_spec, curr_spec_rdp, "DEV-001")

    # Mismatches must be 0! RDP virtual display must NOT be treated as a physical GPU addition
    mismatches = [c for c in changes if c.get("diffStatus") == "MISMATCH"]
    assert len(mismatches) == 0, f"Expected 0 mismatches for RDP adapter, got {mismatches}"

    # If change is recorded, it must be INFO / Info severity with isVirtualGpu=True
    v_changes = [c for c in changes if c.get("isVirtualGpu") or "RDP" in c.get("component", "")]
    for c in v_changes:
        assert c.get("diffStatus") != "MISMATCH"
        assert c.get("severity") == "Info"

def test_physical_gpu_addition_triggers_warning_mismatch():
    base_spec = {
        "gpus": [
            {"model": "NVIDIA GeForce RTX 3060", "vendor": "NVIDIA", "memoryGb": 12}
        ]
    }
    curr_spec_with_gpu = {
        "gpus": [
            {"model": "NVIDIA GeForce RTX 3060", "vendor": "NVIDIA", "memoryGb": 12},
            {"model": "NVIDIA GeForce RTX 4070", "vendor": "NVIDIA", "memoryGb": 12}
        ]
    }

    changes = hardware_diff_service.compare_specs(base_spec, curr_spec_with_gpu, "DEV-001")
    mismatches = [c for c in changes if c.get("diffStatus") == "MISMATCH"]
    assert len(mismatches) == 1
    assert mismatches[0]["component"] == "GPU"
    assert "RTX 4070" in mismatches[0]["description"]

def test_is_virtual_gpu_helper():
    assert HardwareDiffService.is_virtual_gpu("Microsoft Remote Display Adapter") is True
    assert HardwareDiffService.is_virtual_gpu({"model": "Microsoft Remote Display Adapter"}) is True
    assert HardwareDiffService.is_virtual_gpu("Remote Display Adapter") is True
    assert HardwareDiffService.is_virtual_gpu("Citrix Indirect Display Adapter") is True
    assert HardwareDiffService.is_virtual_gpu("Parsec Virtual Display Adapter") is True
    assert HardwareDiffService.is_virtual_gpu("Microsoft Basic Display Adapter") is True
    assert HardwareDiffService.is_virtual_gpu("NVIDIA GeForce RTX 3060") is False
    assert HardwareDiffService.is_virtual_gpu("AMD Radeon RX 6700 XT") is False
    assert HardwareDiffService.is_virtual_gpu("Intel UHD Graphics 630") is False

def test_alert_engine_suppresses_virtual_gpu_by_default():
    # Default policy with empty eventsConfig
    policy = {"mode": "Full", "events_config": {}}
    assert AlertEngine.should_notify("VIRTUAL_GPU_CHANGED", policy) is False

    # When explicitly enabled via toggle
    policy_enabled = {"mode": "Custom", "events_config": {"remoteDisplayAdapter": True}}
    assert AlertEngine.should_notify("VIRTUAL_GPU_CHANGED", policy_enabled) is True
