import pytest
import json
import socket
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models.device import Device, PowerStatus, AgentStatus, HealthStatus
from backend.app.db.session import AsyncSessionLocal
from sqlalchemy import select

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_devices():
    import asyncio
    async def _seed():
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(Device).where(
                    (Device.id == 'PC-PROC-TEST') |
                    (Device.id == 'PC-SINGLE-PROC') |
                    (Device.id == 'PC-LOCAL-TEST')
                )
            )
            for d in res.scalars().all():
                await session.delete(d)
            await session.commit()

            d1 = Device(
                id='PC-PROC-TEST',
                name='PROC-WORKSTATION',
                hostname='HOST-PROC-01',
                ip_address='192.168.1.199',
                mac_address='00:11:22:33:44:55',
                power_status=PowerStatus.ON,
                agent_status=AgentStatus.CONNECTED,
                health_status=HealthStatus.HEALTHY,
                group_name='Office',
                os_type='Windows',
                os_version='Windows 11 Pro'
            )
            d2 = Device(
                id='PC-SINGLE-PROC',
                name='SINGLE-PROC-PC',
                hostname='HOST-SINGLE-01',
                ip_address='192.168.1.201',
                mac_address='00:11:22:33:44:66',
                power_status=PowerStatus.ON,
                agent_status=AgentStatus.CONNECTED,
                health_status=HealthStatus.HEALTHY,
                group_name='Office',
                os_type='Windows',
                os_version='Windows 11 Pro'
            )
            local_name = socket.gethostname()
            d3 = Device(
                id='PC-LOCAL-TEST',
                name=local_name,
                hostname=local_name,
                ip_address='127.0.0.1',
                mac_address='00:11:22:33:44:77',
                power_status=PowerStatus.ON,
                agent_status=AgentStatus.CONNECTED,
                health_status=HealthStatus.HEALTHY,
                group_name='Office',
                os_type='Windows',
                os_version='Windows 11 Pro'
            )
            session.add_all([d1, d2, d3])
            await session.commit()
    asyncio.run(_seed())

def test_process_extraction_from_top_processes_key():
    hb = {
        'deviceId': 'PC-PROC-TEST',
        'hostname': 'HOST-PROC-01',
        'name': 'PROC-WORKSTATION',
        'ip': '192.168.1.199',
        'topProcesses': [
            {'pid': 5001, 'name': 'custom_app.exe', 'cpu': '3.4', 'ram': 150, 'user': 'Admin', 'status': 'Running'},
            {'pid': 5002, 'name': 'node.exe', 'cpu': '1.1', 'ram': 220, 'user': 'Admin', 'status': 'Running'}
        ]
    }
    resp = client.post('/api/v1/agents/heartbeat', json=hb)
    assert resp.status_code == 200

    r_id = client.get('/api/v1/devices/PC-PROC-TEST/processes')
    assert r_id.status_code == 200
    assert len(r_id.json()) == 2
    assert r_id.json()[0]['name'] == 'custom_app.exe'

    r_name = client.get('/api/v1/devices/PROC-WORKSTATION/processes')
    assert r_name.status_code == 200
    assert len(r_name.json()) == 2

    r_host = client.get('/api/v1/devices/HOST-PROC-01/processes')
    assert r_host.status_code == 200
    assert len(r_host.json()) == 2

    r_ip = client.get('/api/v1/devices/192.168.1.199/processes')
    assert r_ip.status_code == 200
    assert len(r_ip.json()) == 2

def test_single_dict_and_stringified_json_process_payload():
    hb_single = {
        'deviceId': 'PC-SINGLE-PROC',
        'hostname': 'HOST-SINGLE-01',
        'name': 'SINGLE-PROC-PC',
        'processes': {'pid': 7777, 'name': 'solitary.exe', 'cpu': '0.5', 'ram': '64MB', 'user': 'CORP\\John', 'status': 'Running'}
    }
    resp = client.post('/api/v1/agents/heartbeat', json=hb_single)
    assert resp.status_code == 200

    r = client.get('/api/v1/devices/PC-SINGLE-PROC/processes')
    assert r.status_code == 200
    procs = r.json()
    assert len(procs) == 1
    assert procs[0]['name'] == 'solitary.exe'
    assert procs[0]['ram'] == 64
    assert procs[0]['user'] == 'John'

def test_local_host_live_processes_sampling():
    r = client.get('/api/v1/devices/PC-LOCAL-TEST/processes')
    assert r.status_code == 200
    procs = r.json()
    assert isinstance(procs, list)
    assert len(procs) > 0
    assert all('pid' in p and 'name' in p for p in procs)

def test_format_device_summary_includes_processes_by_name():
    r = client.get('/api/v1/devices')
    assert r.status_code == 200
    devs = {d['id']: d for d in r.json()}
    assert 'PC-PROC-TEST' in devs
    assert len(devs['PC-PROC-TEST'].get('processes', [])) == 2