import json
import pytest
import sqlite3
from datetime import datetime
from sqlalchemy import create_engine, text, inspect
from backend.app.db.session import Base
from backend.app.models import (
    Device, UserModel, CustomRoleModel, ScheduleModel,
    HardwareSpecModel, HardwareBaselineModel, AlertModel, RdpSessionModel,
    AlertPolicyModel, TelegramSubscriberModel, OperationModel, AgentEnrollmentTokenModel,
    AuditLogModel, HardwareChangeModel
)
from scripts.migrate_sqlite_to_postgres import (
    get_ordered_tables,
    transform_row_for_target,
    migrate_data,
    find_sqlite_db_candidates
)

def test_get_ordered_tables_resolves_foreign_keys_correctly():
    ordered = get_ordered_tables()
    table_names = [t.name for t in ordered]
    
    # devices must come before hardware_specs, hardware_baselines, alerts, alert_policies, rdp_sessions
    assert table_names.index("devices") < table_names.index("hardware_specs")
    assert table_names.index("devices") < table_names.index("hardware_baselines")
    assert table_names.index("devices") < table_names.index("alerts")
    assert table_names.index("devices") < table_names.index("alert_policies")
    assert table_names.index("devices") < table_names.index("rdp_sessions")
    
    # users must come before telegram_subscribers
    assert table_names.index("users") < table_names.index("telegram_subscribers")

def test_transform_row_for_target_handles_json_and_datetime():
    table = Base.metadata.tables["devices"]
    raw_sqlite_row = {
        "id": "PC-TEST",
        "name": "Test PC",
        "hostname": "test-pc",
        "group_name": "Office",
        "ip_address": "192.168.1.50",
        "mac_address": "00:11:22:33:44:55",
        "tags": '["Office", "VIP"]',
        "boot_time": "2026-08-23 10:15:30.000000",
        "last_seen": "2026-08-23 11:00:00",
        "maintenance_mode": 1,
        "cpu_usage": 45,
        "power_status": "ON",
        "agent_status": "CONNECTED",
        "rdp_status": "STOPPED",
        "health_status": "HEALTHY",
    }
    
    transformed = transform_row_for_target(table, raw_sqlite_row)
    assert transformed["tags"] == ["Office", "VIP"]
    assert isinstance(transformed["boot_time"], datetime)
    assert isinstance(transformed["last_seen"], datetime)
    assert transformed["maintenance_mode"] is True
    assert transformed["cpu_usage"] == 45

def test_migration_pipeline_end_to_end(tmp_path):
    # 1. Create source SQLite DB with real models
    src_db_file = str(tmp_path / "source.db")
    src_engine = create_engine(f"sqlite:///{src_db_file}")
    Base.metadata.create_all(src_engine)
    
    with src_engine.begin() as conn:
        # Insert test user
        conn.execute(text("""
            INSERT INTO users (id, username, email, hashed_password, display_name, role, enabled, scope_values)
            VALUES ('USR-1', 'admin', 'admin@local', 'hash123', 'Administrator', 'Super Admin', 1, '[]')
        """))
        # Insert test device
        conn.execute(text("""
            INSERT INTO devices (id, name, hostname, group_name, ip_address, mac_address, tags, maintenance_mode)
            VALUES ('PC-001', 'PC Alpha', 'pc-alpha', 'Engineering', '192.168.1.10', 'AA:BB:CC:DD:EE:01', '["Workstation"]', 0)
        """))
        # Insert test hardware spec
        conn.execute(text("""
            INSERT INTO hardware_specs (id, device_id, raw_spec)
            VALUES (1, 'PC-001', '{"cpu": "Core i7", "ram_gb": 32}')
        """))

    # 2. Create target DB (using SQLite in memory to test schema, extraction, transform, load, and validation)
    dst_db_file = str(tmp_path / "dest.db")
    dst_engine = create_engine(f"sqlite:///{dst_db_file}")
    Base.metadata.create_all(dst_engine)

    # 3. Run migration
    summary = migrate_data(src_engine, dst_engine, truncate=True)
    
    # 4. Verify results
    assert summary["users"]["src"] == 1
    assert summary["users"]["dst"] == 1
    assert summary["devices"]["src"] == 1
    assert summary["devices"]["dst"] == 1
    assert summary["hardware_specs"]["src"] == 1
    assert summary["hardware_specs"]["dst"] == 1
    
    # Check that destination data matches
    with dst_engine.begin() as conn:
        res = conn.execute(text("SELECT name, hostname, tags FROM devices WHERE id='PC-001'")).fetchone()
        assert res[0] == "PC Alpha"
        assert res[1] == "pc-alpha"
        assert "Workstation" in str(res[2])

def test_normalize_postgres_url():
    from scripts.migrate_sqlite_to_postgres import normalize_postgres_url
    assert normalize_postgres_url("postgresql+asyncpg://u:p@localhost:5432/db") == "postgresql+psycopg2://u:p@localhost:5432/db"
    assert normalize_postgres_url("postgres://u:p@localhost:5432/db") == "postgresql+psycopg2://u:p@localhost:5432/db"
    assert normalize_postgres_url("postgresql://u:p@localhost:5432/db") == "postgresql+psycopg2://u:p@localhost:5432/db"

def test_find_sqlite_db_candidates():
    candidates = find_sqlite_db_candidates()
    assert isinstance(candidates, list)
    # At least workstation_manager.db exists in the repository
    assert len(candidates) > 0
    assert any("workstation_manager.db" in c for c in candidates)

def test_dry_run_flag(tmp_path):
    src_db_file = str(tmp_path / "src.db")
    src_engine = create_engine(f"sqlite:///{src_db_file}")
    Base.metadata.create_all(src_engine)
    with src_engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO users (id, username, email, hashed_password, display_name, role, enabled, scope_values)
            VALUES ('USR-DRY', 'dry_user', 'dry@local', 'hash', 'Dry Run', 'Operator', 1, '[]')
        """))
    
    dst_db_file = str(tmp_path / "dst.db")
    dst_engine = create_engine(f"sqlite:///{dst_db_file}")
    Base.metadata.create_all(dst_engine)

    summary = migrate_data(src_engine, dst_engine, dry_run=True)
    assert summary["users"]["src"] == 1
    # Because it was a dry run, dst table in real DB must still be empty (0 rows)
    with dst_engine.connect() as conn:
        actual_cnt = conn.execute(text("SELECT count(*) FROM users")).scalar()
        assert actual_cnt == 0


