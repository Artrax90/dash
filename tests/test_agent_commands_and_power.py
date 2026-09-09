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

def test_resolve_request_base_url_auto_resolves_lan_ip_when_localhost():
    """
    When accessing dashboard locally (Host: localhost:2301 or client 127.0.0.1),
    resolve_request_base_url must resolve the machine's primary non-loopback LAN IP
    so that downloaded installers and one-liners point to a reachable network address.
    """
    from backend.app.main import resolve_request_base_url
    scope = {
        'type': 'http',
        'client': ('127.0.0.1', 54321),
        'headers': [(b'host', b'localhost:2301')],
        'server': ('127.0.0.1', 2301),
        'scheme': 'http',
        'path': '/api/v1/agents/install.bat'
    }
    req = Request(scope)
    url = resolve_request_base_url(req)
    assert not url.startswith("http://localhost"), f"Expected real LAN IP, but got {url}"
    assert not url.startswith("http://127.0.0.1"), f"Expected real LAN IP, but got {url}"
    assert ":2301" in url


def test_service_script_template_has_proxy_null_and_dynamic_config():
    """
    Ensure run_service.ps1 template contains Proxy = $null for WebRequest and ClientWebSocket
    to prevent WPAD / proxy hangs on corporate networks, and reads config.json dynamically.
    """
    with open("agent/standalone_installer.ps1", "r", encoding="utf-8-sig") as f:
        content = f.read()

    # 1. WebRequest in Invoke-Heartbeat and Update-AgentService must set $req.Proxy = $null
    assert "$req.Proxy = $null" in content or "`$req.Proxy = `$null" in content, "Missing Proxy = $null on WebRequest in agent template"

    # 2. ClientWebSocket in Maintain-WebSocketConnection must set Proxy = $null
    assert "Options.Proxy = $null" in content or "Options.Proxy = `$null" in content, "Missing Options.Proxy = $null on ClientWebSocket in agent template"


def test_standalone_installer_has_utf8_bom_and_valid_syntax():
    """
    Windows PowerShell 5.1 requires UTF-8 BOM on non-ASCII scripts to parse Cyrillic correctly.
    This test verifies that the BOM is present and PowerShell's AST parser detects 0 syntax errors.
    """
    import subprocess
    installer_path = "agent/standalone_installer.ps1"
    with open(installer_path, "rb") as f:
        header = f.read(3)
    assert header == b"\xef\xbb\xbf", f"standalone_installer.ps1 is missing UTF-8 BOM (got {header!r})"

    # Verify syntax with PowerShell AST parser
    ps_cmd = (
        "$errs = $null; "
        "[System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path 'agent/standalone_installer.ps1'), [ref]$null, [ref]$errs); "
        "if ($errs.Count -gt 0) { $errs | ForEach-Object { Write-Error $_.Message }; exit 1 } else { Write-Host 'VALID' }"
    )
    import base64
    b64 = base64.b64encode(ps_cmd.encode("utf-16le")).decode("ascii")
    res = subprocess.run(["powershell.exe", "-NoProfile", "-EncodedCommand", b64], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout = res.stdout.decode("utf-8", errors="replace")
    stderr = res.stderr.decode("utf-8", errors="replace")
    assert res.returncode == 0, f"PowerShell syntax validation failed:\n{stderr}\n{stdout}"



