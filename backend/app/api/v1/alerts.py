from fastapi import APIRouter, Depends
from typing import Dict, Any, List
import json
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.models.alert import AlertModel

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
    # 1. Fetch from SQLite Database
    res = await db.execute(select(AlertModel).order_by(desc(AlertModel.created_at)).limit(200))
    models = res.scalars().all()
    
    db_alerts = []
    for m in models:
        db_alerts.append({
            "id": m.id,
            "deviceId": m.device_id,
            "alertType": m.alert_type,
            "category": m.category or "General",
            "severity": m.severity or "Warning",
            "state": m.state or "Open",
            "createdAt": m.created_at.strftime("%Y-%m-%d %H:%M:%S") if m.created_at else "",
            "description": m.description
        })
    
    if db_alerts:
        return db_alerts
        
    return alerts_db

@router.post("/{alert_id}/resolve")
async def resolve_alert(alert_id: str, db: AsyncSession = Depends(get_db)):
    # 1. Try resolving in DB
    res = await db.execute(select(AlertModel).where(AlertModel.id == alert_id))
    model = res.scalar_one_or_none()
    if model:
        model.state = "Resolved"
        await db.commit()
        return {"status": "resolved", "id": alert_id}

    # 2. Try resolving in in-memory / JSON store
    for a in alerts_db:
        if a["id"] == alert_id:
            a["state"] = "Resolved"
            save_alerts_to_file(alerts_db)
            return {"status": "resolved", "id": alert_id}
            
    return {"status": "not_found"}
