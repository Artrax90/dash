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

backup_service = BackupService()
