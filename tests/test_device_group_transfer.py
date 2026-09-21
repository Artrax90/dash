import pytest
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.app.db.session import Base
from backend.app.models.device import Device, HealthStatus, PowerStatus, AgentStatus
from backend.app.api.v1.devices import update_device

class DummyRequest:
    def __init__(self, role="Суперадминистратор", username="admin"):
        self.headers = {
            "X-User-Role": role,
            "X-Username": username
        }

async def get_test_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)()

@pytest.mark.anyio
async def test_device_group_transfer_auto_syncs_hierarchy():
    session = await get_test_session()
    async with session:
        dev = Device(
            id="DEV-TRANSFER-01",
            name="PC-TRANSFER-01",
            hostname="host-transfer-01",
            group_name="Office",
            building="",
            floor="",
            room="",
            mac_address="00:11:22:33:44:55",
            ip_address="192.168.1.101",
            power_status=PowerStatus.ON,
            agent_status=AgentStatus.CONNECTED,
            health_status=HealthStatus.HEALTHY,
            last_seen=datetime.utcnow()
        )
        session.add(dev)
        await session.commit()

        req = DummyRequest()
        # Transfer device from Office to "МНОК / 5 этаж / 518Т"
        payload = {
            "groups": ["МНОК / 5 этаж / 518Т"]
        }
        res = await update_device("DEV-TRANSFER-01", payload, req, db=session)
        assert res is not None

        # Re-query
        q = await session.execute(select(Device).where(Device.id == "DEV-TRANSFER-01"))
        updated = q.scalar_one()
        assert updated.group_name == "МНОК / 5 этаж / 518Т"
        assert updated.building == "МНОК"
        assert updated.floor == "5 этаж"
        assert updated.room == "518Т"

@pytest.mark.anyio
async def test_device_group_transfer_from_old_building_to_new_building():
    session = await get_test_session()
    async with session:
        dev = Device(
            id="DEV-TRANSFER-02",
            name="PC-TRANSFER-02",
            hostname="host-transfer-02",
            group_name="МНОК / 5 этаж / 518Т",
            building="МНОК",
            floor="5 этаж",
            room="518Т",
            mac_address="00:11:22:33:44:66",
            ip_address="192.168.1.102",
            power_status=PowerStatus.ON,
            agent_status=AgentStatus.CONNECTED,
            health_status=HealthStatus.HEALTHY,
            last_seen=datetime.utcnow()
        )
        session.add(dev)
        await session.commit()

        req = DummyRequest()
        # Transfer to a different building without passing building explicitly
        payload = {
            "groups": ["ЦК B4 / 5 этаж / 513"]
        }
        res = await update_device("DEV-TRANSFER-02", payload, req, db=session)
        assert res is not None

        q = await session.execute(select(Device).where(Device.id == "DEV-TRANSFER-02"))
        updated = q.scalar_one()
        assert updated.group_name == "ЦК B4 / 5 этаж / 513"
        assert updated.building == "ЦК B4"
        assert updated.floor == "5 этаж"
        assert updated.room == "513"
