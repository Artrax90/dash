from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List, Optional
import json
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, delete

from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.models.alert import AlertModel
from backend.app.models.device import Device
from backend.app.models.hardware import HardwareChangeModel
from backend.app.ws.manager import ws_manager

router = APIRouter(prefix="/alerts", tags=["alerts"])

ALERTS_FILE = os.path.join(settings.DATA_DIR, "alerts.json")

def load_alerts_from_file() -> List[Dict[str, Any]]:
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            print(f"Error loading alerts file: {e}")
    return []

def save_alerts_to_file(alerts: List[Dict[str, Any]]):
    try:
        os.makedirs(settings.DATA_DIR, exist_ok=True)
        tmp_file = ALERTS_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(alerts[:500], f, ensure_ascii=False, indent=2)
        if os.path.exists(ALERTS_FILE):
            os.replace(tmp_file, ALERTS_FILE)
        else:
            os.rename(tmp_file, ALERTS_FILE)
    except Exception as e:
        print(f"Error saving alerts file: {e}")

alerts_db: List[Dict[str, Any]] = load_alerts_from_file()

@router.get("")
async def list_alerts(db: AsyncSession = Depends(get_db)):
    # 1. Map all devices to display friendly name / hostname
    dev_res = await db.execute(select(Device))
    dev_map = {d.id: (d.name or d.hostname or d.id) for d in dev_res.scalars().all()}

    # 2. Fetch from SQLite Database
    res = await db.execute(select(AlertModel).order_by(desc(AlertModel.created_at)).limit(200))
    models = res.scalars().all()
    
    db_alerts = []
    for m in models:
        dev_name = dev_map.get(m.device_id, m.device_id)
        c_time = m.created_at.strftime("%Y-%m-%d %H:%M:%S") if m.created_at else ""
        db_alerts.append({
            "id": m.id,
            "deviceId": m.device_id,
            "device": dev_name,
            "deviceName": dev_name,
            "type": m.alert_type,
            "alertType": m.alert_type,
            "category": m.category or "General",
            "severity": m.severity or "Warning",
            "state": m.state or "Open",
            "createdAt": c_time,
            "time": c_time,
            "timestamp": c_time,
            "description": m.description
        })
    
    seen_ids = set()
    combined_alerts = []
    for a in db_alerts:
        if a["id"] not in seen_ids:
            seen_ids.add(a["id"])
            combined_alerts.append(a)
            
    for a in alerts_db:
        aid = a.get("id")
        if aid and aid not in seen_ids:
            seen_ids.add(aid)
            if not a.get("device") or a.get("device") == a.get("deviceId"):
                a["device"] = dev_map.get(a.get("deviceId", ""), a.get("deviceId", "ПК"))
            combined_alerts.append(a)
            
    return combined_alerts

@router.post("/{alert_id}/resolve")
async def resolve_alert(alert_id: str, db: AsyncSession = Depends(get_db)):
    resolved_obj = None
    
    # 1. Try resolving in DB
    res = await db.execute(select(AlertModel).where(AlertModel.id == alert_id))
    model = res.scalar_one_or_none()
    if model:
        model.state = "Resolved"
        # Also mark matching hardware change as acknowledged
        if model.alert_type == "HARDWARE_MISMATCH" and model.device_id:
            hw_res = await db.execute(
                select(HardwareChangeModel).where(
                    HardwareChangeModel.device_id == model.device_id,
                    HardwareChangeModel.diff_status == "MISMATCH"
                )
            )
            for ch in hw_res.scalars().all():
                ch.acknowledged = True
                ch.diff_status = "RESOLVED"
        await db.commit()
        resolved_obj = {
            "id": model.id,
            "deviceId": model.device_id,
            "state": "Resolved"
        }

    # 2. Try resolving in JSON store
    for a in alerts_db:
        if a["id"] == alert_id:
            a["state"] = "Resolved"
            save_alerts_to_file(alerts_db)
            if not resolved_obj:
                resolved_obj = a
            break

    if resolved_obj:
        await ws_manager.broadcast_event("alert.resolved", resolved_obj)
        await ws_manager.broadcast_event("alert.updated", resolved_obj)
        return {"status": "resolved", "id": alert_id}
            
    return {"status": "not_found"}

@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, db: AsyncSession = Depends(get_db)):
    ack_obj = None
    
    # 1. Try acknowledging in DB
    res = await db.execute(select(AlertModel).where(AlertModel.id == alert_id))
    model = res.scalar_one_or_none()
    if model:
        model.state = "Acknowledged"
        if model.alert_type == "HARDWARE_MISMATCH" and model.device_id:
            hw_res = await db.execute(
                select(HardwareChangeModel).where(
                    HardwareChangeModel.device_id == model.device_id,
                    HardwareChangeModel.diff_status == "MISMATCH"
                )
            )
            for ch in hw_res.scalars().all():
                ch.acknowledged = True
        await db.commit()
        ack_obj = {"id": model.id, "deviceId": model.device_id, "state": "Acknowledged"}

    # 2. JSON store
    for a in alerts_db:
        if a["id"] == alert_id:
            a["state"] = "Acknowledged"
            save_alerts_to_file(alerts_db)
            if not ack_obj:
                ack_obj = a
            break

    if ack_obj:
        await ws_manager.broadcast_event("alert.updated", ack_obj)
        return {"status": "acknowledged", "id": alert_id}

    return {"status": "not_found"}

@router.post("/resolve-all")
@router.post("/ack-all")
async def resolve_all_alerts(db: AsyncSession = Depends(get_db)):
    # 1. Resolve all in DB
    res = await db.execute(select(AlertModel).where(AlertModel.state != "Resolved"))
    models = res.scalars().all()
    for m in models:
        m.state = "Resolved"
    
    hw_res = await db.execute(select(HardwareChangeModel).where(HardwareChangeModel.diff_status == "MISMATCH"))
    for ch in hw_res.scalars().all():
        ch.acknowledged = True
        ch.diff_status = "RESOLVED"
        
    await db.commit()

    # 2. Resolve in JSON store
    for a in alerts_db:
        a["state"] = "Resolved"
    save_alerts_to_file(alerts_db)

    await ws_manager.broadcast_event("alert.resolved_all", {"status": "all_resolved"})
    return {"status": "all_resolved", "count": len(models)}

@router.delete("/{alert_id}")
async def delete_alert(alert_id: str, db: AsyncSession = Depends(get_db)):
    await db.execute(delete(AlertModel).where(AlertModel.id == alert_id))
    await db.commit()

    global alerts_db
    alerts_db = [a for a in alerts_db if a.get("id") != alert_id]
    save_alerts_to_file(alerts_db)

    await ws_manager.broadcast_event("alert.deleted", {"id": alert_id})
    return {"status": "deleted", "id": alert_id}
