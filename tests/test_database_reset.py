import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.backup_service import backup_service
from backend.app.db.session import AsyncSessionLocal
from backend.app.models.device import Device
from sqlalchemy import select

def test_reset_database_requires_exact_phrase():
    client = TestClient(app)
    res = client.post('/api/v1/system/reset-database', json={'confirmation': 'wrong phrase'})
    assert res.status_code == 400
    assert 'УДАЛИТЬ ВСЕ ДАННЫЕ' in res.json().get('detail', '')

def test_reset_database_service_and_endpoint():
    client = TestClient(app)
    res = client.post('/api/v1/system/reset-database', json={
        'confirmation': 'УДАЛИТЬ ВСЕ ДАННЫЕ',
        'keepCurrentUser': True
    })
    assert res.status_code == 200
    data = res.json()
    assert data.get('status') == 'success'
    assert 'resetAt' in data

@pytest.mark.anyio
async def test_reset_database_clears_tables():
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Device))
        devices = res.scalars().all()
        assert len(devices) == 0
