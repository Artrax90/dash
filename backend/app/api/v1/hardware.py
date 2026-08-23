from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.app.db.session import get_db
from backend.app.models.hardware import HardwareSpecModel, HardwareBaselineModel, HardwareChangeModel
from backend.app.ws.manager import ws_manager

router = APIRouter(prefix="/hardware", tags=["hardware"])

hardware_changes_db: List[Dict[str, Any]] = []

@router.get("/changes")
async def get_changes(device_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    query = select(HardwareChangeModel).order_by(desc(HardwareChangeModel.timestamp))
    if device_id:
        query = query.where(HardwareChangeModel.device_id == device_id)
    result = await db.execute(query)
    changes = result.scalars().all()
    
    db_items = [
        {
            "id": c.id,
            "deviceId": c.device_id,
            "timestamp": c.timestamp.strftime("%Y-%m-%d %H:%M:%S") if c.timestamp else "",
            "component": c.component,
            "changeType": c.change_type,
            "severity": c.severity,
            "previousValue": c.previous_value,
            "currentValue": c.current_value,
            "acknowledged": c.acknowledged,
            "diffStatus": c.diff_status
        }
        for c in changes
    ]
    if db_items:
        return db_items
    if device_id:
        return [c for c in hardware_changes_db if c.get("deviceId") == device_id]
    return hardware_changes_db

@router.post("/baseline/{device_id}")
async def set_baseline(device_id: str, payload: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    approved_by = payload.get("approvedBy", "Administrator")
    spec = payload.get("spec")
    
    if not spec:
        hw_res = await db.execute(select(HardwareSpecModel).where(HardwareSpecModel.device_id == device_id))
        hw_model = hw_res.scalar_one_or_none()
        if hw_model:
            spec = hw_model.raw_spec

    if not spec:
        raise HTTPException(status_code=400, detail="No hardware spec available to approve as baseline")

    bl_res = await db.execute(select(HardwareBaselineModel).where(HardwareBaselineModel.device_id == device_id))
    baseline = bl_res.scalar_one_or_none()
    
    if not baseline:
        baseline = HardwareBaselineModel(
            id=f"BL-{device_id}",
            device_id=device_id,
            approved_by=approved_by,
            spec=spec
        )
        db.add(baseline)
    else:
        baseline.spec = spec
        baseline.approved_by = approved_by
        baseline.updated_at = datetime.utcnow()

    # Mark existing mismatch changes as ACCEPTED_AS_BASELINE
    ch_res = await db.execute(select(HardwareChangeModel).where(HardwareChangeModel.device_id == device_id, HardwareChangeModel.diff_status == "MISMATCH"))
    for ch in ch_res.scalars().all():
        ch.diff_status = "ACCEPTED_AS_BASELINE"
        ch.acknowledged = True

    await db.commit()
    await ws_manager.broadcast_event("baseline.updated", {"deviceId": device_id, "approvedBy": approved_by})

    return {
        "status": "success",
        "deviceId": device_id,
        "approvedBy": approved_by,
        "updatedAt": datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    }
