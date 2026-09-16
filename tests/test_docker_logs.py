import pytest
import urllib.parse
from fastapi.testclient import TestClient
from backend.app.main import app

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
        assert log_entry["level"].upper() == "ERROR" or "err" in log_entry["message"].lower()
