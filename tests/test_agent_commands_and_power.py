import pytest
import time
from datetime import datetime, timedelta
from starlette.requests import Request
from sqlalchemy import select, delete

from backend.app.api.v1.agents import (
    agent_heartbeat,
    queue_device_command,
    pending_device_commands,
    clear_pending_power_commands
)
from backend.app.api.v1.devices import execute_device_power_action
from backend.app.db.session import AsyncSessionLocal
from backend.app.models.device import Device, PowerStatus, AgentStatus, HealthStatus
from backend.app.ws.manager import ws_manager


@pytest.mark.anyio
async def test_heartbeat_returns_fast_interval_when_commands_pending():
    test_dev_id = "TEST-FAST-INTERVAL-001"
    pending_device_commands[test_dev_id].clear()
    pending_device_commands[test_dev_id.upper()].clear()

    async with AsyncSessionLocal() as db:
        try:
            scope = {'type': 'http', 'client': ('192.168.1.188', 54321), 'headers': []}
            req = Request(scope)

            # 1. Without pending commands, should return normal interval (e.g. 60)
            payload_idle = {
                "deviceId": test_dev_id,
                "hostname": "HOST-FAST-001",
                "uptime": "1д 5ч",
                "uptimeSeconds": 100000,
                "cpu": 10,
                "ram": 20,
                "disk": 30
            }
            res_idle = await agent_heartbeat(payload_idle, req, db)
            assert res_idle["heartbeatInterval"] >= 30, f"Expected normal interval, got {res_idle['heartbeatInterval']}"

            # 2. Queue a command for this device
            queue_device_command(test_dev_id, "KILL_PROCESS", extra_data={"pid": 1234})

            # 3. Heartbeat with pending commands should return fast interval (<= 3s)
            payload_busy = {
                "deviceId": test_dev_id,
                "hostname": "HOST-FAST-001",
                "uptime": "1д 5ч",
                "uptimeSeconds": 100005,
                "cpu": 10,
                "ram": 20,
                "disk": 30
            }
            res_busy = await agent_heartbeat(payload_busy, req, db)
            assert res_busy["heartbeatInterval"] <= 3, f"Expected fast interval <= 3s, got {res_busy['heartbeatInterval']}"
            assert len(res_busy["pendingCommands"]) >= 1
            assert res_busy["pendingCommands"][0]["action"] == "KILL_PROCESS"
        finally:
            pending_device_commands[test_dev_id].clear()
            pending_device_commands[test_dev_id.upper()].clear()
            await db.execute(delete(Device).where(Device.id == test_dev_id))
            await db.commit()


@pytest.mark.anyio
async def test_fresh_boot_does_not_drop_recent_manual_shutdown():
    test_dev_id = "TEST-FRESH-BOOT-SHUTDOWN"
    pending_device_commands[test_dev_id].clear()
    pending_device_commands[test_dev_id.upper()].clear()

    async with AsyncSessionLocal() as db:
        try:
            scope = {'type': 'http', 'client': ('192.168.1.189', 54321), 'headers': []}
            req = Request(scope)

            # Boot time was 20 seconds ago
            boot_time = datetime.utcnow() - timedelta(seconds=20)
            boot_iso = boot_time.isoformat() + "Z"

            # Operator requests shutdown NOW (newer than boot time)
            cmd = queue_device_command(
                test_dev_id,
                "SHUTDOWN",
                force=True,
                reason="Operator clicked shutdown",
                extra_data={"source": "MANUAL"}
            )

            payload_fresh = {
                "deviceId": test_dev_id,
                "hostname": "HOST-FRESH-001",
                "uptime": "Только что",
                "uptimeSeconds": 20,
                "bootTime": boot_iso,
                "cpu": 10,
                "ram": 20,
                "disk": 30
            }
            res = await agent_heartbeat(payload_fresh, req, db)
            dispatched = [c["action"] for c in res.get("pendingCommands", [])]
            assert "SHUTDOWN" in dispatched, f"Shutdown command was dropped on fresh boot! Dispatched: {dispatched}"
        finally:
            pending_device_commands[test_dev_id].clear()
            pending_device_commands[test_dev_id.upper()].clear()
            await db.execute(delete(Device).where(Device.id == test_dev_id))
            await db.commit()


@pytest.mark.anyio
async def test_execute_device_power_action_does_not_prematurely_mark_off():
    test_dev_id = "TEST-DEV-POWER-TRANSITION"
    async with AsyncSessionLocal() as db:
        try:
            dev = Device(
                id=test_dev_id,
                name="Тестовый ПК Питание",
                hostname="TEST-DEV-POWER",
                ip_address="192.168.1.199",
                mac_address="00:11:22:33:44:99",
                power_status=PowerStatus.ON,
                health_status=HealthStatus.HEALTHY,
                agent_status=AgentStatus.CONNECTED,
                last_seen=datetime.utcnow()
            )
            db.add(dev)
            await db.commit()

            scope = {'type': 'http', 'client': ('192.168.1.199', 54321), 'headers': []}
            req = Request(scope)

            # Execute reboot action
            res_reboot = await execute_device_power_action(
                device_id=test_dev_id,
                payload={"action": "REBOOT", "initiator": "Admin"},
                request=req,
                db=db
            )
            assert res_reboot["status"] == "success"

            # Check device status in DB: power_status should NOT be OFF
            await db.refresh(dev)
            assert dev.power_status != PowerStatus.OFF, f"Device power_status was prematurely set to OFF!"
            assert dev.power_status in [PowerStatus.SHUTTING_DOWN, PowerStatus.ON]
            assert dev.agent_status == AgentStatus.CONNECTED

            # Execute shutdown action
            res_shutdown = await execute_device_power_action(
                device_id=test_dev_id,
                payload={"action": "SHUTDOWN", "initiator": "Admin"},
                request=req,
                db=db
            )
            assert res_shutdown["status"] == "success"

            await db.refresh(dev)
            assert dev.power_status != PowerStatus.OFF, f"Device power_status was prematurely set to OFF on shutdown!"
            assert dev.power_status == PowerStatus.SHUTTING_DOWN
        finally:
            clear_pending_power_commands(test_dev_id)
            await db.execute(delete(Device).where(Device.id == test_dev_id))
            await db.commit()


def test_websocket_flushes_commands_queued_by_hostname():
    """
    Commands queued under hostname (e.g. 'TEST-HOST-WS') must be flushed when the agent connects
    with deviceId='PC-WS-FLUSH' and hostname='TEST-HOST-WS'.
    """
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    dev_id = "PC-WS-FLUSH"
    host_name = "TEST-HOST-WS"

    # Queue command by hostname (as execute_process_kill does)
    cmd = queue_device_command(host_name, "KILL_PROCESS", extra_data={"pid": 4321, "processName": "bad.exe"})

    try:
        with client.websocket_connect(f"/api/v1/agents/ws?deviceId={dev_id}&hostname={host_name}") as websocket:
            msg_welcome = websocket.receive_json()
            assert msg_welcome.get("type") == "WELCOME"

            # Send PING: if command was flushed, the command arrives BEFORE PONG.
            # If the bug is present (command not flushed), PONG arrives instead of KILL_PROCESS.
            websocket.send_json({"type": "PING"})
            first_msg = websocket.receive_json()
            assert first_msg.get("action") == "KILL_PROCESS", f"Expected flushed command KILL_PROCESS, but got {first_msg}"
            assert first_msg.get("pid") == 4321
    finally:
        pending_device_commands[host_name].clear()
        pending_device_commands[dev_id].clear()


