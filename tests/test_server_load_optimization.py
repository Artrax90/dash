import pytest
import time
from unittest.mock import patch, MagicMock
from backend.app.api.v1.agents import agent_settings
from backend.app.models.device import Device, PowerStatus, AgentStatus

def test_default_heartbeat_interval_is_30_seconds():
    assert agent_settings["defaultHeartbeatInterval"] >= 25, (
        f"defaultHeartbeatInterval is {agent_settings['defaultHeartbeatInterval']}, should be at least 25-30s"
    )
    for group, interval in agent_settings.get("groupHeartbeatIntervals", {}).items():
        assert interval >= 25, f"Group {group} interval is {interval}, should be at least 25-30s"

def test_scheduler_skips_ping_for_already_off_agent_devices():
    from backend.app.services.scheduler_service import scheduler_service

    off_agent_dev = Device(
        id="PC-TEST-OFF",
        name="PC-TEST-OFF",
        ip_address="172.16.45.10",
        power_status=PowerStatus.OFF,
        agent_status=AgentStatus.DISCONNECTED,
        agent_version="1.5.0",
        last_seen=None
    )

    should_ping = scheduler_service.should_probe_device(off_agent_dev)
    assert should_ping is False, "Scheduler should NOT ping an agent-managed PC that is already OFF!"

    on_agent_dev = Device(
        id="PC-TEST-ON",
        name="PC-TEST-ON",
        ip_address="172.16.45.11",
        power_status=PowerStatus.ON,
        agent_status=AgentStatus.DISCONNECTED,
        agent_version="1.5.0",
        last_seen=None
    )
    assert scheduler_service.should_probe_device(on_agent_dev) is True

    agentless_off_dev = Device(
        id="TC-TEST",
        name="TC-TEST",
        ip_address="172.16.45.12",
        power_status=PowerStatus.OFF,
        agent_status=AgentStatus.DISCONNECTED,
        agent_version="Agentless",
        last_seen=None
    )
    assert scheduler_service.should_probe_device(agentless_off_dev) is True

def test_save_device_processes_is_throttled():
    from backend.app.api.v1.devices import maybe_save_device_processes

    with patch("backend.app.api.v1.devices.save_device_processes") as mock_save:
        maybe_save_device_processes({"PC-1": [{"name": "proc1"}]}, min_interval=60.0)
        maybe_save_device_processes({"PC-1": [{"name": "proc1"}]}, min_interval=60.0)
        assert mock_save.call_count <= 1

def test_version_info_cache():
    from backend.app.api.v1.agents import _get_cached_version_info, _set_cached_version_info

    _set_cached_version_info({"currentVersion": "1.5.0", "totalAgents": 30})
    cached = _get_cached_version_info(max_age=10.0)
    assert cached is not None
    assert cached["currentVersion"] == "1.5.0"
