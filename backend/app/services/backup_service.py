import os
import json
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import text, select, delete
from backend.app.core.config import settings
from backend.app.db.session import AsyncSessionLocal, Base, is_postgres_url, engine
from backend.app.models import (
    Device, HardwareSpecModel, HardwareBaselineModel, HardwareChangeModel,
    AlertModel, AlertPolicyModel, RdpSessionModel, ScheduleModel,
    OperationModel, AgentEnrollmentTokenModel, UserModel, CustomRoleModel,
    AuditLogModel, TelegramSubscriberModel
)

class BackupService:
    @staticmethod
    def _serialize_val(val: Any) -> Any:
        if val is None:
            return None
        if isinstance(val, (datetime,)):
            return val.isoformat()
        if hasattr(val, "value"):
            return val.value
        if isinstance(val, (dict, list, int, float, str, bool)):
            return val
        return str(val)

    async def create_backup(self) -> Dict[str, Any]:
        """
        Dumps all database tables and configuration files into a structured JSON backup.
        """
        tables_dump: Dict[str, List[Dict[str, Any]]] = {}
        is_pg = is_postgres_url(str(engine.url))

        async with AsyncSessionLocal() as session:
            for table in Base.metadata.sorted_tables:
                t_name = table.name
                try:
                    res = await session.execute(select(table))
                    rows = res.mappings().all()
                    table_rows = []
                    for r in rows:
                        row_dict = {col: self._serialize_val(val) for col, val in r.items()}
                        table_rows.append(row_dict)
                    tables_dump[t_name] = table_rows
                except Exception as ex:
                    print(f"[Backup] Warning reading table {t_name}: {ex}")
                    tables_dump[t_name] = []

        # Load filesystem configs if present
        configs_dump: Dict[str, Any] = {}
        for cfg_name in ["users.json", "roles.json", "telegram_config.json", "groups.json", "active_sessions.json"]:
            p = os.path.join(settings.DATA_DIR, cfg_name)
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        configs_dump[cfg_name] = json.load(f)
                except Exception:
                    pass

        device_cnt = len(tables_dump.get("devices", []))
        now_iso = datetime.now(timezone.utc).isoformat()
        content_str = json.dumps(tables_dump, sort_keys=True)
        checksum = hashlib.sha256(content_str.encode("utf-8")).hexdigest()

        return {
            "status": "success",
            "backupDate": now_iso,
            "exportedAt": now_iso,
            "version": settings.VERSION,
            "backupVersion": "2.0.0",
            "databaseType": "postgresql" if is_pg else "sqlite",
            "deviceCount": device_cnt,
            "tableCount": len(tables_dump),
            "checksum": checksum,
            "tables": tables_dump,
            "configs": configs_dump
        }

    async def restore_backup(self, backup_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Restores database tables and configs from an uploaded backup object.
        """
        if not isinstance(backup_data, dict):
            raise ValueError("Invalid backup payload format")

        tables_data = backup_data.get("tables", {})
        if not tables_data and "devices" not in tables_data:
            raise ValueError("No valid database table data found in backup")

        restored_counts: Dict[str, int] = {}

        async with AsyncSessionLocal() as session:
            async with session.begin():
                for table in Base.metadata.sorted_tables:
                    t_name = table.name
                    if t_name not in tables_data:
                        continue
                    rows = tables_data[t_name]
                    if not isinstance(rows, list):
                        continue

                    for r in rows:
                        if not isinstance(r, dict):
                            continue
                        clean_row = {}
                        for col in table.columns:
                            c_name = col.name
                            if c_name in r and r[c_name] is not None:
                                val = r[c_name]
                                if "datetime" in str(col.type).lower() or "timestamp" in str(col.type).lower():
                                    if isinstance(val, str):
                                        try:
                                            val = datetime.fromisoformat(val.replace("Z", "+00:00"))
                                        except Exception:
                                            pass
                                clean_row[c_name] = val

                        try:
                            stmt = table.insert().values(**clean_row)
                            await session.execute(stmt)
                        except Exception:
                            pk_cols = [c.name for c in table.primary_key.columns]
                            if pk_cols and pk_cols[0] in clean_row:
                                pk_val = clean_row[pk_cols[0]]
                                upd_stmt = (
                                    table.update()
                                    .where(getattr(table.c, pk_cols[0]) == pk_val)
                                    .values(**{k: v for k, v in clean_row.items() if k != pk_cols[0]})
                                )
                                await session.execute(upd_stmt)

                    restored_counts[t_name] = len(rows)

        configs = backup_data.get("configs", {})
        if isinstance(configs, dict):
            for cfg_name, cfg_val in configs.items():
                if cfg_name in ["users.json", "roles.json", "telegram_config.json", "groups.json", "active_sessions.json"]:
                    p = os.path.join(settings.DATA_DIR, cfg_name)
                    try:
                        os.makedirs(os.path.dirname(p), exist_ok=True)
                        with open(p, "w", encoding="utf-8") as f:
                            json.dump(cfg_val, f, indent=2, ensure_ascii=False)
                    except Exception:
                        pass

        try:
            from backend.app.ws.manager import ws_manager
            await ws_manager.broadcast_event("system.restored", {
                "restoredAt": datetime.now(timezone.utc).isoformat(),
                "deviceCount": restored_counts.get("devices", 0)
            })
        except Exception:
            pass

        return {
            "status": "success",
            "message": "База данных и конфигурация успешно восстановлены из резервной копии",
            "restoredTables": restored_counts,
            "deviceCount": restored_counts.get("devices", 0)
        }

    async def cleanup_old_records(self, days: int = 30) -> Dict[str, Any]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        deleted_alerts = 0
        deleted_audit = 0

        async with AsyncSessionLocal() as session:
            async with session.begin():
                try:
                    res_alt = await session.execute(
                        delete(AlertModel).where(
                            (AlertModel.state == "Resolved") &
                            (AlertModel.created_at < cutoff)
                        )
                    )
                    deleted_alerts = res_alt.rowcount or 0
                except Exception:
                    pass

                try:
                    res_aud = await session.execute(
                        delete(AuditLogModel).where(AuditLogModel.timestamp < cutoff)
                    )
                    deleted_audit = res_aud.rowcount or 0
                except Exception:
                    pass

        return {
            "status": "success",
            "retentionDays": days,
            "deletedAlerts": deleted_alerts,
            "deletedAuditLogs": deleted_audit,
            "message": f"Очистка завершена: удалено {deleted_alerts} устаревших алертов и {deleted_audit} записей аудита (старше {days} дн.)"
        }

    async def reset_database(self, keep_current_user: bool = True, current_user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Completely resets all database tables and clears fleet devices, groups, telemetry, and logs.
        """
        # 1. Truncate / delete all rows in all database tables in reverse dependency order
        async with AsyncSessionLocal() as session:
            async with session.begin():
                for table in reversed(Base.metadata.sorted_tables):
                    try:
                        await session.execute(table.delete())
                    except Exception as ex:
                        print(f"[Reset] Warning clearing table {table.name}: {ex}")

        # 2. Reset filesystem configuration files and caches in DATA_DIR
        os.makedirs(settings.DATA_DIR, exist_ok=True)
        files_to_empty_dict = ["device_processes.json", "device_configs.json"]
        for fname in files_to_empty_dict:
            p = os.path.join(settings.DATA_DIR, fname)
            try:
                with open(p, "w", encoding="utf-8") as f:
                    json.dump({}, f, indent=2, ensure_ascii=False)
            except Exception:
                pass

        files_to_empty_list = [
            "power_logs.json", "alerts.json", "audit_logs.json",
            "groups.json", "groups.backup.json",
            "buildings.json", "buildings.backup.json",
            "schedules.json", "schedules.backup.json",
            "tokens.json", "tokens.backup.json"
        ]
        for fname in files_to_empty_list:
            p = os.path.join(settings.DATA_DIR, fname)
            try:
                with open(p, "w", encoding="utf-8") as f:
                    json.dump([], f, indent=2, ensure_ascii=False)
            except Exception:
                pass

        for extra_file in ["devices.json", "devices_cache.json"]:
            p = os.path.join(settings.DATA_DIR, extra_file)
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

        users_file = os.path.join(settings.DATA_DIR, "users.json")
        backup_users_file = os.path.join(settings.DATA_DIR, "users.backup.json")
        sessions_file = os.path.join(settings.DATA_DIR, "active_sessions.json")

        if keep_current_user:
            preserved_users = []
            try:
                if os.path.exists(users_file):
                    with open(users_file, "r", encoding="utf-8") as f:
                        all_users = json.load(f)
                        if isinstance(all_users, list):
                            if current_user_id:
                                clean_cid = str(current_user_id).strip().lower()
                                target_u = next((u for u in all_users if str(u.get("id", "")).lower() == clean_cid or str(u.get("username", "")).lower() == clean_cid), None)
                                if target_u:
                                    preserved_users.append(target_u)
                            if not preserved_users:
                                admin_u = next((u for u in all_users if "суперадминистратор" in str(u.get("role", "")).lower() or "admin" in str(u.get("role", "")).lower()), None)
                                if admin_u:
                                    preserved_users.append(admin_u)
                                elif all_users:
                                    preserved_users.append(all_users[0])
            except Exception:
                pass

            if preserved_users:
                try:
                    with open(users_file, "w", encoding="utf-8") as f:
                        json.dump(preserved_users, f, indent=2, ensure_ascii=False)
                    with open(backup_users_file, "w", encoding="utf-8") as f:
                        json.dump(preserved_users, f, indent=2, ensure_ascii=False)
                except Exception:
                    pass
        else:
            try:
                with open(users_file, "w", encoding="utf-8") as f:
                    json.dump([], f, indent=2, ensure_ascii=False)
                with open(backup_users_file, "w", encoding="utf-8") as f:
                    json.dump([], f, indent=2, ensure_ascii=False)
                with open(sessions_file, "w", encoding="utf-8") as f:
                    json.dump({}, f, indent=2, ensure_ascii=False)
            except Exception:
                pass

        # 3. Clear in-memory caches
        try:
            from backend.app.api.v1.devices import device_live_processes, device_power_logs, device_drives_cache
            device_live_processes.clear()
            device_power_logs.clear()
            device_drives_cache.clear()
        except Exception:
            pass

        try:
            from backend.app.api.v1.telegram import update_cached_devices
            update_cached_devices([])
        except Exception:
            pass

        try:
            from backend.app.api.v1.agents import fleet_arp_cache, fleet_mac_to_ip
            fleet_arp_cache.clear()
            fleet_mac_to_ip.clear()
        except Exception:
            pass

        # 4. Broadcast WebSocket event
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            from backend.app.ws.manager import ws_manager
            await ws_manager.broadcast_event("system.database_reset", {
                "resetAt": now_iso,
                "usersPreserved": keep_current_user
            })
        except Exception:
            pass

        return {
            "status": "success",
            "message": "База данных полностью обнулена. Все устройства, группы, инциденты и журналы удалены.",
            "resetAt": now_iso,
            "usersPreserved": keep_current_user
        }

backup_service = BackupService()
