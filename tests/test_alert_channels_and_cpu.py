import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import select
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.alert_engine import AlertEngine
from backend.app.schemas.device import AlertPolicyChannelsSchema, AlertPolicySchema

client = TestClient(app)

def test_alert_policy_channels_schema_email_removed():
    """Ensure AlertPolicyChannelsSchema only contains webUi and telegram, and email is removed."""
    schema = AlertPolicyChannelsSchema(webUi=True, telegram=False)
    assert schema.webUi is True
    assert schema.telegram is False
    assert "email" not in AlertPolicyChannelsSchema.model_fields

def test_alert_engine_suppresses_disabled_channels():
    """When webUi=False and telegram=False, dispatch_alert must not send Telegram or WebUI notifications."""
    alert = {
        "id": "TEST-ALT-001",
        "deviceId": "dev-suppress-test",
        "device": "Test Station",
        "type": "HARDWARE_MISMATCH",
        "severity": "Critical",
        "description": "RAM removed from slot 1",
    }
    
    policy = {
        "mode": "Full",
        "events_config": {"hardwareChanges": True},
        "notify_channels": {
            "webUi": False,
            "telegram": False
        }
    }

    async def _run_test():
        with patch("backend.app.api.v1.telegram.get_httpx_client") as mock_httpx, \
             patch("backend.app.ws.manager.ws_manager.broadcast_event", new_callable=AsyncMock) as mock_ws:
            
            await AlertEngine.dispatch_alert(alert, policy=policy)
            
            # Telegram client should not have been called because telegram=False
            assert not mock_httpx.called
            assert not mock_ws.called

    asyncio.run(_run_test())

def test_device_alert_policy_api_without_email():
    """POST and GET /devices/{device_id}/alert-policy without email channel."""
    device_id = "test-device-policy-no-email"
    payload = {
        "mode": "Custom",
        "events": {
            "hardwareChanges": True,
            "agentDisconnect": True
        },
        "thresholds": {
            "cpuPercent": 85,
            "ramPercent": 80,
            "diskPercent": 90,
            "rdpIdleMinutes": 20
        },
        "notifyChannels": {
            "webUi": False,
            "telegram": False
        }
    }
    
    resp = client.post(f"/api/v1/devices/{device_id}/alert-policy", json=payload)
    assert resp.status_code == 200
    
    get_resp = client.get(f"/api/v1/devices/{device_id}/alert-policy")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert "email" not in data.get("notifyChannels", {})
    assert data["notifyChannels"].get("webUi") is False
    assert data["notifyChannels"].get("telegram") is False

def test_process_cpu_delta_calculation_bounds():
    """
    Test CPU delta calculation logic:
    (delta_proc_cpu / (delta_time * cores)) * 100
    Must be within [0.0, 100.0] and never > 100%.
    """
    cores = 4
    delta_time_sec = 5.0
    
    # 1. Normal usage: process used 2.5 CPU-seconds over 5 seconds on 4 cores = 2.5 / 20 = 12.5%
    delta_proc_cpu = 2.5
    pct = round((delta_proc_cpu / (delta_time_sec * cores)) * 100.0, 1)
    assert pct == 12.5
    
    # 2. Heavy usage: process fully utilized 4 cores for 5 seconds = 20 CPU-seconds = 100.0%
    delta_proc_cpu = 20.0
    pct = round((delta_proc_cpu / (delta_time_sec * cores)) * 100.0, 1)
    assert pct == 100.0
    
    # 3. Burst spike or noisy clock: clamp to 100.0% max
    delta_proc_cpu = 50.0
    raw_pct = (delta_proc_cpu / (delta_time_sec * cores)) * 100.0
    bounded_pct = round(min(100.0, max(0.0, raw_pct)), 1)
    assert bounded_pct == 100.0

def test_offline_alert_suppression_when_channels_disabled():
    """When a device's alert policy has webUi=False and telegram=False, trigger_device_offline should not broadcast alert.created or dispatch Telegram."""
    from backend.app.models.device import Device, PowerStatus
    from unittest.mock import AsyncMock, MagicMock
    
    mock_dev = MagicMock(spec=Device)
    mock_dev.id = "dev-off-test"
    mock_dev.hostname = "PC-OFF-TEST"
    mock_dev.name = "Offline Test PC"
    mock_dev.power_status = PowerStatus.ON
    
    policy_dict = {
        "mode": "Full",
        "events_config": {"agentDisconnect": True},
        "notify_channels": {"webUi": False, "telegram": False}
    }
    
    mock_session = AsyncMock()
    # Mock pol_model result
    mock_pol = MagicMock()
    mock_pol.mode = "Full"
    mock_pol.events_config = {"agentDisconnect": True}
    mock_pol.notify_channels = {"webUi": False, "telegram": False}
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_pol
    mock_session.execute.return_value = mock_res
    
    async def _run():
        with patch("backend.app.ws.manager.ws_manager.broadcast_event", new_callable=AsyncMock) as mock_ws, \
             patch("backend.app.services.alert_engine.AlertEngine.dispatch_alert", new_callable=AsyncMock) as mock_dispatch:
            await AlertEngine.trigger_device_offline(mock_session, mock_dev, reason="PC offline")
            
            # Since webUi=False, ws_manager.broadcast_event('alert.created', ...) should NOT be called
            alert_created_calls = [call for call in mock_ws.call_args_list if call.args and call.args[0] == "alert.created"]
            assert len(alert_created_calls) == 0, "alert.created must not be broadcast when webUi channel is False"

    asyncio.run(_run())

def test_alert_policy_persistence_toggle_and_reload():
    """Verify that unchecking both webUi and telegram persists across subsequent GET calls."""
    dev_id = "test-policy-persist-toggle-pc"
    payload = {
        "mode": "Custom",
        "events": {"highCpuUsage": False},
        "thresholds": {"cpuPercent": 80},
        "notifyChannels": {
            "webUi": False,
            "telegram": False
        }
    }
    post_res = client.post(f"/api/v1/devices/{dev_id}/alert-policy", json=payload)
    assert post_res.status_code == 200

    # First reload check
    get_res1 = client.get(f"/api/v1/devices/{dev_id}/alert-policy")
    assert get_res1.status_code == 200
    ch1 = get_res1.json().get("notifyChannels", {})
    assert ch1.get("webUi") is False
    assert ch1.get("web_ui") is False
    assert ch1.get("telegram") is False
    assert ch1.get("tg") is False

    # Upper case ID check
    get_res_upper = client.get(f"/api/v1/devices/{dev_id.upper()}/alert-policy")
    assert get_res_upper.status_code == 200
    ch_upper = get_res_upper.json().get("notifyChannels", {})
    assert ch_upper.get("webUi") is False
    assert ch_upper.get("telegram") is False

def test_process_cpu_anomaly_guard_scales_legacy_percentages():
    """Ensure that when a legacy agent reports modulo-based numbers (e.g. sum=388%), they are scaled to match actual system CPU."""
    from backend.app.api.v1.devices import device_live_processes

    test_id = "PC-ANOMALY-CPU"
    # Emulate the exact values from the user's screenshot
    hb_payload = {
        "deviceId": test_id,
        "hostname": test_id,
        "ip": "192.168.1.99",
        "cpu": 12,  # Actual system CPU is 12%
        "ram": 45,
        "disk": 50,
        "processes": [
            {"pid": 4228, "name": "MsMpEng.exe", "cpu": "86.8", "ram": 283, "user": "SYSTEM"},
            {"pid": 3480, "name": "chrome.exe", "cpu": "82.1", "ram": 137, "user": "User"},
            {"pid": 1808, "name": "chrome.exe", "cpu": "66.6", "ram": 105, "user": "User"},
            {"pid": 5780, "name": "dwm.exe", "cpu": "42.6", "ram": 62, "user": "DWM-2"},
            {"pid": 4, "name": "System.exe", "cpu": "30.6", "ram": 2, "user": "SYSTEM"},
            {"pid": 4044, "name": "svchost.exe", "cpu": "25.9", "ram": 23, "user": "СИСТЕМА"},
            {"pid": 4004, "name": "WmiPrvSE.exe", "cpu": "25.7", "ram": 27, "user": "NETWORK SERVICE"},
        ]
    }

    resp = client.post("/api/v1/agents/heartbeat", json=hb_payload)
    assert resp.status_code == 200

    procs = device_live_processes.get(test_id)
    assert procs is not None
    assert len(procs) == 7

    total_proc_cpu = sum(float(p.get("cpu", 0)) for p in procs)
    # Total sum of process CPU should now be scaled to <= system CPU (12%)
    assert total_proc_cpu <= 12.0
    # Top process (MsMpEng) should now be ~2-3%, definitely NOT 86.8%!
    msmpeng = next(p for p in procs if "MsMpEng" in p["name"])
    assert float(msmpeng["cpu"]) < 5.0



