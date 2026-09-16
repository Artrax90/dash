import pytest
import urllib.parse
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.api.v1.system_logs import detect_log_level, in_memory_log_buffer

client = TestClient(app)

def test_system_logs_forbidden_for_non_superadmin():
    # Regular user / operator should be denied (403)
    resp = client.get(
        "/api/v1/system/logs",
        headers={"X-User-Role": "Operator", "X-Username": "operator"}
    )
    assert resp.status_code == 403

def test_system_logs_forbidden_for_fleet_admin():
    # Fleet admin is NOT superadmin -> denied (403)
    resp = client.get(
        "/api/v1/system/logs",
        headers={"X-User-Role": "FleetAdmin", "X-Username": "fleet_admin"}
    )
    assert resp.status_code == 403

def test_system_containers_list_for_superadmin():
    # Superadmin should get list of containers (200)
    resp = client.get(
        "/api/v1/system/containers",
        headers={"X-User-Role": "SuperAdmin", "X-Username": "admin"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "containers" in data
    container_names = [c["name"] for c in data["containers"]]
    assert "workstation-manager" in container_names

def test_system_logs_allowed_for_superadmin_and_filtering():
    # Superadmin fetches logs
    resp = client.get(
        "/api/v1/system/logs?container=workstation-manager&tail=50",
        headers={"X-User-Role": urllib.parse.quote("Суперадминистратор"), "X-Username": "admin"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "logs" in data
    assert "container" in data
    assert data["container"] == "workstation-manager"
    assert isinstance(data["logs"], list)

def test_system_logs_search_and_level_filter():
    # Superadmin searches for specific level
    resp = client.get(
        "/api/v1/system/logs?container=workstation-manager&level=ERROR",
        headers={"X-User-Role": "SuperAdmin", "X-Username": "admin"}
    )
    assert resp.status_code == 200
    data = resp.json()
    for log_entry in data["logs"]:
        assert log_entry["level"].upper() == "ERROR"

def test_detect_log_level_precedence_and_stderr_bug():
    # Issue reported by user: a line with [INFO] and &stderr=1 inside the URL was falsely marked ERROR!
    line = '2026-09-16 16:08:25,024 [INFO] HTTP Request: GET http://localhost/containers/workstation-manager/logs?stdout=1&stderr=1&tail=500&timestamps=1 "HTTP/1.1 200 OK"'
    assert detect_log_level(line, stream="stderr") == "INFO"

    # [WARNING] should be WARN
    line_warn = '2026-09-16 16:08:25,024 [WARNING] High memory usage detected'
    assert detect_log_level(line_warn, stream="stderr") == "WARN"

    # [ERROR] should be ERROR
    line_err = '2026-09-16 16:08:25,024 [ERROR] Database connection lost'
    assert detect_log_level(line_err, stream="stdout") == "ERROR"

def test_system_logs_date_range_since_and_until_filtering():
    # Inject test logs with timestamps
    in_memory_log_buffer.append({
        "timestamp": "2026-09-16T10:00:00Z",
        "level": "INFO",
        "stream": "stdout",
        "message": "Morning event",
        "raw": "2026-09-16T10:00:00Z [INFO] Morning event"
    })
    in_memory_log_buffer.append({
        "timestamp": "2026-09-16T14:00:00Z",
        "level": "INFO",
        "stream": "stdout",
        "message": "Afternoon event",
        "raw": "2026-09-16T14:00:00Z [INFO] Afternoon event"
    })
    in_memory_log_buffer.append({
        "timestamp": "2026-09-16T18:00:00Z",
        "level": "INFO",
        "stream": "stdout",
        "message": "Evening event",
        "raw": "2026-09-16T18:00:00Z [INFO] Evening event"
    })

    # Query with since and until
    resp = client.get(
        "/api/v1/system/logs?container=workstation-manager&since=2026-09-16T12:00:00Z&until=2026-09-16T16:00:00Z",
        headers={"X-User-Role": "SuperAdmin", "X-Username": "admin"}
    )
    assert resp.status_code == 200
    messages = [l["message"] for l in resp.json()["logs"]]
    assert "Afternoon event" in messages
    assert "Morning event" not in messages
    assert "Evening event" not in messages

def test_system_logs_filters_internal_polling_spam():
    in_memory_log_buffer.append({
        "timestamp": "2026-09-16T14:05:00Z",
        "level": "INFO",
        "stream": "stdout",
        "message": 'HTTP Request: GET http://localhost/containers/workstation-manager/logs?stdout=1&stderr=1 "HTTP/1.1 200 OK"',
        "raw": '2026-09-16T14:05:00Z [INFO] HTTP Request: GET http://localhost/containers/workstation-manager/logs?stdout=1&stderr=1 "HTTP/1.1 200 OK"'
    })
    resp = client.get(
        "/api/v1/system/logs?container=workstation-manager&tail=100",
        headers={"X-User-Role": "SuperAdmin", "X-Username": "admin"}
    )
    assert resp.status_code == 200
    messages = [l["message"] for l in resp.json()["logs"]]
    for m in messages:
        assert "containers/workstation-manager/logs" not in m

def test_system_logs_exclude_routine():
    in_memory_log_buffer.append({
        "timestamp": "2026-09-16T14:10:00Z",
        "level": "INFO",
        "stream": "stdout",
        "message": '172.16.42.0:51780 - "POST /api/v1/agents/heartbeat HTTP/1.1" 200 OK',
        "raw": '2026-09-16T14:10:00Z INFO: 172.16.42.0:51780 - "POST /api/v1/agents/heartbeat HTTP/1.1" 200 OK'
    })
    in_memory_log_buffer.append({
        "timestamp": "2026-09-16T14:10:01Z",
        "level": "INFO",
        "stream": "stdout",
        "message": '172.16.42.0:51780 - "POST /api/v1/agents/update-status HTTP/1.1" 200 OK',
        "raw": '2026-09-16T14:10:01Z INFO: 172.16.42.0:51780 - "POST /api/v1/agents/update-status HTTP/1.1" 200 OK'
    })
    in_memory_log_buffer.append({
        "timestamp": "2026-09-16T14:10:02Z",
        "level": "INFO",
        "stream": "stdout",
        "message": '[WoL Success] Dispatched 32 Magic Packets for 00:58:3F:15:1D:D1',
        "raw": '2026-09-16T14:10:02Z [INFO] [WoL Success] Dispatched 32 Magic Packets for 00:58:3F:15:1D:D1'
    })

    resp = client.get(
        "/api/v1/system/logs?container=workstation-manager&exclude_routine=true",
        headers={"X-User-Role": "SuperAdmin", "X-Username": "admin"}
    )
    assert resp.status_code == 200
    messages = [l["message"] for l in resp.json()["logs"]]
    assert any("[WoL Success]" in m for m in messages)
    assert not any("heartbeat" in m for m in messages)
    assert not any("update-status" in m for m in messages)

def test_system_logs_exclude_custom_phrase():
    in_memory_log_buffer.append({
        "timestamp": "2026-09-16T14:15:00Z",
        "level": "INFO",
        "stream": "stdout",
        "message": 'Special task starting for device PC-99',
        "raw": '2026-09-16T14:15:00Z [INFO] Special task starting for device PC-99'
    })
    in_memory_log_buffer.append({
        "timestamp": "2026-09-16T14:15:01Z",
        "level": "INFO",
        "stream": "stdout",
        "message": 'Routine noise that we want to omit: NOISE_XYZ',
        "raw": '2026-09-16T14:15:01Z [INFO] Routine noise that we want to omit: NOISE_XYZ'
    })

    resp = client.get(
        "/api/v1/system/logs?container=workstation-manager&exclude=NOISE_XYZ,other_word",
        headers={"X-User-Role": "SuperAdmin", "X-Username": "admin"}
    )
    assert resp.status_code == 200
    messages = [l["message"] for l in resp.json()["logs"]]
    assert any("Special task starting" in m for m in messages)
    assert not any("NOISE_XYZ" in m for m in messages)

def test_system_logs_category_filter():
    in_memory_log_buffer.append({
        "timestamp": "2026-09-16T14:20:00Z",
        "level": "INFO",
        "stream": "stdout",
        "message": '172.16.44.188:64626 - "GET /install.ps1 HTTP/1.1" 200 OK',
        "raw": '2026-09-16T14:20:00Z INFO: 172.16.44.188:64626 - "GET /install.ps1 HTTP/1.1" 200 OK'
    })
    in_memory_log_buffer.append({
        "timestamp": "2026-09-16T14:20:01Z",
        "level": "INFO",
        "stream": "stdout",
        "message": '[Scheduler] Rule Недельный цикл triggered WAKE',
        "raw": '2026-09-16T14:20:01Z [INFO] [Scheduler] Rule Недельный цикл triggered WAKE'
    })

    # category=system should exclude HTTP access logs
    resp_sys = client.get(
        "/api/v1/system/logs?container=workstation-manager&category=system",
        headers={"X-User-Role": "SuperAdmin", "X-Username": "admin"}
    )
    assert resp_sys.status_code == 200
    sys_messages = [l["message"] for l in resp_sys.json()["logs"]]
    assert any("[Scheduler]" in m for m in sys_messages)
    assert not any("GET /install.ps1" in m for m in sys_messages)

    # category=http should include HTTP access logs
    resp_http = client.get(
        "/api/v1/system/logs?container=workstation-manager&category=http",
        headers={"X-User-Role": "SuperAdmin", "X-Username": "admin"}
    )
    assert resp_http.status_code == 200
    http_messages = [l["message"] for l in resp_http.json()["logs"]]
    assert any("GET /install.ps1" in m for m in http_messages)
    assert not any("[Scheduler]" in m for m in http_messages)

