from fastapi import APIRouter, Depends, Request, HTTPException
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
    username: Optional[str] = None
    sessionName: Optional[str] = None
    clientIp: Optional[str] = None
    remoteHost: Optional[str] = None

@router.post("/{session_id}/logoff")
async def logoff_session(
    session_id: int,
    request: Request,
    device_id: Optional[str] = None,
    deviceId: Optional[str] = None,
    req: Optional[LogoffRequest] = None,
    db: AsyncSession = Depends(get_db)
):
    raw_role = request.headers.get("X-User-Role") or ""
    import urllib.parse
    user_role = urllib.parse.unquote(raw_role).strip() if "%" in raw_role else raw_role.strip()
    if user_role in ["Наблюдатель", "Observer"]:
        raise HTTPException(
            status_code=403,
            detail="Отказ в доступе: роль «Наблюдатель» имеет доступ только для чтения и не может завершать сессии."
        )

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

    # Determine session properties
    sess_username = req.username if (req and req.username) else None
    dest_ip = req.remoteHost if (req and req.remoteHost) else None
    client_ip = req.clientIp if (req and req.clientIp) else None
    is_outgoing = req.isOutgoing if (req and req.isOutgoing is not None) else False

    # Look up session info from live_device_sessions if missing
    for sess_list in live_device_sessions.values():
        if isinstance(sess_list, list):
            for s in sess_list:
                if str(s.get("id")) == str(session_id):
                    if not sess_username:
                        sess_username = s.get("username")
                    if not dest_ip:
                        s_name = str(s.get("sessionName", ""))
                        if "->" in s_name:
                            dest_ip = s_name.split("->")[-1].strip().split(":")[0].strip()
                        elif s.get("clientIp"):
                            dest_ip = str(s.get("clientIp")).strip()
                    if not client_ip and s.get("clientIp"):
                        client_ip = str(s.get("clientIp")).strip()
                    if not target_pid and s.get("pid"):
                        target_pid = s.get("pid")
                    if not target_type and s.get("type"):
                        target_type = s.get("type")
                    s_type_str = str(s.get("type") or "").lower()
                    if "исходящий" in s_type_str or "mstsc" in str(s.get("sessionName", "")).lower():
                        is_outgoing = True
                    break
        if sess_username and dest_ip:
            break

    if target_type and "исходящий" in str(target_type).lower():
        is_outgoing = True
    if session_id >= 100:
        is_outgoing = True

    action = "LOGOFF"
    dev_ip = (device.ip_address if device and device.ip_address else "").strip()
    remote_sess_id = 0
    remote_username = sess_username or ""
    dest_dev = None

    if is_outgoing and dest_ip:
        clean_dest_ip = dest_ip.split(":")[0].strip()
        dest_res = await db.execute(
            select(Device).where(
                (Device.ip_address == clean_dest_ip) |
                (Device.hostname == clean_dest_ip) |
                (Device.name == clean_dest_ip) |
                (Device.id == clean_dest_ip)
            )
        )
        dest_dev = dest_res.scalar_one_or_none()

        # 1. Reverse lookup: find the corresponding incoming session on the destination server
        target_keys = [clean_dest_ip, clean_dest_ip.upper(), clean_dest_ip.lower()]
        if dest_dev:
            target_keys.extend([dest_dev.id, dest_dev.id.upper(), dest_dev.id.lower()])
            if dest_dev.hostname:
                target_keys.extend([dest_dev.hostname, dest_dev.hostname.upper(), dest_dev.hostname.lower()])

        dest_sessions = []
        for tk in target_keys:
            if tk in live_device_sessions and live_device_sessions[tk]:
                dest_sessions = live_device_sessions[tk]
                break

        matching_sess = None
        for ds in dest_sessions:
            ds_client_ip = str(ds.get("clientIp") or "").strip()
            ds_user = str(ds.get("username") or "").strip().lower()
            if dev_ip and ds_client_ip and ds_client_ip == dev_ip:
                matching_sess = ds
                break
            if sess_username and ds_user and ds_user == sess_username.lower():
                matching_sess = ds
                break

        if not matching_sess and dest_sessions:
            for ds in dest_sessions:
                if ds.get("id") and int(ds.get("id")) < 100:
                    matching_sess = ds
                    break

        if matching_sess:
            remote_sess_id = matching_sess.get("id") or 0
            remote_username = matching_sess.get("username") or sess_username or ""

        # 2. Dispatch LOGOFF command to the remote destination host (clean_dest_ip)
        remote_extra_arg = f"{remote_sess_id}|{remote_username}|0||{dev_ip}"
        if dest_dev:
            queue_device_command(
                device_id=dest_dev.id,
                action="LOGOFF",
                reason=f"Admin requested remote LOGOFF for user {remote_username} from {resolved_dev_id}",
                extra_data={"sessionId": remote_sess_id, "username": remote_username, "clientIp": dev_ip, "remoteHost": clean_dest_ip}
            )
            if dest_dev.ip_address:
                send_direct_lan_power_signal(
                    ip_address=dest_dev.ip_address,
                    action="LOGOFF",
                    device_id=dest_dev.id,
                    mac_address=dest_dev.mac_address or "",
                    hostname=dest_dev.hostname or "",
                    extra_arg=remote_extra_arg
                )

        # Fallback queue & UDP directly to clean_dest_ip
        for target_key in [clean_dest_ip, clean_dest_ip.upper(), clean_dest_ip.lower()]:
            queue_device_command(
                device_id=target_key,
                action="LOGOFF",
                reason=f"Admin requested remote LOGOFF for user {remote_username}",
                extra_data={"sessionId": remote_sess_id, "username": remote_username, "clientIp": dev_ip, "remoteHost": clean_dest_ip}
            )
        send_direct_lan_power_signal(
            ip_address=clean_dest_ip,
            action="LOGOFF",
            device_id="REMOTE",
            mac_address="",
            hostname=clean_dest_ip,
            extra_arg=remote_extra_arg
        )

        # 3. Dispatch command to local client workstation (close mstsc and perform RPC logoff fallback)
        local_extra_arg = f"{target_pid or session_id}|{sess_username or ''}|{target_pid or 0}|{clean_dest_ip}|{dev_ip}"
        queue_device_command(
            device_id=resolved_dev_id,
            action=action,
            reason=f"Admin requested {action} for outgoing session #{session_id} to {clean_dest_ip}",
            extra_data={"sessionId": session_id, "pid": target_pid, "type": target_type, "username": sess_username, "remoteHost": clean_dest_ip, "clientIp": dev_ip}
        )
        if device and device.ip_address:
            send_direct_lan_power_signal(
                ip_address=device.ip_address,
                action=action,
                device_id=device.id,
                mac_address=device.mac_address or "",
                hostname=device.hostname or "",
                extra_arg=local_extra_arg
            )

    else:
        # INCOMING session on device: device is the server hosting the RDP session
        # Format extra_arg: sessionId|username|pid|remoteHost|clientIp
        incoming_extra_arg = f"{session_id}|{sess_username or ''}|0||{client_ip or ''}"
        queue_device_command(
            device_id=resolved_dev_id,
            action=action,
            reason=f"Admin requested {action} for incoming session #{session_id}",
            extra_data={"sessionId": session_id, "username": sess_username, "clientIp": client_ip}
        )
        if device and device.ip_address:
            send_direct_lan_power_signal(
                ip_address=device.ip_address,
                action=action,
                device_id=device.id,
                mac_address=device.mac_address or "",
                hostname=device.hostname or "",
                extra_arg=incoming_extra_arg
            )

        # Also, if client_ip is known (managed workstation that started mstsc), close mstsc there
        if client_ip and client_ip != "-" and not client_ip.startswith("127."):
            clean_client_ip = client_ip.split(":")[0].strip()
            client_res = await db.execute(
                select(Device).where(
                    (Device.ip_address == clean_client_ip) |
                    (Device.hostname == clean_client_ip) |
                    (Device.name == clean_client_ip) |
                    (Device.id == clean_client_ip)
                )
            )
            client_dev = client_res.scalar_one_or_none()
            client_extra_arg = f"0||0|{dev_ip}|"
            if client_dev:
                queue_device_command(
                    device_id=client_dev.id,
                    action="LOGOFF",
                    reason=f"Remote session on {resolved_dev_id} ended, closing local mstsc",
                    extra_data={"sessionId": 0, "remoteHost": dev_ip}
                )
                if client_dev.ip_address:
                    send_direct_lan_power_signal(
                        ip_address=client_dev.ip_address,
                        action="LOGOFF",
                        device_id=client_dev.id,
                        mac_address=client_dev.mac_address or "",
                        hostname=client_dev.hostname or "",
                        extra_arg=client_extra_arg
                    )
            send_direct_lan_power_signal(
                ip_address=clean_client_ip,
                action="LOGOFF",
                device_id="CLIENT",
                mac_address="",
                hostname=clean_client_ip,
                extra_arg=client_extra_arg
            )

    # 4. Immediately purge the removed session (and any remote paired session) from live memory
    ids_to_purge = {str(session_id)}
    if remote_sess_id and remote_sess_id > 0:
        ids_to_purge.add(str(remote_sess_id))

    for k, sess_list in list(live_device_sessions.items()):
        if isinstance(sess_list, list):
            live_device_sessions[k] = [s for s in sess_list if str(s.get("id")) not in ids_to_purge]

    # 5. Update database device model and broadcast real-time WebSocket update for both devices
    if device:
        from backend.app.models.device import RdpStatus
        remaining = live_device_sessions.get(device.id, [])
        device.rdp_status = RdpStatus.ACTIVE if len(remaining) > 0 else RdpStatus.STOPPED
        device.rdp_sessions = remaining
        await db.commit()
        await ws_manager.broadcast_event("device.updated", format_device_summary(device))

    if dest_dev and dest_dev.id != (device.id if device else None):
        from backend.app.models.device import RdpStatus
        dest_remaining = live_device_sessions.get(dest_dev.id, [])
        dest_dev.rdp_status = RdpStatus.ACTIVE if len(dest_remaining) > 0 else RdpStatus.STOPPED
        dest_dev.rdp_sessions = dest_remaining
        await db.commit()
        await ws_manager.broadcast_event("device.updated", format_device_summary(dest_dev))

    return {
        "status": "success",
        "action": action,
        "sessionId": session_id,
        "message": f"{action} успешно отправлен на {resolved_dev_id}"
    }



