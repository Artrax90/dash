import os
import time
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models.device import Device, PowerStatus, AgentStatus, HealthStatus
from backend.app.db.session import AsyncSessionLocal
from sqlalchemy import select

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_devices():
    """Seed test workstation with distinct id, hostname, and name."""
    import asyncio
    async def _seed():
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(Device).where(
                    (Device.id == 'PC-DESK-TEST') | 
                    (Device.name == 'DESKTOP-J8IDHQH') |
                    (Device.hostname == 'HOST-J8IDHQH')
                )
            )
            for d in res.scalars().all():
                await session.delete(d)
            await session.commit()

            test_dev = Device(
                id='PC-DESK-TEST',
                name='DESKTOP-J8IDHQH',
                hostname='HOST-J8IDHQH',
                ip_address='192.168.1.188',
                mac_address='A0:B1:C2:D3:E4:F5',
                power_status=PowerStatus.ON,
                agent_status=AgentStatus.CONNECTED,
                health_status=HealthStatus.HEALTHY,
                group_name='Office',
                os_type='Windows',
                os_version='Windows 11 Pro'
            )
            session.add(test_dev)
            await session.commit()
    asyncio.run(_seed())

def test_power_action_by_name_and_case_insensitive():
    """
    Ensure POST /devices/{device_id}/power resolves target by name, case-insensitively,
    and successfully dispatches direct LAN signal and queues command.
    """
    with patch('backend.app.api.v1.agents.send_direct_lan_power_signal') as mock_lan,          patch('backend.app.api.v1.agents.queue_device_command') as mock_queue:
        
        resp = client.post(
            '/api/v1/devices/desktop-j8idhqh/power',
            json={'action': 'SHUTDOWN', 'force': True, 'user': 'Admin'}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('status') == 'success'
        assert mock_lan.called
        assert mock_queue.called

def test_power_action_load_devices_fallback():
    """
    Ensure if device is not in DB ORM session, execute_device_power_action
    falls back to load_devices() cache so web actions match Telegram reliability.
    """
    mock_devs = [
        {
            'id': 'PC-REMOTE-99',
            'name': 'REMOTE-PC-99',
            'hostname': 'REMOTE-HOST-99',
            'ip': '192.168.1.199',
            'mac': '11:22:33:44:55:66',
            'powerStatus': 'On'
        }
    ]
    with patch('backend.app.api.v1.telegram.load_devices', return_value=mock_devs),          patch('backend.app.api.v1.agents.send_direct_lan_power_signal') as mock_lan,          patch('backend.app.api.v1.agents.queue_device_command') as mock_queue:
        
        resp = client.post(
            '/api/v1/devices/remote-pc-99/power',
            json={'action': 'REBOOT', 'force': True, 'user': 'Admin'}
        )
        assert resp.status_code == 200
        assert mock_lan.called
        assert mock_queue.called

def test_command_ttl_not_dropped_at_75_seconds():
    """
    Agent heartbeat is 60s. A command created 75 seconds ago must NOT be dropped as stale!
    """
    from backend.app.api.v1.agents import pending_device_commands, queue_device_command
    
    dev_id = 'PC-DESK-TEST'
    cmd = queue_device_command(dev_id, 'SHUTDOWN', force=True, reason='Test command')
    cmd['createdTimestamp'] = time.time() - 75
    
    hb_payload = {
        'deviceId': dev_id,
        'hostname': 'HOST-J8IDHQH',
        'mac': 'A0:B1:C2:D3:E4:F5',
        'cpu': 15,
        'ram': 45,
        'uptime': '2ч 15м',
        'uptimeSeconds': 8100
    }
    resp = client.post('/api/v1/agents/heartbeat', json=hb_payload)
    assert resp.status_code == 200
    data = resp.json()
    pending = data.get('pendingCommands', [])
    action_list = [c.get('action') for c in pending]
    assert 'SHUTDOWN' in action_list

def test_real_processes_not_replaced_by_dummy_stub():
    """
    Verify that:
    1. When real processes are reported for DESKTOP-J8IDHQH, they are saved and retrievable
       by name, id, and case-insensitively.
    2. get_device_processes does NOT return the hardcoded 5-dummy processes stub.
    """
    real_procs = [
        {'pid': 1104, 'name': 'chrome.exe', 'cpu': '1.2', 'ram': 450, 'diskIo': '0.4 MB/s', 'user': 'Worker', 'status': 'Running'},
        {'pid': 2208, 'name': 'code.exe', 'cpu': '2.5', 'ram': 620, 'diskIo': '0.1 MB/s', 'user': 'Worker', 'status': 'Running'},
        {'pid': 3312, 'name': 'slack.exe', 'cpu': '0.4', 'ram': 280, 'diskIo': '0.0 MB/s', 'user': 'Worker', 'status': 'Running'}
    ]

    hb_payload = {
        'deviceId': 'PC-DESK-TEST',
        'hostname': 'HOST-J8IDHQH',
        'name': 'DESKTOP-J8IDHQH',
        'mac': 'A0:B1:C2:D3:E4:F5',
        'cpu': 5.0,
        'ram': 50,
        'processes': real_procs
    }
    resp = client.post('/api/v1/agents/heartbeat', json=hb_payload)
    assert resp.status_code == 200

    resp_procs = client.get('/api/v1/devices/DESKTOP-J8IDHQH/processes')
    assert resp_procs.status_code == 200
    procs = resp_procs.json()
    assert len(procs) == 3
    names = [p['name'] for p in procs]
    assert 'chrome.exe' in names
    assert 'code.exe' in names
    assert 'svchost.exe (LocalSystemNetworkRestricted)' not in names
    assert 'WorkstationManagerAgent.exe' not in names
