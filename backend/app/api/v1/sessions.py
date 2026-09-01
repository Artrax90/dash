from fastapi import APIRouter, Depends
from pydantic import BaseModel
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
    sessions_list: Any,
    hostname: Optional[str] = None,
    reported_device_id: Optional[str] = None,
    ip_address: Optional[str] = None
):
    if not device_id:
        print(f"[SESSIONS] update_device_sessions called with EMPTY device_id, skipping")
        return

    if isinstance(sessions_list, dict):
        sessions_list = [sessions_list]
    elif not isinstance(sessions_list, list):
        sessions_list = []

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

    print(f"[SESSIONS] update_device_sessions: device_id={device_id}, sessions_count={len(norm_list)}, keys={list(keys_to_index)}, total_keys_in_memory={len(live_device_sessions)}")

@router.get("/debug")
async def debug_sessions():
    """Debug endpoint to inspect live_device_sessions in-memory state"""
    result = {}
    unique_lists = set()
    for k, v in live_device_sessions.items():
        list_id = id(v)
        if list_id not in unique_lists:
            unique_lists.add(list_id)
            result[k] = {
                "count": len(v),
                "sessions": v[:3]  # first 3 for brevity
            }
        else:
            result[k] = {"count": len(v), "alias_of": "same_list"}
    return {
        "total_keys": len(live_device_sessions),
        "unique_session_lists": len(unique_lists),
        "data": result
    }

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

class LogoffRequest(BaseModel):
    deviceId: Optional[str] = None
    device_id: Optional[str] = None
    pid: Optional[int] = None
    type: Optional[str] = None
    isOutgoing: Optional[bool] = None

@router.post("/{session_id}/logoff")
async def logoff_session(
    session_id: int,
    device_id: Optional[str] = None,
    deviceId: Optional[str] = None,
    req: Optional[LogoffRequest] = None,
    db: AsyncSession = Depends(get_db)
):
    from backend.app.api.v1.agents import queue_device_command
    target_dev_id = (req.deviceId if req and req.deviceId else None) or (req.device_id if req and req.device_id else None) or device_id or deviceId
    target_pid = req.pid if req else None
    target_type = req.type if req else None

    # If target device ID is explicitly provided
    if target_dev_id:
        target_dev_id_clean = target_dev_id.strip()
        is_outgoing_rdp = (target_type and "Исходящий" in target_type) or (session_id >= 100)
        action = "CLOSE_RDP_CLIENT" if is_outgoing_rdp else "LOGOFF"
        queue_device_command(
            device_id=target_dev_id_clean,
            action=action,
            reason=f"Admin requested {action} for session #{session_id}",
            extra_data={"sessionId": session_id, "pid": target_pid, "type": target_type}
        )
        return {"status": "success", "message": f"{action} queued for session #{session_id} on {target_dev_id_clean}"}

    # Fallback: search session in live memory
    for dev_id, sess_list in list(live_device_sessions.items()):
        if isinstance(sess_list, list):
            for s in sess_list:
                if str(s.get("id")) == str(session_id):
                    s_pid = s.get("pid")
                    s_type = s.get("type", "")
                    action = "CLOSE_RDP_CLIENT" if "Исходящий" in s_type or session_id >= 100 else "LOGOFF"
                    queue_device_command(
                        device_id=dev_id,
                        action=action,
                        reason=f"Admin requested {action} for session #{session_id} ({s.get('username')})",
                        extra_data={"sessionId": session_id, "pid": s_pid, "type": s_type, "username": s.get("username")}
                    )
                    return {"status": "success", "message": f"{action} command queued for session #{session_id} on {dev_id}"}

    return {"status": "success", "message": f"Logoff command dispatched for session {session_id}"}


