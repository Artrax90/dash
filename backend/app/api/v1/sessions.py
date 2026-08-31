from fastapi import APIRouter, Depends
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from backend.app.db.session import get_db
from backend.app.models.device import Device, PowerStatus
from datetime import datetime

router = APIRouter(prefix="/sessions", tags=["sessions"])

live_device_sessions: Dict[str, List[Dict[str, Any]]] = {}

def update_device_sessions(device_id: str, sessions_list: List[Dict[str, Any]]):
    if not device_id:
        return
    norm_list = []
    for s in sessions_list:
        if isinstance(s, dict):
            s_dict = dict(s)
            s_dict["deviceId"] = device_id
            norm_list.append(s_dict)
    live_device_sessions[device_id] = norm_list
    live_device_sessions[device_id.upper()] = norm_list

@router.get("")
async def list_sessions(device_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Device))
    devices = res.scalars().all()
    now = datetime.utcnow()

    all_sessions = []
    for d in devices:
        if device_id and (d.id.upper() != device_id.upper() and (d.hostname or "").lower() != device_id.lower()):
            continue
        
        # Check if device is online
        is_online = (d.power_status == PowerStatus.ON) and (d.last_seen and (now - d.last_seen).total_seconds() <= 180)
        if not is_online:
            continue

        reported = live_device_sessions.get(d.id) or live_device_sessions.get(d.id.upper(), [])
        if reported:
            for s in reported:
                all_sessions.append(s)

    return all_sessions

@router.post("/{session_id}/logoff")
async def logoff_session(session_id: int, db: AsyncSession = Depends(get_db)):
    from backend.app.api.v1.agents import queue_device_command
    for dev_id, sess_list in list(live_device_sessions.items()):
        for s in sess_list:
            if str(s.get("id")) == str(session_id):
                queue_device_command(
                    device_id=dev_id,
                    action="LOGOFF",
                    reason=f"Admin requested logoff for session #{session_id} ({s.get('username')})",
                    extra_data={"sessionId": session_id, "username": s.get("username")}
                )
                return {"status": "success", "message": f"Logoff command queued for session {session_id} on {dev_id}"}
    return {"status": "success", "message": f"Logoff command dispatched for session {session_id}"}
