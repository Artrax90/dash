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
    assert pg_opts.get("pool_size") == 20
    assert pg_opts.get("max_overflow") == 15
    assert pg_opts.get("pool_pre_ping") is True

    sqlite_opts = get_engine_options("sqlite+aiosqlite:///./data/workstation_manager.db")
    assert "pool_size" not in sqlite_opts
    assert "max_overflow" not in sqlite_opts

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

    # Run it a second time: must be idempotent and not crash or attempt duplicate column creation
    with mem_engine.begin() as conn:
        safe_migrate_columns_sync(conn)

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

