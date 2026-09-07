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

