from fastapi import APIRouter
from typing import Dict, Any, List

router = APIRouter(prefix="/alerts", tags=["alerts"])

alerts_db: List[Dict[str, Any]] = []

@router.get("")
async def list_alerts():
    return alerts_db

@router.post("/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    for a in alerts_db:
        if a["id"] == alert_id:
            a["state"] = "Resolved"
            return {"status": "resolved", "id": alert_id}
    return {"status": "not_found"}
