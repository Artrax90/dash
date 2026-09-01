from fastapi import APIRouter, Depends
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from backend.app.db.session import get_db
from backend.app.models.device import Device, PowerStatus
from datetime import datetime

router = APIRouter(prefix="/sessions", tags=["sessions"])

live_device_sessions: Dict[str, List[Dict[str, Any]]] = {}

def update_device_sessions(
    device_id: str,
    sessions_list: List[Dict[str, Any]],
    hostname: Optional[str] = None,
    reported_device_id: Optional[str] = None,
    ip_address: Optional[str] = None
):
    if not device_id:
        return
    norm_list = []
    for s in sessions_list:
        if isinstance(s, dict):
            s_dict = dict(s)
            s_dict["deviceId"] = device_id
            norm_list.append(s_dict)

    keys_to_index = {device_id, device_id.upper(), device_id.lower()}
    if hostname:
        keys_to_index.update({hostname, hostname.upper(), hostname.lower()})
    if reported_device_id:
        keys_to_index.update({reported_device_id, reported_device_id.upper(), reported_device_id.lower()})
    if ip_address:
        keys_to_index.add(ip_address)

    for k in keys_to_index:
        live_device_sessions[k] = norm_list

@router.get("")
async def list_sessions(
    device_id: Optional[str] = None,
    deviceId: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    req_dev_id = (device_id or deviceId or "").strip()
    
    # 1. Direct fast-path lookup if specific deviceId requested
    if req_dev_id:
        for k in [req_dev_id, req_dev_id.upper(), req_dev_id.lower()]:
            if k in live_device_sessions and live_device_sessions[k]:
                return live_device_sessions[k]

        # Check in DB if not found in memory directly
        res = await db.execute(select(Device))
        devices = res.scalars().all()
        did_clean = req_dev_id.lower()
        for d in devices:
            if (
                d.id.lower() == did_clean or
                (d.hostname and d.hostname.lower() == did_clean) or
                (d.ip_address and d.ip_address.lower() == did_clean) or
                (d.name and d.name.lower() == did_clean)
            ):
                reported = (
                    live_device_sessions.get(d.id) or
                    live_device_sessions.get(d.id.upper()) or
                    live_device_sessions.get(d.id.lower()) or
                    (live_device_sessions.get(d.hostname) if d.hostname else None) or
                    (live_device_sessions.get(d.hostname.upper()) if d.hostname else None) or
                    (live_device_sessions.get(d.hostname.lower()) if d.hostname else None) or
                    (live_device_sessions.get(d.ip_address) if d.ip_address else None) or
                    []
                )
                return reported
        return []

    # 2. Global query: return all unique live sessions
    seen = set()
    all_sessions = []
    for k, sess_list in live_device_sessions.items():
        if isinstance(sess_list, list):
            for s in sess_list:
                s_key = (str(s.get("deviceId")), str(s.get("id")), str(s.get("username")), str(s.get("sessionName")))
                if s_key not in seen:
                    seen.add(s_key)
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
