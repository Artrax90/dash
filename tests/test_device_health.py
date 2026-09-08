import pytest
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.app.db.session import Base
from backend.app.models.device import Device, HealthStatus, PowerStatus, AgentStatus
from backend.app.models.hardware import HardwareChangeModel, HardwareBaselineModel
from backend.app.models.alert import AlertModel
from backend.app.api.v1.hardware import set_baseline
from backend.app.api.v1.alerts import resolve_alert, resolve_all_alerts

class DummyRequest:
    headers = {"X-User-Name": "Admin"}

async def get_test_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)()

@pytest.mark.anyio
async def test_set_baseline_resets_device_health_to_healthy():
    session = await get_test_session()
    async with session:
        device = Device(
            id="PC-TEST01",
            name="TestPC",
            hostname="test-host",
            group_name="Office",
            mac_address="00:11:22:33:44:55",
            ip_address="192.168.1.50",
            power_status=PowerStatus.ON,
            agent_status=AgentStatus.CONNECTED,
            health_status=HealthStatus.CRITICAL,
            last_seen=datetime.utcnow()
        )
        session.add(device)
        
        change = HardwareChangeModel(
            id="HWC-001",
            device_id="PC-TEST01",
            component="RAM",
            change_type="MODIFIED",
            severity="Critical",
            previous_value="16 GB",
            current_value="32 GB",
            diff_status="MISMATCH"
        )
        session.add(change)
        
        alert = AlertModel(
            id="ALT-001",
            device_id="PC-TEST01",
            alert_type="HARDWARE_MISMATCH",
            severity="Critical",
            state="Open",
            description="Несоответствие эталону: ОЗУ"
        )
        session.add(alert)
        await session.commit()

        payload = {
            "approvedBy": "Admin",
            "spec": {"ram": {"totalGb": 32}}
        }
        res = await set_baseline("PC-TEST01", payload, DummyRequest(), session)
        assert res["status"] == "success"

        dev_res = await session.execute(select(Device).where(Device.id == "PC-TEST01"))
        updated_dev = dev_res.scalar_one()
        assert updated_dev.health_status == HealthStatus.HEALTHY, f"Expected HEALTHY, got {updated_dev.health_status}"

        alt_res = await session.execute(select(AlertModel).where(AlertModel.id == "ALT-001"))
        updated_alt = alt_res.scalar_one()
        assert updated_alt.state == "Resolved"

@pytest.mark.anyio
async def test_resolve_alert_restores_healthy_status_when_no_other_issues():
    session = await get_test_session()
    async with session:
        device = Device(
            id="PC-TEST02",
            name="TestPC2",
            hostname="test-host2",
            mac_address="00:11:22:33:44:56",
            ip_address="192.168.1.51",
            power_status=PowerStatus.ON,
            agent_status=AgentStatus.CONNECTED,
            health_status=HealthStatus.CRITICAL,
            last_seen=datetime.utcnow()
        )
        session.add(device)

        alert = AlertModel(
            id="ALT-002",
            device_id="PC-TEST02",
            alert_type="HIGH_CPU",
            severity="Critical",
            state="Open",
            description="Загрузка ЦП 95%"
        )
        session.add(alert)
        await session.commit()

        await resolve_alert("ALT-002", DummyRequest(), session)

        dev_res = await session.execute(select(Device).where(Device.id == "PC-TEST02"))
        updated_dev = dev_res.scalar_one()
        assert updated_dev.health_status == HealthStatus.HEALTHY

@pytest.mark.anyio
async def test_resolve_all_alerts_restores_devices_to_healthy():
    session = await get_test_session()
    async with session:
        device = Device(
            id="PC-TEST03",
            name="TestPC3",
            hostname="test-host3",
            mac_address="00:11:22:33:44:57",
            ip_address="192.168.1.52",
            power_status=PowerStatus.ON,
            agent_status=AgentStatus.CONNECTED,
            health_status=HealthStatus.WARNING,
            last_seen=datetime.utcnow()
        )
        session.add(device)

        alert = AlertModel(
            id="ALT-003",
            device_id="PC-TEST03",
            alert_type="HIGH_RAM",
            severity="Warning",
            state="Open",
            description="Память 90%"
        )
        session.add(alert)
        await session.commit()

        await resolve_all_alerts(DummyRequest(), session)

        dev_res = await session.execute(select(Device).where(Device.id == "PC-TEST03"))
        updated_dev = dev_res.scalar_one()
        assert updated_dev.health_status == HealthStatus.HEALTHY
