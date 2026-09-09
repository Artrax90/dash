import pytest
from backend.app.api.v1.users import (
    register_user_session,
    validate_user_session,
    revoke_user_sessions,
    user_active_sessions
)
from backend.app.api.v1.devices import execute_process_kill

def test_single_session_kick_out():
    username = "admin"
    token1 = register_user_session(username)
    assert validate_user_session(username, token1) is True

    # User logs in from a second location/device with the same account
    token2 = register_user_session(username)
    assert token2 != token1

    # First session must now be invalidated/kicked out!
    assert validate_user_session(username, token1) is False
    # Second session must be valid
    assert validate_user_session(username, token2) is True

    # Revoke sessions
    revoke_user_sessions(username)
    assert validate_user_session(username, token2) is False

@pytest.mark.anyio
async def test_process_kill_dispatcher():
    # Attempting to kill process without device or pid should fail
    res_fail = await execute_process_kill("NONEXISTENT_DEVICE", pid=1234, process_name="test.exe", user="Operator")
    assert res_fail["status"] == "error" or res_fail.get("success") is False

    # Test process kill with a mock device in SQLite DB
    from backend.app.db.session import AsyncSessionLocal
    from backend.app.models.device import Device, PowerStatus, HealthStatus, AgentStatus
    from datetime import datetime

    async with AsyncSessionLocal() as session:
        test_dev = Device(
            id="TEST-DEV-01",
            name="Тестовый ПК",
            hostname="TEST-DEV-01",
            ip_address="192.168.1.99",
            mac_address="00:11:22:33:44:55",
            power_status=PowerStatus.ON,
            health_status=HealthStatus.HEALTHY,
            agent_status=AgentStatus.CONNECTED,
            last_seen=datetime.utcnow()
        )

        session.add(test_dev)
        await session.commit()

        # Execute kill on the real DB device
        res = await execute_process_kill("TEST-DEV-01", pid=9999, process_name="miner.exe", user="Admin", db=session)
        assert res["status"] == "success"
        assert res["pid"] == 9999
        assert res["processName"] == "miner.exe"

        # Cleanup
        await session.delete(test_dev)
        await session.commit()

def test_windows_agent_service_script_generation():
    from backend.app.main import get_windows_agent_service_ps1
    from backend.app.core.config import settings

    base_url = "http://192.168.1.37:2301"
    device_id = "PC-1F7D"
    mac = "AA:BB:CC:DD:EE:FF"
    
    script = get_windows_agent_service_ps1(base_url, device_id, mac)
    
    # 1. Verification of variable replacements
    assert f"$DeviceId = '{device_id}'" in script
    assert f"$DeviceMac = '{mac}'" in script
    assert f"$ServerUrl = '{base_url}'" in script
    assert f"$AgentVersion = '{settings.LATEST_AGENT_VERSION}'" in script
    
    # 2. Critical bug verification: NO literal '$InstallDir'
    assert "'$InstallDir'" not in script
    assert "Join-Path $InstallDir" in script
    
    # 3. Mutex logic
    assert "agentMutex" in script

@pytest.mark.anyio
async def test_agent_update_logs_no_fake_success():
    from datetime import datetime, timedelta
    from backend.app.core.config import settings
    from backend.app.api.v1.agents import (
        agent_update_statuses,
        agent_update_logs,
        get_agent_update_logs
    )

    agent_update_logs.clear()
    agent_update_statuses.clear()

    now = datetime.utcnow()
    # Log entry in UPDATING status that is 45 seconds old (previously was falsely marked SUCCESS after 30s)
    old_ts = (now - timedelta(seconds=45)).isoformat() + "Z"
    agent_update_logs.append({
        "deviceId": "TEST-PC",
        "deviceName": "Test Workstation",
        "previousVersion": "2.9.4",
        "targetVersion": settings.LATEST_AGENT_VERSION,
        "status": "UPDATING",
        "details": "Загрузка обновления службы",
        "timestamp": old_ts
    })

    # When querying logs, it must NOT fake SUCCESS because device hasn't reported SUCCESS
    logs = await get_agent_update_logs()
    assert len(logs) == 1
    assert logs[0]["status"] == "UPDATING"

    # Now simulate device reporting SUCCESS
    agent_update_statuses["TEST-PC"] = {
        "status": "SUCCESS",
        "version": settings.LATEST_AGENT_VERSION,
        "completedAt": datetime.utcnow().isoformat() + "Z"
    }

    logs_after = await get_agent_update_logs()
    assert logs_after[0]["status"] == "SUCCESS"
    assert settings.LATEST_AGENT_VERSION in logs_after[0]["details"]

@pytest.mark.anyio
async def test_agent_heartbeat_new_device_registration():
    """Verify that heartbeat from a brand new device registers successfully without NameError or constraint failures."""
    from backend.app.api.v1.agents import agent_heartbeat
    from backend.app.db.session import AsyncSessionLocal
    from backend.app.models.device import Device
    from starlette.requests import Request
    from sqlalchemy import delete

    test_dev_id = "TEST-NEW-HEARTBEAT-REG-001"
    async with AsyncSessionLocal() as db:
        try:
            scope = {'type': 'http', 'client': ('192.168.1.155', 54321), 'headers': []}
            req = Request(scope)
            payload = {
                "deviceId": test_dev_id,
                "hostname": "TEST-HOST-REG-001",
                "version": "2.9.4",
                "ip": "192.168.1.155",
                "mac": "AA:BB:CC:DD:EE:FF",
                "cpu": 15,
                "ram": 45,
                "disk": 50
            }
            res = await agent_heartbeat(payload, req, db)
            assert res["status"] == "ok"
            assert res["latestVersion"] == "2.9.9"
        finally:
            await db.execute(delete(Device).where(Device.id == test_dev_id))
            await db.commit()

@pytest.mark.anyio
async def test_process_kill_command_payload_structure():
    """Verify that process kill command payload contains flat pid, processName and extra dict."""
    from backend.app.api.v1.agents import queue_device_command, pending_device_commands

    dev_id = "TEST-PC-KILL-CHECK"
    cmd = queue_device_command(
        device_id=dev_id,
        action="KILL_PROCESS",
        force=True,
        reason="Kill firefox test",
        extra_data={"pid": 10476, "processName": "firefox.exe"}
    )
    assert cmd["action"] == "KILL_PROCESS"
    assert cmd["pid"] == 10476
    assert cmd["processName"] == "firefox.exe"
    assert cmd["extra"]["pid"] == 10476
    assert cmd["extra"]["processName"] == "firefox.exe"
    assert dev_id in pending_device_commands
    assert any(c["id"] == cmd["id"] for c in pending_device_commands[dev_id])

def test_windows_agent_service_script_no_literal_placeholders():
    """Verify that get_windows_agent_service_ps1 does not output literal single-quoted placeholders."""
    from backend.app.main import get_windows_agent_service_ps1

    code = get_windows_agent_service_ps1("http://192.168.0.237:2301", "", "")
    assert "'$deviceId'" not in code
    assert "'$mac'" not in code
    assert "'$ServerUrl'" not in code
    assert "$DeviceId =" in code
    assert "$ServerUrl =" in code
    assert "function Update-AgentService" in code

@pytest.mark.anyio
async def test_agent_py_endpoint():
    """Verify that GET /agent.py returns 200 OK and valid Python code."""
    from backend.app.main import get_python_agent_script_endpoint

    res = await get_python_agent_script_endpoint()
    assert res.status_code == 200
    assert "AGENT_VERSION" in res.body.decode("utf-8")
    assert "SHUTDOWN" in res.body.decode("utf-8")

@pytest.mark.anyio
async def test_process_cpu_locale_comma_handling():
    """Verify that process CPU with comma separator (Russian locale) is cleanly parsed without zeroing."""
    from backend.app.api.v1.agents import agent_heartbeat
    from backend.app.api.v1.devices import device_live_processes
    from backend.app.db.session import AsyncSessionLocal
    from starlette.requests import Request
    import uuid

    test_dev_id = f"PC-TEST-CPU-{uuid.uuid4().hex[:6].upper()}"
    async with AsyncSessionLocal() as db:
        try:
            scope = {'type': 'http', 'client': ('127.0.0.1', 54321), 'headers': []}
            req = Request(scope)
            payload = {
                "deviceId": test_dev_id,
                "hostname": test_dev_id,
                "ip": "127.0.0.1",
                "cpu": 15,
                "ram": 45,
                "disk": 50,
                "processes": [
                    {
                        "pid": 1234,
                        "name": "chrome.exe",
                        "cpu": "5,4",
                        "ram": 450,
                        "diskIo": "0.5 MB/s",
                        "user": "User",
                        "status": "Running"
                    },
                    {
                        "pid": 5678,
                        "name": "code.exe",
                        "cpu": "12.8%",
                        "ram": 800,
                        "diskIo": "1.2 MB/s",
                        "user": "User",
                        "status": "Running"
                    }
                ]
            }
            res = await agent_heartbeat(payload, req, db)
            assert res["status"] == "ok"
            procs = device_live_processes.get(test_dev_id, [])
            assert len(procs) == 2
            p_chrome = next(p for p in procs if p["pid"] == 1234)
            p_code = next(p for p in procs if p["pid"] == 5678)
            assert float(p_chrome["cpu"]) > 0.0
            assert float(p_chrome["cpu"]) == 5.4
            assert float(p_code["cpu"]) == 12.8
        finally:
            from sqlalchemy import delete
            from backend.app.models.device import Device
            await db.execute(delete(Device).where(Device.id == test_dev_id))
            await db.commit()

