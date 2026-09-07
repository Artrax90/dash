import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.ws.manager import ws_manager
from backend.app.api.v1.agents import queue_device_command

@pytest.mark.anyio
async def test_ws_manager_agent_registration_and_command():
    mock_ws = AsyncMock()
    mock_ws.send_json = AsyncMock()

    # Register agent
    await ws_manager.register_agent("PC-TEST-WS", mock_ws, hostname="HOST-WS-01")
    assert ws_manager.is_agent_connected("PC-TEST-WS") is True
    assert ws_manager.is_agent_connected("pc-test-ws") is True
    assert ws_manager.is_agent_connected("HOST-WS-01") is True

    # Send command over websocket
    cmd_payload = {"id": "CMD-001", "action": "KILL_PROCESS", "pid": 5555, "processName": "bad.exe"}
    sent = await ws_manager.send_agent_command("PC-TEST-WS", cmd_payload)
    assert sent is True
    mock_ws.send_json.assert_awaited_once_with(cmd_payload)

    # Unregister agent
    ws_manager.unregister_agent("PC-TEST-WS", hostname="HOST-WS-01")
    assert ws_manager.is_agent_connected("PC-TEST-WS") is False
    assert ws_manager.is_agent_connected("HOST-WS-01") is False

@pytest.mark.anyio
async def test_queue_device_command_pushes_to_connected_websocket():
    mock_ws = AsyncMock()
    mock_ws.send_json = AsyncMock()

    await ws_manager.register_agent("PC-INSTANT-01", mock_ws, hostname="INSTANT-HOST")
    try:
        # Queuing command must immediately trigger WebSocket push if agent is connected
        cmd = queue_device_command("PC-INSTANT-01", "REBOOT", force=True, reason="Immediate test")
        assert cmd["action"] == "REBOOT"
        
        # Let event loop execute background task
        import asyncio
        await asyncio.sleep(0.02)

        # Verify that mock_ws received the command over websocket
        mock_ws.send_json.assert_awaited_once()
        args, _ = mock_ws.send_json.call_args
        assert args[0]["action"] == "REBOOT"
        assert args[0]["id"] == cmd["id"]
    finally:
        ws_manager.unregister_agent("PC-INSTANT-01", hostname="INSTANT-HOST")

def test_agent_websocket_endpoint_ping_pong():
    client = TestClient(app)
    with client.websocket_connect("/api/v1/agents/ws?deviceId=PC-WS-ENDPOINT&hostname=TEST-PC") as websocket:
        # First message is welcome greeting
        welcome = websocket.receive_json()
        assert welcome.get("type") == "WELCOME"
        assert welcome.get("status") == "connected"

        # Test ping
        websocket.send_json({"type": "PING"})
        data = websocket.receive_json()
        assert data.get("type") == "PONG"

