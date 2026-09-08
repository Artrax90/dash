import pytest
from httpx import AsyncClient
from backend.app.main import app
from backend.app.services.backup_service import backup_service

@pytest.mark.anyio
async def test_create_system_backup_contains_all_entities():
    backup_data = await backup_service.create_backup()
    assert isinstance(backup_data, dict)
    assert backup_data.get("status") == "success"
    assert "version" in backup_data
    assert "tables" in backup_data
    assert "devices" in backup_data["tables"]
    assert "exportedAt" in backup_data
    assert "checksum" in backup_data

def test_backup_endpoint_returns_json_attachment():
    from fastapi.testclient import TestClient
    client = TestClient(app)
    res = client.get("/api/v1/system/backup")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "success"
    assert "tables" in data
    assert "devices" in data["tables"]

def test_restore_and_cleanup_endpoints():
    from fastapi.testclient import TestClient
    client = TestClient(app)
    
    # 1. Cleanup endpoint
    res_clean = client.post("/api/v1/system/cleanup", json={"days": 60})
    assert res_clean.status_code == 200
    assert res_clean.json().get("status") == "success"
    
    # 2. Restore endpoint with valid payload
    res_backup = client.get("/api/v1/system/backup")
    backup_json = res_backup.json()
    res_restore = client.post("/api/v1/system/restore", json=backup_json)
    assert res_restore.status_code == 200
    assert res_restore.json().get("status") == "success"
