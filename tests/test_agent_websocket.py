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

def test_powershell_client_websocket_real_connect():
    import threading
    import time
    import uvicorn
    import subprocess
    import tempfile
    import os

    server_port = 2399
    config = uvicorn.Config(app, host="127.0.0.1", port=server_port, log_level="warning")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    time.sleep(1.0)

    ps_script = f"""
$ws = New-Object System.Net.WebSockets.ClientWebSocket
$cts = New-Object System.Threading.CancellationTokenSource
$cts.CancelAfter(4000)
$uri = New-Object System.Uri('ws://127.0.0.1:{server_port}/api/v1/agents/ws?deviceId=PC-PWSH-TEST')
try {{
    $task = $ws.ConnectAsync($uri, $cts.Token)
    $task.Wait()
    Write-Host ("STATE:" + $ws.State)
}} catch {{
    Write-Host ("ERROR:" + $_.Exception.ToString())
}}
"""
    with tempfile.NamedTemporaryFile(suffix=".ps1", delete=False, mode="w", encoding="utf-8") as f:
        f.write(ps_script)
        temp_file = f.name

    try:
        res = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", temp_file],
            capture_output=True, text=True
        )
        print("POWERSHELL STDOUT:", res.stdout)
        print("POWERSHELL STDERR:", res.stderr)
        assert "STATE:Open" in res.stdout, f"Expected Open state, got: {res.stdout}"
    finally:
        server.should_exit = True
        if os.path.exists(temp_file):
            os.remove(temp_file)


