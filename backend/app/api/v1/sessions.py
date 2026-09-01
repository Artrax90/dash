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

def is_real_rdp_session(s: dict) -> bool:
    if not isinstance(s, dict):
        return False
    s_type = str(s.get("type") or "").strip()
    s_name = str(s.get("sessionName") or "").strip().lower()
    
    # Outgoing RDP (mstsc process)
    is_outgoing = "исходящий" in s_type.lower() or s_name.startswith("mstsc") or "mstsc" in s_name
    # Incoming RDP (rdp-tcp#... or clientIp present)
    is_incoming = "входящий" in s_type.lower() or "rdp" in s_name or s_name.startswith("rdp-tcp") or bool(s.get("clientIp") and s.get("clientIp") != "-")
    
    if is_outgoing or is_incoming:
        # Extra guard: exclude pure local console even if mislabeled
        if s_name in ["console", "services", "rdp-tcp", ""] and not is_outgoing and not s_name.startswith("rdp-tcp#"):
            if not s.get("clientIp") or s.get("clientIp") == "-":
                return False
        return True
        
    return False

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
            if is_real_rdp_session(s_dict):
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
    from backend.app.api.v1.agents import queue_device_command, send_direct_lan_power_signal
    from backend.app.ws.manager import ws_manager
    from backend.app.api.v1.devices import format_device_summary

    target_dev_id = (req.deviceId if req and req.deviceId else None) or (req.device_id if req and req.device_id else None) or device_id or deviceId
    target_pid = req.pid if req else None
    target_type = req.type if req else None

    # Find the target device
    device = None
    if target_dev_id:
        res = await db.execute(select(Device).where((Device.id == target_dev_id.strip()) | (Device.hostname == target_dev_id.strip())))
        device = res.scalar_one_or_none()

    resolved_dev_id = device.id if device else (target_dev_id.strip() if target_dev_id else None)

    # If target not found in DB directly, try live_device_sessions
    if not resolved_dev_id:
        for dev_id, sess_list in list(live_device_sessions.items()):
            if isinstance(sess_list, list):
                for s in sess_list:
                    if str(s.get("id")) == str(session_id):
                        resolved_dev_id = str(s.get("deviceId", dev_id))
                        if not target_pid and s.get("pid"):
                            target_pid = s.get("pid")
                        if not target_type and s.get("type"):
                            target_type = s.get("type")
                        break
            if resolved_dev_id:
                break

    if not resolved_dev_id:
        resolved_dev_id = "PC-DEFAULT"

    # Look up session info for remote target IP and username
    sess_username = None
    dest_ip = None
    for sess_list in live_device_sessions.values():
        if isinstance(sess_list, list):
            for s in sess_list:
                if str(s.get("id")) == str(session_id):
                    sess_username = s.get("username")
                    s_name = str(s.get("sessionName", ""))
                    if "->" in s_name:
                        dest_ip = s_name.split("->")[-1].strip().split(":")[0].strip()
                    elif s.get("clientIp"):
                        dest_ip = str(s.get("clientIp")).strip()
                    break
        if sess_username or dest_ip:
            break

    if req and req.isOutgoing is not None:
        is_outgoing_rdp = req.isOutgoing
    else:
        is_outgoing_rdp = (target_type and "Исходящий" in target_type) or (session_id >= 100)

    action = "CLOSE_RDP_CLIENT" if is_outgoing_rdp else "LOGOFF"
    extra_arg = str(target_pid) if is_outgoing_rdp and target_pid else str(session_id)

    # 1. Queue command for heartbeat fallback
    queue_device_command(
        device_id=resolved_dev_id,
        action=action,
        reason=f"Admin requested {action} for session #{session_id}",
        extra_data={"sessionId": session_id, "pid": target_pid, "type": target_type, "username": sess_username, "remoteHost": dest_ip}
    )

    # 2. Send instant UNICAST UDP trigger to device LAN agent (0ms latency)
    if device and device.ip_address:
        send_direct_lan_power_signal(
            ip_address=device.ip_address,
            action=action,
            device_id=device.id,
            mac_address=device.mac_address or "",
            hostname=device.hostname or "",
            extra_arg=extra_arg
        )

    # 2.5 If LOGOFF and dest_ip is known, also send LOGOFF to the destination server if managed
    if action == "LOGOFF" and dest_ip:
        dest_res = await db.execute(select(Device).where((Device.ip_address == dest_ip) | (Device.hostname == dest_ip)))
        dest_dev = dest_res.scalar_one_or_none()
        if dest_dev:
            queue_device_command(
                device_id=dest_dev.id,
                action="LOGOFF",
                reason=f"Admin requested remote LOGOFF for user {sess_username or ''} from {resolved_dev_id}",
                extra_data={"sessionId": session_id, "username": sess_username}
            )
            if dest_dev.ip_address:
                send_direct_lan_power_signal(
                    ip_address=dest_dev.ip_address,
                    action="LOGOFF",
                    device_id=dest_dev.id,
                    mac_address=dest_dev.mac_address or "",
                    hostname=dest_dev.hostname or "",
                    extra_arg=str(session_id)
                )

    # 3. Immediately purge the removed session from live memory
    for k, sess_list in list(live_device_sessions.items()):
        if isinstance(sess_list, list):
            live_device_sessions[k] = [s for s in sess_list if str(s.get("id")) != str(session_id)]

    # 4. Update database device model and broadcast real-time WebSocket update
    if device:
        from backend.app.models.device import RdpStatus
        remaining = live_device_sessions.get(device.id, [])
        device.rdp_status = RdpStatus.ACTIVE if len(remaining) > 0 else RdpStatus.STOPPED
        device.rdp_sessions = remaining
        await db.commit()
        await ws_manager.broadcast_event("device.updated", format_device_summary(device))

    return {
        "status": "success",
        "action": action,
        "sessionId": session_id,
        "message": f"{action} успешно отправлен на {resolved_dev_id}"
    }



