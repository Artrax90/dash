import pytest
import time
from datetime import datetime, timezone
from backend.app.api.v1.devices import (
    record_telemetry_snapshot,
    device_telemetry_history,
    fleet_telemetry_history,
    log_device_power_event,
    device_power_logs
)

def test_record_telemetry_snapshot_with_top_processes():
    # Clear test telemetry
    device_telemetry_history["PC-TEST-01"] = []
    
    sample_procs = [
        {"pid": 1234, "name": "render.exe", "cpu": 75.5, "ram": 2048},
        {"pid": 5678, "name": "chrome.exe", "cpu": 12.0, "ram": 1024},
        {"pid": 9012, "name": "antivirus.exe", "cpu": 4.5, "ram": 512},
    ]
    
    record_telemetry_snapshot(
        device_id="PC-TEST-01",
        cpu=92,
        ram=70,
        disk=45,
        is_online=True,
        top_processes=sample_procs
    )
    
    pts = device_telemetry_history["PC-TEST-01"]
    assert len(pts) > 0
    latest = pts[-1]
    assert latest["cpu"] == 92
    assert latest["ram"] == 70
    assert "topProcesses" in latest
    assert len(latest["topProcesses"]) == 3
    assert latest["topProcesses"][0]["name"] == "render.exe"
    assert latest["topProcesses"][0]["cpu"] == 75.5

@pytest.mark.anyio
async def test_device_telemetry_history_high_res_and_events():
    from backend.app.api.v1.devices import get_device_telemetry_history
    
    now_ts = time.time()
    # Seed historical points with top processes
    device_telemetry_history["PC-TEST-02"] = [
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "time": now_ts - 1800,  # 30 mins ago
            "deviceId": "PC-TEST-02",
            "cpu": 88,
            "ram": 65,
            "disk": 50,
            "isOnline": True,
            "topProcesses": [
                {"pid": 200, "name": "blender.exe", "cpu": 80.0, "ram": 4096}
            ]
        },
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "time": now_ts - 60,
            "deviceId": "PC-TEST-02",
            "cpu": 15,
            "ram": 40,
            "disk": 50,
            "isOnline": True,
            "topProcesses": [
                {"pid": 300, "name": "explorer.exe", "cpu": 2.0, "ram": 256}
            ]
        }
    ]
    
    # Seed a power event
    log_device_power_event(
        device_id="PC-TEST-02",
        action="REBOOT",
        details="Перезагрузка по расписанию",
        status="Success",
        initiator="Расписание",
        source="SCHEDULE"
    )
    
    res = await get_device_telemetry_history(device_id="PC-TEST-02", time_range="1h")
    assert res["deviceId"] == "PC-TEST-02"
    assert len(res["points"]) >= 20  # High resolution: 25-30 buckets instead of 7
    assert "events" in res
    assert len(res["events"]) > 0
    assert res["events"][0]["action"] == "REBOOT"
    
    # Check that points contain top processes from telemetry
    points_with_procs = [p for p in res["points"] if p.get("topProcesses")]
    assert len(points_with_procs) > 0
    assert points_with_procs[0]["topProcesses"][0]["name"] in ["blender.exe", "explorer.exe"]

@pytest.mark.anyio
async def test_fleet_telemetry_history_high_res_and_top_stressed():
    from backend.app.api.v1.devices import get_fleet_telemetry_history
    from unittest.mock import AsyncMock
    
    mock_db = AsyncMock()
    
    res = await get_fleet_telemetry_history(time_range="1h", group="ALL", db=mock_db)
    assert "points" in res
    assert len(res["points"]) >= 20  # High resolution: 25-30 buckets instead of 7
    # Verify points include maxCpu, activeCount, offlineCount
    first_pt = res["points"][0]
    assert "activeCount" in first_pt
    assert "offlineCount" in first_pt

def test_format_device_summary_contains_drives():
    from backend.app.models.device import Device, PowerStatus
    from backend.app.api.v1.devices import format_device_summary, device_drives_cache

    d = Device(
        id="PC-DISK-01",
        name="Test PC",
        hostname="PC-DISK-01",
        ip_address="192.168.1.100",
        mac_address="00:11:22:33:44:55",
        power_status=PowerStatus.ON,
        disk_usage=55,
        last_seen=datetime.utcnow()
    )

    # 1. Fallback drives when cache is empty
    device_drives_cache.pop("PC-DISK-01", None)
    summary = format_device_summary(d)
    assert "drives" in summary
    assert isinstance(summary["drives"], list)
    assert len(summary["drives"]) >= 1
    assert summary["drives"][0]["device"] == "C:"
    assert summary["drives"][0]["percent"] == 55

    # 2. Live drives when reported by agent
    device_drives_cache["PC-DISK-01"] = [
        {"device": "C:", "volumeName": "System", "sizeGb": 250.0, "usedGb": 120.0, "freeGb": 130.0, "percent": 48},
        {"device": "D:", "volumeName": "Data", "sizeGb": 1000.0, "usedGb": 800.0, "freeGb": 200.0, "percent": 80},
    ]
    summary2 = format_device_summary(d)
    assert len(summary2["drives"]) == 2
    assert summary2["drives"][0]["device"] == "C:"
    assert summary2["drives"][1]["device"] == "D:"
    assert summary2["drives"][1]["sizeGb"] == 1000.0

@pytest.mark.anyio
async def test_agent_heartbeat_updates_device_drives_cache():
    from backend.app.api.v1.agents import agent_heartbeat
    from backend.app.api.v1.devices import device_drives_cache, format_device_summary
    from backend.app.models.device import Device, PowerStatus
    from unittest.mock import AsyncMock, MagicMock

    mock_db = AsyncMock()
    dev = Device(
        id="PC-DISK-02",
        hostname="PC-DISK-02",
        name="Disk PC 2",
        power_status=PowerStatus.ON,
        disk_usage=40,
        last_seen=datetime.utcnow()
    )
    mock_res = MagicMock()
    mock_res.scalars.return_value.first.return_value = dev
    mock_res.scalar_one_or_none.return_value = dev
    mock_db.execute.return_value = mock_res

    payload = {
        "deviceId": "PC-DISK-02",
        "cpu": 15,
        "ram": 50,
        "disk": 40,
        "drives": [
            {"device": "C:", "volumeName": "SystemOS", "fileSystem": "NTFS", "sizeGb": 480.0, "usedGb": 192.0, "freeGb": 288.0, "percent": 40},
            {"device": "E:", "volumeName": "NVMe-Backup", "fileSystem": "NTFS", "sizeGb": 2000.0, "usedGb": 500.0, "freeGb": 1500.0, "percent": 25}
        ]
    }

    resp = await agent_heartbeat(payload=payload, request=MagicMock(), db=mock_db)
    assert resp["status"] == "ok"
    assert "PC-DISK-02" in device_drives_cache
    assert len(device_drives_cache["PC-DISK-02"]) == 2
    assert device_drives_cache["PC-DISK-02"][1]["device"] == "E:"

    summary = format_device_summary(dev)
    assert len(summary["drives"]) == 2
    assert summary["drives"][1]["volumeName"] == "NVMe-Backup"


