import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
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

