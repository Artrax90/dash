import pytest
import time
from datetime import datetime, timedelta
from starlette.requests import Request
from sqlalchemy import select, delete

from backend.app.api.v1.agents import (
    agent_heartbeat,
    report_inventory
)
from backend.app.db.session import AsyncSessionLocal
from backend.app.models.device import Device, PowerStatus, AgentStatus, HealthStatus
from backend.app.models.alert import AlertModel
from backend.app.services.alert_engine import alert_engine, AlertEngine


@pytest.mark.anyio
async def test_startup_inventory_then_heartbeat_triggers_online_alert():
    """
    Demonstrates the bug:
    When a PC wakes up (e.g. from schedule):
    1. It was PowerStatus.OFF with an active OFFLINE alert.
    2. The agent starts and immediately calls /inventory.
    3. The agent then calls /heartbeat with isStartup=True.
    
    Expected:
    trigger_device_online MUST be invoked, resolving the open OFFLINE alert
    and updating the device state tracker to ONLINE.
    """
    test_dev_id = "TEST-PC-ONLINE-001"
    clean_id = test_dev_id.upper()
    
    # Setup tracker state as OFFLINE for 8 minutes (like 10:50 to 10:58)
    AlertEngine._device_state_tracker[clean_id] = {
        "state": "OFFLINE",
        "last_offline_time": time.time() - 480,
        "last_online_time": 0,
        "last_offline_alert_ts": time.time() - 480,
        "last_online_alert_ts": 0
    }

    async with AsyncSessionLocal() as db:
        try:
            # Ensure clean database state
            await db.execute(delete(AlertModel).where(AlertModel.device_id == test_dev_id))
            await db.execute(delete(Device).where(Device.id == test_dev_id))
            
            # Create device in OFF state
            dev = Device(
                id=test_dev_id,
                name="Test Online PC",
                hostname=test_dev_id,
                ip_address="192.168.1.205",
                mac_address="AA:BB:CC:DD:EE:01",
                os_type="Windows",
                os_version="Windows 10 Pro",
                agent_version="2.9.16",
                power_status=PowerStatus.OFF,
                agent_status=AgentStatus.DISCONNECTED,
                health_status=HealthStatus.HEALTHY,
                group_name="Office",
                last_seen=datetime.utcnow() - timedelta(minutes=8)
            )
            db.add(dev)
            
            # Create open OFFLINE alert
            alert = AlertModel(
                id=f"ALT-OFF-{test_dev_id}-12345",
                device_id=test_dev_id,
                alert_type="OFFLINE",
                severity="Warning",
                description="Связь с агентом прервана",
                state="Open",
                created_at=datetime.utcnow() - timedelta(minutes=8)
            )
            db.add(alert)
            await db.commit()

            # 1. Agent starts and calls /inventory first (as in Invoke-Heartbeat $true)
            inv_payload = {
                "deviceId": test_dev_id,
                "hostname": test_dev_id,
                "mac": "AA:BB:CC:DD:EE:01",
                "hardwareSpec": {"cpu": "Core i7", "ram": {"totalGb": 16}}
            }
            await report_inventory(inv_payload, db)

            # 2. Agent immediately calls /heartbeat with isStartup=True
            scope = {'type': 'http', 'client': ('192.168.1.205', 54321), 'headers': []}
            req = Request(scope)
            hb_payload = {
                "deviceId": test_dev_id,
                "hostname": test_dev_id,
                "mac": "AA:BB:CC:DD:EE:01",
                "isStartup": True,
                "uptime": "Только что",
                "uptimeSeconds": 15,
                "cpu": 10,
                "ram": 25,
                "disk": 30
            }
            await agent_heartbeat(hb_payload, req, db)

            # Verification:
            # AlertEngine tracker must be marked ONLINE
            assert AlertEngine._device_state_tracker[clean_id]["state"] == "ONLINE", (
                f"Expected tracker state to be ONLINE, but was {AlertEngine._device_state_tracker[clean_id]['state']}"
            )

            # Open alert must be Resolved
            alt_res = await db.execute(select(AlertModel).where(AlertModel.device_id == test_dev_id))
            saved_alert = alt_res.scalars().first()
            assert saved_alert is not None
            assert saved_alert.state == "Resolved", f"Expected OFFLINE alert to be Resolved, but was {saved_alert.state}"

        finally:
            await db.execute(delete(AlertModel).where(AlertModel.device_id == test_dev_id))
            await db.execute(delete(Device).where(Device.id == test_dev_id))
            await db.commit()
            AlertEngine._device_state_tracker.pop(clean_id, None)


@pytest.mark.anyio
async def test_booting_device_heartbeat_triggers_online_alert():
    """
    Demonstrates the second aspect of the bug:
    When a PC was woken up and had PowerStatus.BOOTING,
    when heartbeat arrives, it must trigger online alert.
    """
    test_dev_id = "TEST-PC-BOOTING-001"
    clean_id = test_dev_id.upper()
    
    AlertEngine._device_state_tracker[clean_id] = {
        "state": "OFFLINE",
        "last_offline_time": time.time() - 300,
        "last_online_time": 0,
        "last_offline_alert_ts": time.time() - 300,
        "last_online_alert_ts": 0
    }

    async with AsyncSessionLocal() as db:
        try:
            await db.execute(delete(AlertModel).where(AlertModel.device_id == test_dev_id))
            await db.execute(delete(Device).where(Device.id == test_dev_id))
            
            # Create device in BOOTING state (as set by wake command)
            dev = Device(
                id=test_dev_id,
                name="Test Booting PC",
                hostname=test_dev_id,
                ip_address="192.168.1.206",
                mac_address="AA:BB:CC:DD:EE:02",
                os_type="Windows",
                os_version="Windows 10 Pro",
                agent_version="2.9.16",
                power_status=PowerStatus.BOOTING,
                agent_status=AgentStatus.DISCONNECTED,
                health_status=HealthStatus.HEALTHY,
                group_name="Office",
                last_seen=datetime.utcnow() - timedelta(minutes=5)
            )
            db.add(dev)
            
            alert = AlertModel(
                id=f"ALT-OFF-{test_dev_id}-67890",
                device_id=test_dev_id,
                alert_type="OFFLINE",
                severity="Warning",
                description="Связь с агентом прервана",
                state="Open",
                created_at=datetime.utcnow() - timedelta(minutes=5)
            )
            db.add(alert)
            await db.commit()

            scope = {'type': 'http', 'client': ('192.168.1.206', 54321), 'headers': []}
            req = Request(scope)
            hb_payload = {
                "deviceId": test_dev_id,
                "hostname": test_dev_id,
                "mac": "AA:BB:CC:DD:EE:02",
                "isStartup": True,
                "uptimeSeconds": 20
            }
            await agent_heartbeat(hb_payload, req, db)

            assert AlertEngine._device_state_tracker[clean_id]["state"] == "ONLINE"
            alt_res = await db.execute(select(AlertModel).where(AlertModel.device_id == test_dev_id))
            saved_alert = alt_res.scalars().first()
            assert saved_alert is not None
            assert saved_alert.state == "Resolved"

        finally:
            await db.execute(delete(AlertModel).where(AlertModel.device_id == test_dev_id))
            await db.execute(delete(Device).where(Device.id == test_dev_id))
            await db.commit()
            AlertEngine._device_state_tracker.pop(clean_id, None)
