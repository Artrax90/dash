import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.api.v1.users import (
    register_user_session,
    validate_user_session,
    user_active_sessions,
    _save_sessions,
    _load_sessions
)
from backend.app.api.v1.devices import device_live_processes, format_device_summary
from backend.app.models.device import Device, PowerStatus, HealthStatus, AgentStatus
from agent.agent_standalone import get_top_processes

client = TestClient(app)

def test_validate_session_rejects_missing_token_or_superseded_session():
    username = "test_user_session"
    
    # 1. First PC logs in, gets token 1
    token_1 = register_user_session(username)
    assert token_1 is not None
    
    # PC 1 checks /validate-session with token 1 -> must be valid
    resp1 = client.get(
        "/api/v1/users/validate-session",
        headers={"X-Username": username, "Authorization": f"Bearer {token_1}"}
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["valid"] is True
    assert data1["active"] is True

    # 2. PC 2 logs in with same username -> gets token 2
    token_2 = register_user_session(username)
    assert token_2 != token_1

    # 3. PC 1 now checks /validate-session with old token 1 -> MUST BE INVALID (kicked out!)
    resp1_old = client.get(
        "/api/v1/users/validate-session",
        headers={"X-Username": username, "Authorization": f"Bearer {token_1}"}
    )
    assert resp1_old.status_code == 200
    data1_old = resp1_old.json()
    assert data1_old["valid"] is False, "Old session must be invalidated"

    # 4. Caller claiming username without any token header MUST be rejected as invalid
    resp_no_token = client.get(
        "/api/v1/users/validate-session",
        headers={"X-Username": username}
    )
    assert resp_no_token.status_code == 200
    data_no_token = resp_no_token.json()
    assert data_no_token["valid"] is False, "Session check without token must not be valid"

def test_full_process_collection_not_capped_to_15():
    procs = get_top_processes()
    assert isinstance(procs, list)
    # On any running machine, there are dozens or hundreds of processes (>15)
    # If get_top_processes was capped to 15, len(procs) would be <= 15.
    # It must return all running processes.
    assert len(procs) > 15, f"Expected more than 15 processes, got {len(procs)}"

def test_device_summary_and_endpoint_include_all_reported_processes():
    dev_id = "TEST-PC-PROC-FULL"
    test_proc_list = [
        {"pid": i, "name": f"proc_{i}.exe", "cpu": "0.1", "ram": 50, "user": "SYSTEM", "status": "Running"}
        for i in range(1, 35) # 34 processes
    ]
    device_live_processes[dev_id] = test_proc_list
    device_live_processes[dev_id.upper()] = test_proc_list

    dev = Device(
        id=dev_id,
        name="Test Full Procs",
        hostname=dev_id,
        ip_address="192.168.1.188",
        mac_address="00:11:22:33:44:88",
        power_status=PowerStatus.ON,
        health_status=HealthStatus.HEALTHY,
        agent_status=AgentStatus.CONNECTED
    )

    summary = format_device_summary(dev)
    assert "processes" in summary
    assert len(summary["processes"]) == 34, f"Expected all 34 processes in summary, got {len(summary.get('processes', []))}"
