import time
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.app.api.v1.devices import (
    get_device_stats,
    invalidate_device_stats_cache,
    _stats_cache,
    _STATS_CACHE_TTL,
    list_devices,
    invalidate_devices_cache,
    _devices_cache
)
from backend.app.api.v1.agents import (
    should_broadcast_device_update,
    _last_device_broadcast_state
)
from backend.app.api.v1.alerts import (
    list_alerts,
    invalidate_alerts_cache,
    _alerts_cache
)
from backend.app.api.v1.sessions import (
    list_sessions,
    live_device_sessions,
    update_device_sessions
)

@pytest.mark.anyio
async def test_device_stats_in_memory_caching():
    invalidate_device_stats_cache()
    assert len(_stats_cache) == 0

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    
    # Mock return value of db.execute
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    mock_request = MagicMock()
    mock_request.headers = {}
    mock_request.state = MagicMock()

    # First call - cache miss, should query DB
    res1 = await get_device_stats(mock_request, db=mock_db)
    assert res1["total"] == 0
    assert mock_db.execute.call_count == 1
    assert len(_stats_cache) > 0

    # Second call within TTL - cache hit, should NOT query DB again
    res2 = await get_device_stats(mock_request, db=mock_db)
    assert res2 == res1
    assert mock_db.execute.call_count == 1  # call count stayed at 1!

    # Invalidate cache
    invalidate_device_stats_cache()
    assert len(_stats_cache) == 0

    # Third call after invalidation - should query DB again
    res3 = await get_device_stats(mock_request, db=mock_db)
    assert res3 == res1
    assert mock_db.execute.call_count == 2


def test_device_heartbeat_broadcast_throttling():
    _last_device_broadcast_state.clear()
    dev_id = "PC-BENCH-01"

    # 1. Initial call for a new device -> MUST broadcast
    state1 = {
        "ip": "192.168.1.50",
        "power": "Online",
        "agent": "Online",
        "rdp": "Stopped",
        "sessions_count": 0,
        "health": "Healthy",
    }
    assert should_broadcast_device_update(dev_id, state1) is True

    # 2. Immediate second call with identical state -> MUST be throttled (False)
    assert should_broadcast_device_update(dev_id, state1) is False

    # 3. Third call 2 seconds later with identical state -> STILL throttled (False)
    assert should_broadcast_device_update(dev_id, state1) is False

    # 4. State change: User connects via RDP -> MUST broadcast immediately (True)
    state_rdp_connected = dict(state1, rdp="Active", sessions_count=1)
    assert should_broadcast_device_update(dev_id, state_rdp_connected) is True

    # 5. Immediate repeated call with same RDP state -> throttled (False)
    assert should_broadcast_device_update(dev_id, state_rdp_connected) is False

    # 6. State change: Power status changed -> MUST broadcast immediately (True)
    state_power_off = dict(state_rdp_connected, power="Offline")
    assert should_broadcast_device_update(dev_id, state_power_off) is True

    # 7. Time elapsed > 30s with identical state -> periodic broadcast allowed (True)
    _last_device_broadcast_state[dev_id]["ts"] = time.time() - 35
    assert should_broadcast_device_update(dev_id, state_power_off) is True


@pytest.mark.anyio
async def test_list_sessions_fast_path_when_empty():
    update_device_sessions("PC-NO-SESS", sessions_list=[])
    assert "PC-NO-SESS" in live_device_sessions
    assert live_device_sessions["PC-NO-SESS"] == []

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()

    # Must return [] immediately from memory without touching db
    res = await list_sessions(device_id="PC-NO-SESS", db=mock_db)
    assert res == []
    mock_db.execute.assert_not_called()


@pytest.mark.anyio
async def test_list_alerts_caching():
    invalidate_alerts_cache()
    mock_db = AsyncMock()
    
    mock_dev_res = MagicMock()
    mock_dev_res.scalars.return_value.all.return_value = []
    
    mock_alert_res = MagicMock()
    mock_alert_res.scalars.return_value.all.return_value = []
    
    mock_db.execute.side_effect = [mock_dev_res, mock_alert_res]

    # First call: queries db
    res1 = await list_alerts(db=mock_db)
    assert mock_db.execute.call_count == 2
    assert len(_alerts_cache) > 0

    # Second call: returns cached without querying db again
    res2 = await list_alerts(db=mock_db)
    assert res2 == res1
    assert mock_db.execute.call_count == 2


@pytest.mark.anyio
async def test_list_devices_caching():
    invalidate_devices_cache()
    mock_db = AsyncMock()
    
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_res

    mock_request = MagicMock()
    mock_request.headers = {}
    mock_request.state = MagicMock()

    # First call: executes queries
    res1 = await list_devices(mock_request, db=mock_db)
    count_after_first = mock_db.execute.call_count
    assert count_after_first > 0

    # Second call within TTL: returns cached
    res2 = await list_devices(mock_request, db=mock_db)
    assert res2 == res1
    assert mock_db.execute.call_count == count_after_first
