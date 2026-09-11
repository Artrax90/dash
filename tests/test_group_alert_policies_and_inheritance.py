import pytest
import os
import json
from typing import Dict, Any
from backend.app.core.config import settings

@pytest.fixture(autouse=True)
def cleanup_scope_policies():
    policies_file = os.path.join(settings.DATA_DIR, 'scope_alert_policies.json')
    backup_file = os.path.join(settings.DATA_DIR, 'scope_alert_policies.backup.json')
    for f in [policies_file, backup_file]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass
    yield
    for f in [policies_file, backup_file]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass

def test_scope_alert_policies_service_crud():
    from backend.app.services.scope_policy_service import (
        save_scope_policy,
        get_scope_policy,
        load_all_scope_policies,
        delete_scope_policy,
        resolve_effective_policy
    )

    # 1. Initially no policies
    assert get_scope_policy('group:Office') is None

    # 2. Save group policy
    group_pol = {
        'mode': 'Custom',
        'events': {'hardwareChanges': True, 'highCpuUsage': False},
        'thresholds': {'cpuPercent': 80, 'ramPercent': 75},
        'notifyChannels': {'webUi': True, 'telegram': False}
    }
    saved = save_scope_policy('group:Office', group_pol)
    assert saved['scope'] == 'group:Office'
    assert saved['thresholds']['cpuPercent'] == 80

    # 3. Retrieve policy
    retrieved = get_scope_policy('group:Office')
    assert retrieved is not None
    assert retrieved['thresholds']['cpuPercent'] == 80
    assert retrieved['notifyChannels']['telegram'] is False

    # 4. Save floor override
    floor_pol = {
        'mode': 'Custom',
        'thresholds': {'cpuPercent': 65},
        'notifyChannels': {'webUi': True, 'telegram': True}
    }
    save_scope_policy('floor:Главный корпус / 2 этаж', floor_pol)
    assert get_scope_policy('floor:Главный корпус / 2 этаж')['thresholds']['cpuPercent'] == 65

    # 5. Delete floor policy
    assert delete_scope_policy('floor:Главный корпус / 2 этаж') is True
    assert get_scope_policy('floor:Главный корпус / 2 этаж') is None

def test_hierarchical_cascading_inheritance():
    from backend.app.services.scope_policy_service import (
        save_scope_policy,
        resolve_effective_policy
    )

    # Setup hierarchy: Group:Office -> Building:Главный корпус -> Floor:2 этаж -> Room:204
    save_scope_policy('group:Office', {
        'mode': 'Custom',
        'events': {'agentDisconnect': True, 'hardwareChanges': True},
        'thresholds': {'cpuPercent': 85, 'ramPercent': 80},
        'notifyChannels': {'webUi': True, 'telegram': True}
    })

    # Case A: Device with no individual policy, no room policy, no floor policy -> inherits from Group:Office
    dev_a = {
        'id': 'PC-TEST-01',
        'hostname': 'OFFICE-PC-01',
        'group_name': 'Office',
        'building': 'Главный корпус',
        'floor': '1 этаж',
        'room': '101'
    }
    eff_a = resolve_effective_policy(dev_a)
    assert eff_a['source'] == 'group'
    assert eff_a['sourceName'] == 'Office'
    assert eff_a['isInherited'] is True
    assert eff_a['thresholds']['cpuPercent'] == 85

    # Case B: Set policy on Floor:2 этаж -> Device on 2 этаж inherits from Floor
    save_scope_policy('floor:Главный корпус / 2 этаж', {
        'mode': 'Critical Only',
        'thresholds': {'cpuPercent': 70},
        'notifyChannels': {'webUi': True, 'telegram': False}
    })
    dev_b = {
        'id': 'PC-TEST-02',
        'hostname': 'OFFICE-PC-02',
        'group_name': 'Office',
        'building': 'Главный корпус',
        'floor': '2 этаж',
        'room': '201'
    }
    eff_b = resolve_effective_policy(dev_b)
    assert eff_b['source'] == 'floor'
    assert '2 этаж' in eff_b['sourceName']
    assert eff_b['isInherited'] is True
    assert eff_b['thresholds']['cpuPercent'] == 70
    assert eff_b['notifyChannels']['telegram'] is False

    # Case C: Set policy on Room:204 -> Device in Room 204 inherits from Room
    save_scope_policy('room:Главный корпус / 2 этаж / 204', {
        'mode': 'Full',
        'thresholds': {'cpuPercent': 60},
        'notifyChannels': {'webUi': True, 'telegram': True}
    })
    dev_c = {
        'id': 'PC-TEST-03',
        'hostname': 'OFFICE-PC-03',
        'group_name': 'Office',
        'building': 'Главный корпус',
        'floor': '2 этаж',
        'room': '204'
    }
    eff_c = resolve_effective_policy(dev_c)
    assert eff_c['source'] == 'room'
    assert '204' in eff_c['sourceName']
    assert eff_c['isInherited'] is True
    assert eff_c['thresholds']['cpuPercent'] == 60

    # Case D: Device has its own individual policy in device_policy arg -> Device policy overrides everything!
    device_custom_policy = {
        'mode': 'Custom',
        'thresholds': {'cpuPercent': 95},
        'notifyChannels': {'webUi': True, 'telegram': True}
    }
    eff_d = resolve_effective_policy(dev_c, device_policy=device_custom_policy)
    assert eff_d['source'] == 'device'
    assert eff_d['isInherited'] is False
    assert eff_d['thresholds']['cpuPercent'] == 95

    # Case E: Device custom policy mode is 'Inherit' -> falls back to Room
    eff_e = resolve_effective_policy(dev_c, device_policy={'mode': 'Inherit'})
    assert eff_e['source'] == 'room'
    assert eff_e['isInherited'] is True
    assert eff_e['thresholds']['cpuPercent'] == 60

def test_scope_policy_propagation_helper():
    from backend.app.services.scope_policy_service import (
        save_scope_policy,
        propagate_group_policy,
        get_scope_policy
    )

    base_policy = {
        'mode': 'Custom',
        'thresholds': {'cpuPercent': 77},
        'notifyChannels': {'webUi': True, 'telegram': True}
    }

    # Propagate to specific floors
    propagate_group_policy(
        scope='group:Warehouse',
        policy=base_policy,
        cascade='floors',
        target_scopes=['floor:Склад / 1 этаж', 'floor:Склад / 2 этаж']
    )

    p1 = get_scope_policy('floor:Склад / 1 этаж')
    p2 = get_scope_policy('floor:Склад / 2 этаж')
    assert p1 is not None and p1['thresholds']['cpuPercent'] == 77
    assert p2 is not None and p2['thresholds']['cpuPercent'] == 77

def test_group_and_device_alert_policy_api_endpoints():
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)

    # 1. Save scope policy for group:Management
    resp = client.post('/api/v1/groups/scope/alert-policy', json={
        'scope': 'group:Management',
        'policy': {
            'mode': 'Critical Only',
            'thresholds': {'cpuPercent': 72},
            'notifyChannels': {'webUi': True, 'telegram': False}
        }
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data['scope'] == 'group:Management'
    assert data['thresholds']['cpuPercent'] == 72

    # 2. Retrieve scope policy
    get_resp = client.get('/api/v1/groups/scope/alert-policy?scope=group:Management')
    assert get_resp.status_code == 200
    ret_data = get_resp.json()
    assert ret_data['mode'] == 'Critical Only'
    assert ret_data['notifyChannels']['telegram'] is False

    # 3. Propagate group policy to floors via POST /group-policy/{name}
    prop_resp = client.post('/api/v1/groups/group-policy/Management', json={
        'policy': {
            'mode': 'Custom',
            'thresholds': {'cpuPercent': 68},
            'notifyChannels': {'webUi': True, 'telegram': True}
        },
        'targetFloors': ['floor:Корпус А / 3 этаж']
    })
    assert prop_resp.status_code == 200

    floor_check = client.get('/api/v1/groups/scope/alert-policy?scope=floor:Корпус А / 3 этаж')
    assert floor_check.status_code == 200
    assert floor_check.json()['thresholds']['cpuPercent'] == 68

    # 4. List all scope policies
    list_resp = client.get('/api/v1/groups/alert-policies')
    assert list_resp.status_code == 200
    all_scopes = list_resp.json()
    assert any(k.lower() == 'group:management' for k in all_scopes)

    # 5. Delete scope policy
    del_resp = client.delete('/api/v1/groups/scope/alert-policy?scope=floor:Корпус А / 3 этаж')
    assert del_resp.status_code == 200
    floor_after_del = client.get('/api/v1/groups/scope/alert-policy?scope=floor:Корпус А / 3 этаж')
    assert floor_after_del.status_code == 200
    assert floor_after_del.json().get('mode') == 'Inherit'

def test_device_alert_policy_inheritance_and_reset_endpoints():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.services.scope_policy_service import save_scope_policy

    client = TestClient(app)

    # 1. Setup group policy
    save_scope_policy('group:Office', {
        'mode': 'Custom',
        'thresholds': {'cpuPercent': 88, 'ramPercent': 82},
        'notifyChannels': {'webUi': True, 'telegram': False}
    })

    # Device endpoint without individual override -> resolves to global/group
    dev_id = 'PC-INHERIT-TEST'
    # Save a custom override on device
    save_resp = client.post(f'/api/v1/devices/{dev_id}/alert-policy', json={
        'mode': 'Custom',
        'thresholds': {'cpuPercent': 99},
        'notifyChannels': {'webUi': True, 'telegram': True}
    })
    assert save_resp.status_code == 200
    saved_data = save_resp.json()
    assert saved_data['policy']['hasCustomOverride'] is True
    assert saved_data['policy']['thresholds']['cpuPercent'] == 99

    # Fetch device policy
    get_resp = client.get(f'/api/v1/devices/{dev_id}/alert-policy')
    assert get_resp.status_code == 200
    pol_data = get_resp.json()
    assert pol_data['hasCustomOverride'] is True
    assert pol_data['isInherited'] is False
    assert pol_data['thresholds']['cpuPercent'] == 99

    # Reset to Inherit
    reset_resp = client.post(f'/api/v1/devices/{dev_id}/alert-policy', json={
        'mode': 'Inherit'
    })
    assert reset_resp.status_code == 200
    reset_data = reset_resp.json()
    assert reset_data['policy']['hasCustomOverride'] is False
    assert reset_data['policy']['isInherited'] is True

    # Fetch again -> now inherited
    get_after_reset = client.get(f'/api/v1/devices/{dev_id}/alert-policy')
    assert get_after_reset.status_code == 200
    pol_after_reset = get_after_reset.json()
    assert pol_after_reset['hasCustomOverride'] is False
    assert pol_after_reset['isInherited'] is True



