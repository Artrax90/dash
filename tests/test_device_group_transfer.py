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

@pytest.mark.anyio
async def test_fleet_admin_hierarchical_scope_transfer_success():
    from unittest.mock import patch
    from fastapi import HTTPException
    session = await get_test_session()
    async with session:
        dev = Device(
            id="DEV-TRANSFER-03",
            name="PC-TRANSFER-03",
            hostname="host-transfer-03",
            group_name="Office",
            building="",
            floor="",
            room="",
            mac_address="00:11:22:33:44:77",
            ip_address="192.168.1.103",
            power_status=PowerStatus.ON,
            agent_status=AgentStatus.CONNECTED,
            health_status=HealthStatus.HEALTHY,
            last_seen=datetime.utcnow()
        )
        session.add(dev)
        await session.commit()

        # Fleet admin with scope "МНОК"
        mock_user = [{
            "username": "fleet_admin",
            "role": "Администратор парка",
            "scope": "Группы: МНОК",
            "allowedGroups": ["МНОК"]
        }]
        req = DummyRequest(role="Администратор парка", username="fleet_admin")
        payload = {"groups": ["МНОК / 5 этаж / 518Т"]}
        with patch("backend.app.api.v1.users.load_users", return_value=mock_user):
            res = await update_device("DEV-TRANSFER-03", payload, req, db=session)
            assert res is not None

        q = await session.execute(select(Device).where(Device.id == "DEV-TRANSFER-03"))
        updated = q.scalar_one()
        assert updated.group_name == "МНОК / 5 этаж / 518Т"
        assert updated.building == "МНОК"
        assert updated.floor == "5 этаж"
        assert updated.room == "518Т"

@pytest.mark.anyio
async def test_fleet_admin_forbidden_transfer_outside_scope():
    from unittest.mock import patch
    from fastapi import HTTPException
    session = await get_test_session()
    async with session:
        dev = Device(
            id="DEV-TRANSFER-04",
            name="PC-TRANSFER-04",
            hostname="host-transfer-04",
            group_name="МНОК / 5 этаж / 518Т",
            building="МНОК",
            floor="5 этаж",
            room="518Т",
            mac_address="00:11:22:33:44:88",
            ip_address="192.168.1.104",
            power_status=PowerStatus.ON,
            agent_status=AgentStatus.CONNECTED,
            health_status=HealthStatus.HEALTHY,
            last_seen=datetime.utcnow()
        )
        session.add(dev)
        await session.commit()

        # Fleet admin with scope "МНОК" tries to transfer to "УЛК"
        mock_user = [{
            "username": "fleet_admin",
            "role": "Администратор парка",
            "scope": "Группы: МНОК",
            "allowedGroups": ["МНОК"]
        }]
        req = DummyRequest(role="Администратор парка", username="fleet_admin")
        payload = {"groups": ["УЛК / 3 этаж / 301"]}
        with patch("backend.app.api.v1.users.load_users", return_value=mock_user):
            with pytest.raises(HTTPException) as exc_info:
                await update_device("DEV-TRANSFER-04", payload, req, db=session)
            assert exc_info.value.status_code == 403
            assert "не входит в вашу зону ответственности" in exc_info.value.detail

@pytest.mark.anyio
async def test_fleet_admin_room_level_scope_transfer_success():
    from unittest.mock import patch
    session = await get_test_session()
    async with session:
        dev = Device(
            id="DEV-TRANSFER-05",
            name="PC-TRANSFER-05",
            hostname="host-transfer-05",
            group_name="Office",
            building="",
            floor="",
            room="",
            mac_address="00:11:22:33:44:99",
            ip_address="192.168.1.105",
            power_status=PowerStatus.ON,
            agent_status=AgentStatus.CONNECTED,
            health_status=HealthStatus.HEALTHY,
            last_seen=datetime.utcnow()
        )
        session.add(dev)
        await session.commit()

        # Fleet admin with room-level scope "518Т"
        mock_user = [{
            "username": "fleet_admin",
            "role": "Администратор парка",
            "scope": "Группы: 518Т",
            "allowedGroups": ["518Т"]
        }]
        req = DummyRequest(role="Администратор парка", username="fleet_admin")
        payload = {"groups": ["МНОК / 5 этаж / 518Т"]}
        with patch("backend.app.api.v1.users.load_users", return_value=mock_user):
            res = await update_device("DEV-TRANSFER-05", payload, req, db=session)
            assert res is not None

        q = await session.execute(select(Device).where(Device.id == "DEV-TRANSFER-05"))
        updated = q.scalar_one()
        assert updated.group_name == "МНОК / 5 этаж / 518Т"
        assert updated.building == "МНОК"
        assert updated.floor == "5 этаж"
        assert updated.room == "518Т"
