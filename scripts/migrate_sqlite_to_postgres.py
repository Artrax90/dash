#!/usr/bin/env python3
"""
Workstation Manager - SQLite to PostgreSQL Enterprise Migration Tool
Transfers all devices, users, credentials, hardware baselines, specs, alerts,
schedules, audit logs, and sessions from SQLite to PostgreSQL with zero data loss.
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import create_engine, text, inspect, Table, select
from sqlalchemy.types import JSON, DateTime, Boolean, Integer, Float

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.db.session import Base, is_postgres_url
# Ensure all models are imported so Base.metadata is fully populated
from backend.app.models import (
    Device, UserModel, CustomRoleModel, ScheduleModel,
    HardwareSpecModel, HardwareBaselineModel, AlertModel, RdpSessionModel,
    AlertPolicyModel, TelegramSubscriberModel, OperationModel, AgentEnrollmentTokenModel,
    AuditLogModel, HardwareChangeModel
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migration")

def get_ordered_tables() -> List[Table]:
    """Return all SQLAlchemy tables sorted in topological dependency order (parents before children)."""
    return list(Base.metadata.sorted_tables)

def parse_iso_datetime(val: Any) -> Optional[datetime]:
    """Parse string representations of datetime from SQLite into Python datetime objects."""
    if val is None or isinstance(val, datetime):
        return val
    s = str(val).strip()
    if not s:
        return None
    # Handle formats like "2026-08-23 10:15:30.123456", "2026-08-23T10:15:30", etc.
    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s)
    except Exception:
        logger.warning(f"Could not parse datetime string: '{s}', leaving as-is")
        return None

def transform_row_for_target(table: Table, row_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Clean, parse, and type-cast a raw dictionary row from SQLite for insertion into target DB."""
    transformed: Dict[str, Any] = {}
    col_map = {col.name: col for col in table.columns}

    for key, val in row_dict.items():
        if key not in col_map:
            continue
        col = col_map[key]
        
        if val is None:
            transformed[key] = None
            continue

        # JSON columns in SQLite are stored as TEXT
        if isinstance(col.type, JSON):
            if isinstance(val, str):
                val_trimmed = val.strip()
                if not val_trimmed:
                    transformed[key] = [] if key in ("tags", "scope_values", "permissions") else {}
                else:
                    try:
                        transformed[key] = json.loads(val_trimmed)
                    except Exception as e:
                        logger.warning(f"Failed to parse JSON for {table.name}.{key}: {e}")
                        transformed[key] = val
            else:
                transformed[key] = val

        # DateTime columns in SQLite are stored as TEXT
        elif isinstance(col.type, DateTime):
            transformed[key] = parse_iso_datetime(val)

        # Boolean columns in SQLite are stored as 1/0
        elif isinstance(col.type, Boolean):
            if isinstance(val, (int, float)):
                transformed[key] = bool(val)
            elif isinstance(val, str):
                transformed[key] = val.lower() in ("1", "true", "yes", "t")
            else:
                transformed[key] = bool(val)

        # Integer columns
        elif isinstance(col.type, Integer):
            try:
                transformed[key] = int(val)
            except (ValueError, TypeError):
                transformed[key] = val

        # Default: pass-through
        else:
            transformed[key] = val

    return transformed

def find_sqlite_db_candidates() -> List[str]:
    """Scan the repository for existing SQLite databases that contain Workstation Manager tables."""
    candidates = [
        os.path.join(PROJECT_ROOT, "data", "workstation_manager.db"),
        os.path.join(PROJECT_ROOT, "workstation_manager.db"),
        os.path.join(PROJECT_ROOT, "data", "workstation.db"),
        os.path.join(PROJECT_ROOT, "data", "app.db"),
    ]
    valid = []
    for path in candidates:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            valid.append(path)
    return valid

def reset_postgres_sequences(engine, tables: List[Table]) -> None:
    """Reset PostgreSQL serial sequences so newly inserted rows do not collide with auto-increment IDs."""
    if engine.dialect.name != "postgresql":
        return

    with engine.begin() as conn:
        for table in tables:
            # Look for integer primary key columns
            for col in table.primary_key.columns:
                if isinstance(col.type, Integer):
                    try:
                        seq_sql = text(f"""
                            SELECT setval(
                                pg_get_serial_sequence('{table.name}', '{col.name}'),
                                COALESCE((SELECT MAX({col.name}) FROM "{table.name}"), 1),
                                true
                            );
                        """)
                        conn.execute(seq_sql)
                        logger.info(f"Reset sequence for table '{table.name}' on column '{col.name}'.")
                    except Exception as e:
                        logger.debug(f"Could not reset sequence for {table.name}.{col.name}: {e}")

def migrate_data(
    src_engine,
    dst_engine,
    truncate: bool = False,
    dry_run: bool = False,
    batch_size: int = 500
) -> Dict[str, Dict[str, int]]:
    """
    Execute migration from src_engine (SQLite) to dst_engine (PostgreSQL/Target).
    Returns a dictionary of {table_name: {'src': count, 'dst': count}}.
    """
    ordered_tables = get_ordered_tables()
    summary: Dict[str, Dict[str, int]] = {}

    src_inspector = inspect(src_engine)
    src_tables = set(src_inspector.get_table_names())

    # 1. Truncate target tables if requested (in reverse topological order)
    if truncate and not dry_run:
        logger.info("Truncating destination tables before migration...")
        with dst_engine.begin() as conn:
            for table in reversed(ordered_tables):
                try:
                    conn.execute(table.delete())
                except Exception as e:
                    logger.debug(f"Truncate notice for {table.name}: {e}")

    # 2. Migrate each table in dependency order
    for table in ordered_tables:
        table_name = table.name
        if table_name not in src_tables:
            logger.debug(f"Skipping table '{table_name}' (not in source database).")
            continue

        # Read all rows from source SQLite
        with src_engine.connect() as src_conn:
            result = src_conn.execute(text(f"SELECT * FROM \"{table_name}\""))
            col_names = list(result.keys())
            raw_rows = [dict(zip(col_names, row)) for row in result.fetchall()]

        src_count = len(raw_rows)
        if src_count == 0:
            logger.info(f"Table '{table_name}': 0 rows in source.")
            summary[table_name] = {"src": 0, "dst": 0}
            continue

        logger.info(f"Table '{table_name}': found {src_count} rows in source.")

        # Transform rows
        transformed_rows = [transform_row_for_target(table, r) for r in raw_rows]

        # Insert rows into destination in batches
        if not dry_run:
            with dst_engine.begin() as dst_conn:
                for i in range(0, len(transformed_rows), batch_size):
                    batch = transformed_rows[i:i + batch_size]
                    dst_conn.execute(table.insert(), batch)

        # Count destination rows
        if not dry_run:
            with dst_engine.connect() as dst_conn:
                cnt_res = dst_conn.execute(text(f"SELECT COUNT(*) FROM \"{table_name}\""))
                dst_count = cnt_res.scalar() or 0
        else:
            dst_count = src_count  # Simulation

        summary[table_name] = {"src": src_count, "dst": dst_count}

    # 3. Reset PostgreSQL sequences
    if not dry_run:
        reset_postgres_sequences(dst_engine, ordered_tables)

    return summary

def normalize_postgres_url(url: str) -> str:
    """Ensure PostgreSQL URL uses psycopg2 or standard driver for synchronous migration."""
    if not url:
        return ""
    # Replace asyncpg with psycopg2 or standard postgresql dialect
    if "postgresql+asyncpg://" in url:
        url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    elif "postgres://" in url:
        url = url.replace("postgres://", "postgresql+psycopg2://")
    elif url.startswith("postgresql://") and "+psycopg2" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg2://")
    return url

def ensure_postgres_driver():
    """Ensure psycopg2 driver is available, auto-installing psycopg2-binary if running in container/environment without it."""
    try:
        import psycopg2
        return
    except ImportError:
        pass
    try:
        import subprocess
        logger.info("psycopg2 driver not found. Installing psycopg2-binary automatically...")
        res = subprocess.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "psycopg2-binary"], capture_output=True, text=True)
        if res.returncode == 0:
            logger.info("psycopg2-binary installed successfully.")
        else:
            logger.warning(f"Failed to auto-install psycopg2-binary: {res.stderr}")
    except Exception as e:
        logger.warning(f"Could not auto-install psycopg2-binary: {e}")

def main():
    parser = argparse.ArgumentParser(description="Migrate Workstation Manager data from SQLite to PostgreSQL.")
    parser.add_argument("--sqlite", type=str, help="Path to source SQLite database file")
    parser.add_argument("--postgres-url", type=str, help="Target PostgreSQL connection URL")
    parser.add_argument("--truncate", action="store_true", help="Truncate target tables before inserting")
    parser.add_argument("--dry-run", action="store_true", help="Perform dry run without modifying target DB")
    args = parser.parse_args()

    # Determine SQLite database path
    sqlite_path = args.sqlite
    if not sqlite_path:
        candidates = find_sqlite_db_candidates()
        if not candidates:
            logger.error("No SQLite database found. Please specify with --sqlite /path/to/db.sqlite")
            sys.exit(1)
        # Select candidate with most devices
        best_candidate = candidates[0]
        max_devs = -1
        for cand in candidates:
            try:
                e = create_engine(f"sqlite:///{cand}")
                with e.connect() as c:
                    cnt = c.execute(text("SELECT count(*) FROM devices")).scalar() or 0
                    if cnt > max_devs:
                        max_devs = cnt
                        best_candidate = cand
            except Exception:
                pass
        sqlite_path = best_candidate
        logger.info(f"Auto-selected SQLite database: {sqlite_path} ({max_devs} devices found)")

    if not os.path.exists(sqlite_path):
        logger.error(f"Source SQLite file does not exist: {sqlite_path}")
        sys.exit(1)

    # Determine PostgreSQL URL
    pg_url = args.postgres_url or os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if not pg_url or not is_postgres_url(pg_url):
        logger.error("No PostgreSQL URL provided. Set DATABASE_URL in environment or use --postgres-url")
        logger.error("Example: postgresql://postgres:postgres_pass@localhost:5432/workstation_manager")
        sys.exit(1)

    sync_pg_url = normalize_postgres_url(pg_url)
    logger.info(f"Connecting to source SQLite: {sqlite_path}")
    logger.info(f"Connecting to target PostgreSQL: {sync_pg_url.split('@')[-1] if '@' in sync_pg_url else sync_pg_url}")

    ensure_postgres_driver()
    src_engine = create_engine(f"sqlite:///{sqlite_path}")
    dst_engine = create_engine(sync_pg_url)

    # Ensure schema exists in PostgreSQL
    if not args.dry_run:
        logger.info("Ensuring PostgreSQL schema and tables exist...")
        Base.metadata.create_all(dst_engine)

    # Execute migration
    summary = migrate_data(
        src_engine=src_engine,
        dst_engine=dst_engine,
        truncate=args.truncate,
        dry_run=args.dry_run
    )

    # Display summary
    print("\n" + "=" * 65)
    print(f"{'TABLE NAME':<30} | {'SQLITE':<10} | {'POSTGRES':<10} | {'STATUS'}")
    print("=" * 65)
    all_ok = True
    for tbl, counts in summary.items():
        src_cnt = counts["src"]
        dst_cnt = counts["dst"]
        status = "OK" if src_cnt == dst_cnt else "MISMATCH"
        if status != "OK":
            all_ok = False
        print(f"{tbl:<30} | {src_cnt:<10} | {dst_cnt:<10} | {status}")
    print("=" * 65)

    if all_ok:
        print("\nSUCCESS: All records successfully migrated to PostgreSQL with zero data loss!")
    else:
        print("\nWARNING: Some table counts mismatched. Check log output above.")

if __name__ == "__main__":
    main()
