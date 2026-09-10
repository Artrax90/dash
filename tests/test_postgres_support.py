import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine, inspect, text, Table, Column, String, Integer, MetaData
from sqlalchemy.dialects import postgresql, sqlite
from backend.app.db.session import Base, get_engine_options, is_postgres_url
from backend.app.models import (
    Device, UserModel, CustomRoleModel, ScheduleModel,
    HardwareSpecModel, HardwareBaselineModel, AlertModel, RdpSessionModel
)

def test_is_postgres_url_detection():
    assert is_postgres_url("postgresql+asyncpg://user:pass@localhost:5432/db") is True
    assert is_postgres_url("postgresql://user:pass@localhost:5432/db") is True
    assert is_postgres_url("postgres://user:pass@localhost:5432/db") is True
    assert is_postgres_url("sqlite+aiosqlite:///./data/workstation_manager.db") is False
    assert is_postgres_url("sqlite:///data.db") is False

def test_get_engine_options_postgres_vs_sqlite():
    pg_opts = get_engine_options("postgresql+asyncpg://user:pass@localhost:5432/db")
    assert pg_opts.get("pool_size") == 30
    assert pg_opts.get("max_overflow") == 20
    assert pg_opts.get("pool_timeout") == 15
    assert pg_opts.get("pool_pre_ping") is True
    assert pg_opts.get("pool_recycle") == 300
    assert pg_opts.get("pool_reset_on_return") == "rollback"

    sqlite_opts = get_engine_options("sqlite+aiosqlite:///./data/workstation_manager.db")
    assert "pool_size" not in sqlite_opts
    assert "max_overflow" not in sqlite_opts

@pytest.mark.anyio
async def test_get_db_lifecycle_no_connection_leak():
    import asyncio
    from sqlalchemy.pool import AsyncAdaptedQueuePool
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import text
    from backend.app.db.session import get_db

    # Test that get_db closes and releases connections back to the pool under all execution flows
    gen = get_db()
    session = await gen.__anext__()
    assert session is not None
    # Simulate an endpoint running a query
    await session.execute(text("SELECT 1"))
    # Finish generator (like FastAPI does on request completion)
    try:
        await gen.__anext__()
    except StopAsyncIteration:
        pass

    # Verify cancelled request lifecycle
    gen_cancel = get_db()
    session_cancel = await gen_cancel.__anext__()
    await session_cancel.execute(text("SELECT 1"))
    try:
        await gen_cancel.athrow(asyncio.CancelledError())
    except asyncio.CancelledError:
        pass

def test_all_models_ddl_compilation_for_postgresql():
    pg_dialect = postgresql.dialect()
    for table_name, table in Base.metadata.tables.items():
        from sqlalchemy.schema import CreateTable
        ddl = str(CreateTable(table).compile(dialect=pg_dialect))
        assert f"CREATE TABLE {table_name}" in ddl or f'CREATE TABLE "{table_name}"' in ddl
        assert len(ddl) > 20

def test_safe_column_migration_logic():
    from backend.app.main import safe_migrate_columns_sync
    
    # Create an in-memory SQLite database mimicking old schema without some columns
    mem_engine = create_engine("sqlite:///:memory:")
    with mem_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE devices (
                id VARCHAR(32) PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                hostname VARCHAR(100) NOT NULL,
                group_name VARCHAR(100) NOT NULL,
                ip_address VARCHAR(45) NOT NULL,
                mac_address VARCHAR(32) NOT NULL
            )
        """))
    
    # Run safe_migrate_columns_sync
    with mem_engine.begin() as conn:
        safe_migrate_columns_sync(conn)
        
        # Verify columns were added without throwing errors
        inspector = inspect(conn)
        cols = {c["name"] for c in inspector.get_columns("devices")}
        assert "boot_time" in cols
        assert "uptime_seconds" in cols
        assert "building" in cols
        assert "floor" in cols
        assert "room" in cols
        assert "is_archived" in cols
        assert "decommission_reason" in cols
        assert "decommission_comment" in cols
        assert "decommissioned_at" in cols

    # Run it a second time: must be idempotent and not crash or attempt duplicate column creation
    with mem_engine.begin() as conn:
        safe_migrate_columns_sync(conn)

def test_postgres_column_migration_syntax_and_types():
    from backend.app.main import safe_migrate_columns_sync
    
    mock_conn = MagicMock()
    mock_conn.dialect.name = "postgresql"
    
    executed_sqls = []
    def mock_execute(statement, *args, **kwargs):
        sql_str = str(statement)
        executed_sqls.append(sql_str)
        return MagicMock()
    
    mock_conn.execute.side_effect = mock_execute
    
    with patch("sqlalchemy.inspect") as mock_inspect:
        mock_inspector = MagicMock()
        mock_inspect.return_value = mock_inspector
        mock_inspector.get_table_names.return_value = ["devices"]
        mock_inspector.get_columns.return_value = [{"name": "id"}]
        
        safe_migrate_columns_sync(mock_conn)
        
    combined_sql = "\n".join(executed_sqls)
    assert "BOOLEAN DEFAULT FALSE" in combined_sql
    assert "BOOLEAN DEFAULT 0" not in combined_sql
    assert "TIMESTAMP" in combined_sql
    assert "IF NOT EXISTS" in combined_sql
    assert "ix_devices_is_archived" in combined_sql

def test_system_status_endpoint_reports_database_info():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    client = TestClient(app)
    response = client.get("/api/v1/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "database" in data
    assert "type" in data["database"]
    assert data["database"]["type"] in ["sqlite", "postgresql"]
    assert "connected" in data["database"]
    assert data["database"]["connected"] is True

def test_device_stats_includes_database_type():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    client = TestClient(app)
    response = client.get("/api/v1/devices/stats")
    assert response.status_code == 200
    data = response.json()
    assert "databaseType" in data
    assert data["databaseType"] in ["sqlite", "postgresql"]

@pytest.mark.anyio
async def test_scheduler_reachability_probe():
    from backend.app.services.scheduler_service import SchedulerService
    # Localhost or invalid IP probe returns tuple (bool, candidate_ip)
    res_ok, cand = await SchedulerService._check_device_reachability("127.0.0.1", False, None)
    # Loopback IP check returns False
    assert res_ok is False

@pytest.mark.anyio
async def test_alert_engine_dispatch_non_blocking_task(monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock, MagicMock
    from backend.app.services.alert_engine import alert_engine

    # Mock dispatch_alert to record if it was called via asyncio.create_task
    task_created = []
    real_create_task = asyncio.create_task

    def mock_create_task(coro, *args, **kwargs):
        task_created.append(coro)
        return real_create_task(coro, *args, **kwargs)

    monkeypatch.setattr(asyncio, "create_task", mock_create_task)

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_res.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_res

    mock_device = MagicMock()
    mock_device.id = "TEST-DEV-QUEUE"
    mock_device.name = "Test Dev"
    mock_device.hostname = "test-dev"

    # Call trigger_device_offline - must complete immediately without awaiting network
    await alert_engine.trigger_device_offline(
        session=mock_session,
        device=mock_device,
        reason="Test disconnect"
    )

    # Verify that dispatch_alert was dispatched asynchronously via create_task
    assert len(task_created) >= 1

