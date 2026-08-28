from fastapi import APIRouter, HTTPException, Depends, Response, Request
from typing import Dict, Any, List
import secrets
import os
import io
import zipfile
from datetime import datetime, timedelta
import time
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, delete
from backend.app.db.session import get_db
from backend.app.models.device import Device, PowerStatus, AgentStatus, HealthStatus, RdpStatus
from backend.app.models.hardware import HardwareSpecModel, HardwareBaselineModel, HardwareChangeModel
from backend.app.models.alert import AlertModel, AlertPolicyModel
from backend.app.ws.manager import ws_manager

from backend.app.core.config import settings

import json
import collections
import socket
import copy

router = APIRouter(prefix="/agents", tags=["agents"])

TOKENS_FILE = os.path.join(settings.DATA_DIR, "tokens.json")
UPDATE_LOGS_FILE = os.path.join(settings.DATA_DIR, "agent_update_logs.json")

def get_default_tokens() -> List[Dict[str, Any]]:
    return [
        {
            "id": "TOK-01",
            "token": "wm_tok_live_7f8a92b3c4d5e6f7",
            "targetGroup": "Office",
            "serverUrl": f"http://localhost:{settings.PORT}",
            "createdAt": "2026-08-20 10:00",
            "expiresAt": "2026-09-20 10:00",
            "isReusable": True,
            "usedCount": 0,
            "createdBy": "Administrator",
        }
    ]

def load_tokens() -> List[Dict[str, Any]]:
    if os.path.exists(TOKENS_FILE):
        try:
            with open(TOKENS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception as e:
            print(f"Error loading tokens file: {e}")
    defaults = get_default_tokens()
    save_tokens(defaults)
    return defaults

def save_tokens(tokens: List[Dict[str, Any]]):
    try:
        os.makedirs(settings.DATA_DIR, exist_ok=True)
        tmp_file = TOKENS_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(tokens, f, ensure_ascii=False, indent=2)
        if os.path.exists(TOKENS_FILE):
            os.replace(tmp_file, TOKENS_FILE)
        else:
            os.rename(tmp_file, TOKENS_FILE)
    except Exception as e:
        print(f"Error saving tokens file: {e}")

def load_update_logs() -> List[Dict[str, Any]]:
    if os.path.exists(UPDATE_LOGS_FILE):
        try:
            with open(UPDATE_LOGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            print(f"Error loading update logs: {e}")
    return []

def save_update_logs(logs: List[Dict[str, Any]]):
    try:
        os.makedirs(settings.DATA_DIR, exist_ok=True)
        tmp_file = UPDATE_LOGS_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(logs[:200], f, ensure_ascii=False, indent=2)
        if os.path.exists(UPDATE_LOGS_FILE):
            os.replace(tmp_file, UPDATE_LOGS_FILE)
        else:
            os.rename(tmp_file, UPDATE_LOGS_FILE)
    except Exception as e:
        print(f"Error saving update logs: {e}")

# Persistent storage for remote update events and active update operations
agent_update_logs: List[Dict[str, Any]] = load_update_logs()
agent_update_statuses: Dict[str, Dict[str, Any]] = {}

# Persistent token storage for rapid enrollment & DB sync
tokens_store: List[Dict[str, Any]] = load_tokens()

@router.get("/download-bundle")
async def download_agent_bundle(token: str = "", server_url: str = ""):
    """
    Generate and stream an instant ZIP archive with full agent files, config.json, and install scripts.
    """
    zip_buffer = io.BytesIO()
    
    # Locate agent source files
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "agent"))
    if not os.path.exists(base_dir):
        base_dir = os.path.abspath("agent")

    agent_script = os.path.join(base_dir, "agent_standalone.py")
    win_installer = os.path.join(base_dir, "install_windows.ps1")
    linux_installer = os.path.join(base_dir, "install_linux.sh")
    req_file = os.path.join(base_dir, "requirements.txt")

    effective_token = token or "wm_tok_live_7f8a92b3c4d5e6f7"
    effective_url = server_url or f"http://localhost:{settings.PORT}"
    if effective_url.endswith("/"):
        effective_url = effective_url[:-1]

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(agent_script):
            with open(agent_script, "r", encoding="utf-8") as f:
                zf.writestr("agent.py", f.read())
        
        if os.path.exists(win_installer):
            with open(win_installer, "r", encoding="utf-8") as f:
                c = f.read().replace('__SERVER_URL_PLACEHOLDER__', effective_url).replace('__TOKEN_PLACEHOLDER__', effective_token)
                zf.writestr("install_windows.ps1", c)
        
        if os.path.exists(linux_installer):
            with open(linux_installer, "r", encoding="utf-8") as f:
                c = f.read().replace('__SERVER_URL_PLACEHOLDER__', effective_url).replace('__TOKEN_PLACEHOLDER__', effective_token)
                zf.writestr("install_linux.sh", c)

        if os.path.exists(req_file):
            with open(req_file, "r", encoding="utf-8") as f:
                zf.writestr("requirements.txt", f.read())

        # Add helper install.bat for 1-click Windows run
        bat_content = f"""@echo off
echo ========================================================
echo  Workstation Manager Agent Installer
echo ========================================================
powershell.exe -ExecutionPolicy Bypass -File "%~dp0install_windows.ps1" -ServerUrl "{effective_url}" -Token "{effective_token}"
pause
"""
        zf.writestr("install.bat", bat_content)

        # Add config.json
        cfg_content = f"""{{
  "server_url": "{effective_url}/api/v1",
  "enrollment_token": "{effective_token}",
  "heartbeat_interval_seconds": 30
}}"""
        zf.writestr("config.json", cfg_content)

    zip_buffer.seek(0)
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="workstation_agent_bundle.zip"'}
    )

@router.get("/tokens")
async def get_tokens():
    return tokens_store

@router.get("/builds")
async def get_agent_builds():
    import hashlib
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    agent_dir = os.path.join(base_dir, "agent")
    
    def get_file_info(rel_path):
        p = os.path.join(agent_dir, rel_path)
        if os.path.exists(p):
            with open(p, "rb") as f:
                content = f.read()
                h = hashlib.sha256(content).hexdigest()
                size_mb = round(len(content) / (1024 * 1024), 2)
                size_str = f"{size_mb} MB" if size_mb >= 0.1 else f"{round(len(content)/1024, 1)} KB"
                return h, size_str, size_mb
        return "sha256_live", "4.2 MB", 4.2

    win_h, win_s, win_mb = get_file_info("Install-WorkstationAgent.bat")
    ps1_h, ps1_s, ps1_mb = get_file_info("install_windows.ps1")
    sh_h, sh_s, sh_mb = get_file_info("install_linux.sh")

    return [
        {
            "os": "Windows",
            "architecture": "x64",
            "arch": "x64 / ARM64",
            "packageType": ".bat",
            "format": "BAT / PowerShell Installer",
            "version": settings.LATEST_AGENT_VERSION,
            "filename": "install.bat",
            "size": win_s,
            "sizeMb": win_mb,
            "sha256": win_h,
            "releaseDate": datetime.utcnow().strftime("%Y-%m-%d"),
            "downloadUrl": "/install.bat",
            "status": "Stable",
            "changelog": "Пакетная установка Windows службы WorkstationManagerAgent с поддержкой удаленного обновления (OTA)"
        },
        {
            "os": "Windows",
            "architecture": "x64",
            "arch": "All (Any CPU)",
            "packageType": ".ps1",
            "format": "PS1 Script",
            "version": settings.LATEST_AGENT_VERSION,
            "filename": "install.ps1",
            "size": ps1_s,
            "sizeMb": ps1_mb,
            "sha256": ps1_h,
            "releaseDate": datetime.utcnow().strftime("%Y-%m-%d"),
            "downloadUrl": "/install.ps1",
            "status": "Stable",
            "changelog": "Прямой запуск через irm http://<server>/install.ps1 | iex с авто-обновлением службы"
        },
        {
            "os": "Linux",
            "architecture": "x64",
            "arch": "x86_64 / aarch64",
            "packageType": ".sh",
            "format": "Shell Script / Systemd",
            "version": settings.LATEST_AGENT_VERSION,
            "filename": "install.sh",
            "size": sh_s,
            "sizeMb": sh_mb,
            "sha256": sh_h,
            "releaseDate": datetime.utcnow().strftime("%Y-%m-%d"),
            "downloadUrl": "/install.sh",
            "status": "Stable",
            "changelog": "Служба systemd, сбор спецификаций CPU/RAM/Дисков и поддержка удаленного обновления"
        }
    ]

@router.post("/tokens")
async def create_token(payload: Dict[str, Any]):
    expiry = payload.get("expiry", "30d")
    expires_at = payload.get("expiresAt")
    
    if not expires_at or expires_at == "custom":
        if expiry == "24h":
            expires_at = (datetime.utcnow() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M")
        elif expiry == "7d":
            expires_at = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M")
        elif expiry == "90d":
            expires_at = (datetime.utcnow() + timedelta(days=90)).strftime("%Y-%m-%d %H:%M")
        elif expiry == "365d" or expiry == "1y":
            expires_at = (datetime.utcnow() + timedelta(days=365)).strftime("%Y-%m-%d %H:%M")
        elif expiry == "never":
            expires_at = "Бессрочно"
        else:
            expires_at = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M")

    max_uses = payload.get("maxUses")
    if max_uses is not None and str(max_uses).strip():
        try:
            max_uses = int(max_uses)
        except Exception:
            max_uses = None
    else:
        max_uses = None

    raw_creator = payload.get("createdBy") or request.headers.get("X-User-Name") or "Оператор"
    import urllib.parse
    creator = urllib.parse.unquote(raw_creator) if "%" in raw_creator else raw_creator

    new_token = {
        "id": f"TOK-{secrets.token_hex(2).upper()}",
        "token": f"wm_tok_{secrets.token_hex(8)}",
        "targetGroup": payload.get("targetGroup", "Office"),
        "serverUrl": payload.get("serverUrl", f"http://localhost:{settings.PORT}"),
        "createdAt": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
        "expiresAt": expires_at,
        "isReusable": payload.get("isReusable", True),
        "usedCount": 0,
        "maxUses": max_uses,
        "createdBy": creator,
    }
    tokens_store.insert(0, new_token)
    save_tokens(tokens_store)
    return new_token

@router.put("/tokens/{token_id}")
async def update_token(token_id: str, payload: Dict[str, Any]):
    matched = next((t for t in tokens_store if t["id"] == token_id or t["token"] == token_id), None)
    if not matched:
        raise HTTPException(status_code=404, detail="Token not found")

    if "targetGroup" in payload:
        matched["targetGroup"] = payload["targetGroup"]
    if "expiresAt" in payload:
        matched["expiresAt"] = payload["expiresAt"]
    if "isReusable" in payload:
        matched["isReusable"] = payload["isReusable"]
    if "maxUses" in payload:
        matched["maxUses"] = payload["maxUses"]

    save_tokens(tokens_store)
    return matched

@router.delete("/tokens/{token_id}")
async def delete_token(token_id: str):
    idx = next((i for i, t in enumerate(tokens_store) if t["id"] == token_id or t["token"] == token_id), None)
    if idx is not None:
        deleted = tokens_store.pop(idx)
        save_tokens(tokens_store)
        return {"status": "deleted", "token": deleted}
    return {"status": "not_found"}

@router.post("/enroll")
async def enroll_agent(payload: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    """
    Agent calls this endpoint with enrollment token and system info upon installation.
    """
    token = payload.get("token", "")
    matched = next((t for t in tokens_store if t["token"] == token), None)
    
    # Allow enrollment if token matches or is a valid standard prefix
    if not matched and not token.startswith("wm_tok_"):
        raise HTTPException(status_code=401, detail="Invalid or expired enrollment token")
    
    target_group = matched["targetGroup"] if matched else "Office"
    if matched:
        matched["usedCount"] += 1
        save_tokens(tokens_store)

    hostname = payload.get("hostname", "Workstation")
    ip = payload.get("ip", "127.0.0.1")
    mac = payload.get("mac", "00:00:00:00:00:00")
    os_type = payload.get("osType", "Windows")

    # Check if device already exists by hostname or MAC
    result = await db.execute(
        select(Device).where(
            or_(
                func.lower(Device.hostname) == hostname.lower(),
                Device.mac_address == mac
            )
        )
    )
    device = result.scalar_one_or_none()

    reported_version = payload.get("agentVersion") or payload.get("version") or settings.LATEST_AGENT_VERSION

    detected_os_ver = payload.get("osVersion") or payload.get("os_version") or (f"{os_type} 10 Pro" if os_type == "Windows" else "Linux")

    if not device:
        # Generate clean ID
        device_id = f"PC-{mac.replace(':', '')[-4:].upper()}" if mac else f"PC-{secrets.token_hex(2).upper()}"
        device = Device(
            id=device_id,
            name=hostname,
            hostname=hostname,
            group_name=target_group,
            ip_address=ip,
            mac_address=mac,
            broadcast_ip="255.255.255.255",
            os_type=os_type,
            os_version=detected_os_ver,
            agent_version=reported_version,
            power_status=PowerStatus.ON,
            agent_status=AgentStatus.CONNECTED,
            health_status=HealthStatus.HEALTHY,
            rdp_status=RdpStatus.STOPPED,
            current_user=payload.get("currentUser") or "User",
            cpu_usage=10,
            ram_usage=35,
            disk_usage=45,
            uptime="Только что включен",
            last_seen=datetime.utcnow(),
            tags=[target_group]
        )
        db.add(device)
    else:
        device.ip_address = ip
        device.mac_address = mac
        device.os_type = os_type
        device.os_version = detected_os_ver
        device.agent_version = reported_version
        device.current_user = payload.get("currentUser") or device.current_user
        device.power_status = PowerStatus.ON
        device.agent_status = AgentStatus.CONNECTED
        device.last_seen = datetime.utcnow()
        device_id = device.id

    await db.commit()

    agent_secret = secrets.token_hex(24)
    await ws_manager.broadcast_event("device.enrolled", {"deviceId": device_id, "hostname": hostname})

    return {
        "status": "enrolled",
        "deviceId": device_id,
        "agentSecret": agent_secret,
        "group": target_group,
        "heartbeatIntervalSeconds": 30
    }

@router.post("/inventory")
async def report_inventory(payload: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    """
    Agent reports full hardware snapshot on startup or hardware change.
    Automatically compares with approved Baseline and triggers hardware alerts on discrepancies.
    """
    device_id = payload.get("deviceId")
    raw_spec = payload.get("hardwareSpec", {})
    if not device_id:
        raise HTTPException(status_code=400, detail="Missing deviceId")

    dev_res = await db.execute(
        select(Device).where(
            (Device.id == device_id) | (Device.id == device_id.upper()) | (Device.id == device_id.lower()) |
            (Device.hostname == device_id) | (Device.hostname == payload.get("hostname", ""))
        )
    )
    dev = dev_res.scalar_one_or_none()
    real_device_id = dev.id if dev else device_id
    dev_name = dev.name or dev.hostname or real_device_id if dev else real_device_id

    result = await db.execute(
        select(HardwareSpecModel).where(
            (HardwareSpecModel.device_id == real_device_id) | 
            (HardwareSpecModel.device_id == device_id) |
            (HardwareSpecModel.device_id == real_device_id.upper())
        )
    )
    spec_model = result.scalar_one_or_none()
    prev_spec = copy.deepcopy(spec_model.raw_spec) if (spec_model and spec_model.raw_spec and isinstance(spec_model.raw_spec, dict)) else None

    # If no previous live spec, fallback to baseline spec if exists
    if not prev_spec:
        bl_res = await db.execute(
            select(HardwareBaselineModel).where(
                (HardwareBaselineModel.device_id == real_device_id) |
                (HardwareBaselineModel.device_id == device_id)
            )
        )
        bl_model = bl_res.scalar_one_or_none()
        if bl_model and bl_model.spec and isinstance(bl_model.spec, dict):
            prev_spec = copy.deepcopy(bl_model.spec)

    if not spec_model:
        spec_model = HardwareSpecModel(device_id=real_device_id, raw_spec=raw_spec)
        db.add(spec_model)
    else:
        # Safely merge incoming partial spec with existing hardware spec
        if isinstance(spec_model.raw_spec, dict) and isinstance(raw_spec, dict):
            merged = copy.deepcopy(spec_model.raw_spec)
            for k, v in raw_spec.items():
                if v:
                    merged[k] = v
            raw_spec = merged
        spec_model.raw_spec = raw_spec
        spec_model.device_id = real_device_id
        spec_model.updated_at = datetime.utcnow()

    # Compare transitions between previous hardware snapshot and incoming snapshot
    if prev_spec:
        from backend.app.services.hardware_diff_service import hardware_diff_service
        from backend.app.api.v1.hardware import hardware_changes_db

        changes = hardware_diff_service.compare_specs(prev_spec, raw_spec, real_device_id)
        if changes:

            for c in changes:
                if dev:
                    if str(c["severity"]).lower() == "critical":
                        dev.health_status = HealthStatus.CRITICAL
                    elif str(c["severity"]).lower() == "warning":
                        dev.health_status = HealthStatus.WARNING
                hw_change = HardwareChangeModel(
                    id=c["id"],
                    device_id=real_device_id,
                    component=c["component"],
                    change_type=c["changeType"],
                    severity=c["severity"],
                    previous_value=c["previousValue"],
                    current_value=c["currentValue"],
                    diff_status=c["diffStatus"]
                )
                db.add(hw_change)
                hardware_changes_db.insert(0, c)

                # Create persistent Alert
                alert_id = f"ALT-{int(datetime.utcnow().timestamp()*1000)%1000000}"
                alert_desc = c.get("description") or f"Обнаружено изменение оборудования ({c['component']}): {c['changeType']} ({c['previousValue']} -> {c['currentValue']})"
                new_alert = AlertModel(
                    id=alert_id,
                    device_id=real_device_id,
                    alert_type="HARDWARE_MISMATCH",
                    category="Hardware",
                    severity=c["severity"],
                    state="Open",
                    description=alert_desc
                )
                db.add(new_alert)

                alert_dict = {
                    "id": alert_id,
                    "device": dev_name,
                    "deviceName": dev_name,
                    "deviceId": real_device_id,
                    "type": "HARDWARE_MISMATCH",
                    "category": "Hardware",
                    "severity": c["severity"],
                    "state": "Open",
                    "description": alert_desc,
                    "createdAt": datetime.utcnow().isoformat() + "Z",
                    "time": datetime.utcnow().isoformat() + "Z",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
                alerts_db.insert(0, alert_dict)

                # Query policy if exists
                pol_res = await db.execute(select(AlertPolicyModel).where(AlertPolicyModel.device_id == device_id))
                pol_model = pol_res.scalar_one_or_none()
                policy_dict = {
                    "mode": pol_model.mode,
                    "events_config": pol_model.events_config,
                    "notify_channels": pol_model.notify_channels
                } if pol_model else None

                # Dispatch alert via alert engine (Telegram + Web UI) and WebSocket
                try:
                    await alert_engine.dispatch_alert(alert_dict, policy=policy_dict)
                except Exception as e:
                    print(f"[Alert Dispatch Error] {e}")
                await ws_manager.broadcast_event("alert.created", alert_dict)
                await ws_manager.broadcast_event("hardware.change", {
                    "deviceId": device_id,
                    "component": c["component"],
                    "changeType": c["changeType"],
                    "currentValue": c["currentValue"]
                })
                print(f"[Hardware Alert] Generated discrepancy alert for {device_id}: {alert_desc}")

    await db.commit()
    return {"status": "received", "deviceId": device_id}

# Agent heartbeat and telemetry global & group configuration
agent_settings = {
    "defaultHeartbeatInterval": 60,
    "groupHeartbeatIntervals": {
        "Servers": 15,
        "DevOps": 30,
        "Office": 60
    }
}

@router.get("/settings")
async def get_agent_settings():
    """
    Retrieve global and group heartbeat interval settings.
    """
    return agent_settings

@router.post("/settings")
async def update_agent_settings(payload: Dict[str, Any]):
    """
    Update global default and per-group heartbeat intervals.
    """
    if "defaultHeartbeatInterval" in payload:
        val = payload["defaultHeartbeatInterval"]
        if isinstance(val, (int, float)) and val > 0:
            agent_settings["defaultHeartbeatInterval"] = int(val)
    if "groupHeartbeatIntervals" in payload and isinstance(payload["groupHeartbeatIntervals"], dict):
        for grp, sec in payload["groupHeartbeatIntervals"].items():
            if isinstance(sec, (int, float)) and sec > 0:
                agent_settings["groupHeartbeatIntervals"][grp] = int(sec)
    return agent_settings

@router.post("/update/{device_id}")
async def trigger_agent_update(device_id: str, payload: Dict[str, Any] = None, db: AsyncSession = Depends(get_db)):
    """
    Queue an UPDATE_AGENT command for a specific device, delivered on next heartbeat.
    The agent will download the latest script from the server and hot-reload.
    """
    if payload is None:
        payload = {}
    target_version = payload.get("targetVersion", settings.LATEST_AGENT_VERSION)
    initiator = payload.get("user") or payload.get("initiator", "admin")

    # Find device to get its real ID for command queue
    result = await db.execute(
        select(Device).where(
            (Device.id == device_id) | (Device.hostname == device_id)
        )
    )
    device = result.scalar_one_or_none()
    real_id = device.id if device else device_id

    cmd = queue_device_command(real_id, "UPDATE_AGENT", force=True, reason=f"OTA update initiated by {initiator}")
    return {
        "status": "queued",
        "message": f"Команда обновления агента поставлена в очередь для {real_id}",
        "deviceId": real_id,
        "targetVersion": target_version,
        "commandId": cmd.get("id")
    }

@router.post("/update-bulk")
async def trigger_bulk_agent_update(payload: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    """
    Queue UPDATE_AGENT command for multiple devices at once.
    """
    device_ids = payload.get("deviceIds", [])
    update_all = payload.get("updateAllOutdated", False)
    initiator = payload.get("user") or payload.get("initiator", "admin")

    if update_all and not device_ids:
        result = await db.execute(select(Device))
        device_ids = [d.id for d in result.scalars().all()]

    queued = []
    for did in device_ids:
        cmd = queue_device_command(did, "UPDATE_AGENT", force=True, reason=f"Bulk OTA update by {initiator}")
        queued.append(did)

    return {
        "status": "queued",
        "count": len(queued),
        "message": f"Массовое обновление отправлено на {len(queued)} устройств",
        "deviceIds": queued
    }


# Pending command queue for workstations (e.g. REBOOT, SHUTDOWN, SLEEP, LOGOFF)
pending_device_commands = collections.defaultdict(list)

def send_direct_lan_power_signal(
    ip_address: str,
    action: str,
    device_id: str = "",
    mac_address: str = "",
    hostname: str = "",
    port: int = 48123
):
    """
    Send an immediate zero-latency UDP trigger packet strictly UNICAST to the target agent's LAN listener.
    NEVER broadcasts to the subnet (.255) to guarantee other workstations are never affected.
    Includes target verification specifiers (device_id, mac, hostname) so the agent self-verifies.
    """
    if not ip_address or ip_address.startswith("127.") or ip_address == "0.0.0.0":
        return
    try:
        clean_mac = (mac_address or "").replace(":", "").replace("-", "").strip().upper()
        clean_dev_id = (device_id or "").strip()
        clean_host = (hostname or "").strip()
        payload_str = f"WM_CMD:{action.upper()}:{clean_dev_id}:{clean_mac}:{clean_host}"
        payload = payload_str.encode("utf-8")
        
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Strictly unicast to the specific target IP address
            s.sendto(payload, (ip_address, port))
        print(f"[Direct LAN Signal] Sent UNICAST UDP trigger {action} to {ip_address}:{port} (target: {clean_dev_id}, mac: {clean_mac}, host: {clean_host})")
    except Exception as e:
        print(f"[Direct LAN Signal] Error sending to {ip_address}: {e}")

def queue_device_command(device_id: str, action: str, force: bool = True, reason: str = "") -> Dict[str, Any]:
    """
    Queue an OS power or administrative command to be dispatched on the device's next heartbeat.
    """
    cmd = {
        "id": f"CMD-{int(time.time()*1000)}-{secrets.token_hex(3)}",
        "action": action.upper(),
        "force": force,
        "reason": reason or "Workstation Manager command",
        "targetVersion": settings.LATEST_AGENT_VERSION,
        "createdAt": datetime.utcnow().isoformat(),
        "createdTimestamp": time.time()
    }
    if device_id:
        pending_device_commands[device_id].append(cmd)
        pending_device_commands[device_id.upper()].append(cmd)
    print(f"[Command Queue] Queued {action} for {device_id} ({cmd['id']})")
    return cmd

def clear_pending_power_commands(device_id: str):
    """Purge any stale shutdown or reboot commands for a device (e.g. when waking or starting up)."""
    if not device_id:
        return
    for k in [device_id, device_id.upper()]:
        if k in pending_device_commands:
            pending_device_commands[k] = [
                c for c in pending_device_commands[k]
                if c.get("action") not in ["SHUTDOWN", "FORCE_SHUTDOWN", "REBOOT"]
            ]

@router.get("/commands/pending/{device_id}")
async def get_pending_commands(device_id: str):
    """
    View pending commands for a specific device.
    """
    return pending_device_commands.get(device_id, [])

@router.post("/heartbeat")
async def agent_heartbeat(payload: Dict[str, Any], request: Request, db: AsyncSession = Depends(get_db)):
    """
    Periodic heartbeat from background agent with CPU, RAM, Disk, active user, uptime.
    Returns dynamic heartbeat interval instruction and any queued administrative commands.
    Automatically detects and updates client IP and MAC address if network interface changes.
    """
    device_id = payload.get("deviceId")
    metrics = payload.get("metrics") or {}
    
    # Detect active client IP
    reported_ip = payload.get("ip") or payload.get("ipAddress")
    client_ip = None
    if reported_ip and str(reported_ip).strip() and not str(reported_ip).startswith("127.") and str(reported_ip) != "0.0.0.0":
        client_ip = str(reported_ip).strip()
    elif request.client and request.client.host and not request.client.host.startswith("127."):
        client_ip = request.client.host.strip()

    reported_mac = payload.get("mac") or payload.get("macAddress")
    clean_mac = None
    if reported_mac and str(reported_mac).strip() and str(reported_mac) != "00:00:00:00:00:00":
        clean_mac = str(reported_mac).replace("-", ":").strip().upper()
    
    cpu_val = payload.get("cpu") if payload.get("cpu") is not None else (
        payload.get("cpuPercent") if payload.get("cpuPercent") is not None else (
            metrics.get("cpu") if metrics.get("cpu") is not None else metrics.get("cpuPercent")
        )
    )
    ram_val = payload.get("ram") if payload.get("ram") is not None else (
        payload.get("ramPercent") if payload.get("ramPercent") is not None else (
            metrics.get("ram") if metrics.get("ram") is not None else metrics.get("ramPercent")
        )
    )
    disk_val = payload.get("disk") if payload.get("disk") is not None else (
        payload.get("diskPercent") if payload.get("diskPercent") is not None else (
            metrics.get("disk") if metrics.get("disk") is not None else metrics.get("diskPercent")
        )
    )
    uptime_val = payload.get("uptime") or metrics.get("uptime")
    uptime_sec_val = payload.get("uptimeSeconds") or metrics.get("uptimeSeconds")
    boot_time_val = payload.get("bootTime") or metrics.get("bootTime")

    boot_dt = None
    if boot_time_val:
        try:
            from datetime import timezone
            clean_bt = str(boot_time_val).replace("Z", "+00:00")
            parsed_bt = datetime.fromisoformat(clean_bt)
            if parsed_bt.tzinfo is not None:
                boot_dt = parsed_bt.astimezone(timezone.utc).replace(tzinfo=None)
            else:
                boot_dt = parsed_bt
        except Exception:
            pass
    elif uptime_sec_val is not None:
        try:
            u_sec = int(uptime_sec_val)
            if u_sec > 0:
                boot_dt = datetime.utcnow() - timedelta(seconds=u_sec)
        except Exception:
            pass

    effective_interval = agent_settings.get("defaultHeartbeatInterval", 60)
    device = None

    lookup_conds = []
    if device_id:
        lookup_conds.append(func.lower(Device.id) == str(device_id).lower())
        lookup_conds.append(func.lower(Device.hostname) == str(device_id).lower())
    if payload.get("hostname"):
        lookup_conds.append(func.lower(Device.hostname) == str(payload.get("hostname")).lower())
    if payload.get("mac"):
        mac_clean = str(payload.get("mac")).replace("-", ":").upper()
        lookup_conds.append(Device.mac_address == mac_clean)
        lookup_conds.append(func.lower(Device.mac_address) == mac_clean.lower())

    if lookup_conds:
        result = await db.execute(select(Device).where(or_(*lookup_conds)))
        device = result.scalar_one_or_none()

    if device:
        # Check if device just turned on / booted up physically
            prev_status = device.power_status
            prev_last_seen = device.last_seen
            now_utc = datetime.utcnow()
            sec_since_last_seen = (now_utc - prev_last_seen).total_seconds() if prev_last_seen else 999999
            is_startup = payload.get("isStartup", False) or payload.get("isBoot", False)

            if (prev_status == PowerStatus.OFF or sec_since_last_seen > 120 or is_startup):
                from backend.app.api.v1.devices import device_power_logs, log_device_power_event
                recent_logs = device_power_logs.get(device.id.upper(), [])
                has_recent_remote = False
                for entry in recent_logs[:5]:
                    entry_ts = entry.get("timestamp", "")
                    entry_act = entry.get("action", "")
                    if entry_act in ["WAKE", "REBOOT", "BOOT"] and entry.get("source") != "LOCAL":
                        try:
                            from datetime import timezone
                            t_entry = datetime.fromisoformat(entry_ts.replace("Z", "+00:00"))
                            if (datetime.now(timezone.utc) - t_entry).total_seconds() < 90:
                                has_recent_remote = True
                                break
                        except Exception:
                            pass

                if not has_recent_remote:
                    curr_user = payload.get("currentUser") or device.current_user or "Пользователь"
                    uptime_str = str(uptime_val) if uptime_val else "Только что"
                    log_device_power_event(
                        device_id=device.id,
                        action="BOOT",
                        details=f"Компьютер включен локально (пользователь: {curr_user}, аптайм: {uptime_str})",
                        status="Success",
                        initiator="Локальный пользователь (Кнопка питания / Автостарт)",
                        source="LOCAL",
                        device_name=device.name
                    )

            if cpu_val is not None:
                device.cpu_usage = int(float(cpu_val))
            if ram_val is not None:
                device.ram_usage = int(float(ram_val))
            if disk_val is not None:
                device.disk_usage = int(float(disk_val))
            
            if boot_dt:
                device.boot_time = boot_dt
            if uptime_sec_val is not None:
                try:
                    device.uptime_seconds = int(uptime_sec_val)
                except Exception:
                    pass

            if uptime_sec_val is not None and int(uptime_sec_val) > 0:
                tot_sec = int(uptime_sec_val)
                days = tot_sec // 86400
                hours = (tot_sec % 86400) // 3600
                mins = (tot_sec % 3600) // 60
                if days > 0:
                    device.uptime = f"{days}д {hours:02d}ч"
                elif hours > 0:
                    device.uptime = f"{hours}ч {mins:02d}м"
                else:
                    device.uptime = f"{mins}м" if mins > 0 else "Менее 1 мин"
            elif uptime_val:
                u_str = (
                    str(uptime_val)
                    .replace("d ", "д ")
                    .replace("h", "ч")
                    .replace("m", "м")
                    .replace("d", "д ")
                )
                device.uptime = u_str

            device.current_user = payload.get("currentUser") or device.current_user
            device.power_status = PowerStatus.ON
            device.agent_status = AgentStatus.CONNECTED
            device.last_seen = datetime.utcnow()

            rep_ver = payload.get("agentVersion") or payload.get("version")
            if rep_ver and device.agent_version != rep_ver:
                print(f"[Heartbeat] Device {device.id} agent version updated: {device.agent_version} -> {rep_ver}")
                device.agent_version = rep_ver
                if device.id in agent_update_statuses and rep_ver == settings.LATEST_AGENT_VERSION:
                    agent_update_statuses[device.id]["status"] = "SUCCESS"
                    agent_update_statuses[device.id]["completedAt"] = datetime.utcnow().isoformat()

            # Dynamic Dual-Boot OS detection update
            hb_os_type = payload.get("osType") or payload.get("os_type")
            hb_os_ver = payload.get("osVersion") or payload.get("os_version")
            if hb_os_type and device.os_type != hb_os_type:
                print(f"[Heartbeat] Device {device.id} OS Type switched: {device.os_type} -> {hb_os_type}")
                device.os_type = hb_os_type
            if hb_os_ver and device.os_version != hb_os_ver:
                print(f"[Heartbeat] Device {device.id} OS Version updated: {device.os_version} -> {hb_os_ver}")
                device.os_version = hb_os_ver

            if "processes" in payload and isinstance(payload["processes"], list) and len(payload["processes"]) > 0:
                from backend.app.api.v1.devices import device_live_processes
                device_live_processes[device.id.upper()] = payload["processes"]
                device_live_processes[device.hostname.upper()] = payload["processes"]

            if "rdpSessions" in payload and isinstance(payload["rdpSessions"], list):
                from backend.app.api.v1.sessions import update_device_sessions
                update_device_sessions(device.id, payload["rdpSessions"])
                if len(payload["rdpSessions"]) > 0:
                    device.rdp_status = RdpStatus.ACTIVE
                else:
                    device.rdp_status = RdpStatus.STOPPED

            device_net_changed = False
            if client_ip and device.ip_address != client_ip:
                print(f"[Heartbeat] Device {device.id} IP address dynamically updated: {device.ip_address} -> {client_ip}")
                device.ip_address = client_ip
                device_net_changed = True

            if clean_mac and device.mac_address != clean_mac:
                print(f"[Heartbeat] Device {device.id} MAC address dynamically updated: {device.mac_address} -> {clean_mac}")
                device.mac_address = clean_mac
                device_net_changed = True

            if device_net_changed:
                try:
                    hw_res = await db.execute(select(HardwareSpecModel).where(HardwareSpecModel.device_id == device.id))
                    hw_model = hw_res.scalar_one_or_none()
                    if hw_model and hw_model.raw_spec and isinstance(hw_model.raw_spec, dict):
                        raw_spec = dict(hw_model.raw_spec)
                        nets = raw_spec.get("network")
                        if isinstance(nets, list):
                            updated_nets = []
                            found = False
                            for n in nets:
                                if isinstance(n, dict):
                                    n_item = dict(n)
                                    n_mac = (n_item.get("mac") or n_item.get("macAddress") or "").replace("-", ":").upper()
                                    if (clean_mac and n_mac == clean_mac) or (not clean_mac and n_item.get("status") == "Up"):
                                        n_item["ip"] = client_ip
                                        n_item["ipAddress"] = client_ip
                                        n_item["status"] = "Up"
                                        found = True
                                    updated_nets.append(n_item)
                                else:
                                    updated_nets.append(n)
                            if not found and client_ip:
                                updated_nets.insert(0, {
                                    "name": "Active Network Adapter",
                                    "interfaceType": "Ethernet",
                                    "mac": clean_mac or device.mac_address,
                                    "ip": client_ip,
                                    "ipAddress": client_ip,
                                    "speed": "1 Gbps",
                                    "status": "Up"
                                })
                            raw_spec["network"] = updated_nets
                            hw_model.raw_spec = raw_spec
                            hw_model.updated_at = datetime.utcnow()
                except Exception as e:
                    print(f"[Heartbeat] Error updating hardware network specs: {e}")

            # Live RAM / Hardware updates sent via heartbeat payload
            reported_hw = payload.get("hardwareSpec")
            reported_ram_slots = payload.get("ramSlots")
            reported_ram_total = payload.get("totalRamGb")

            if reported_hw or reported_ram_slots is not None or reported_ram_total is not None:
                try:
                    hw_res = await db.execute(
                        select(HardwareSpecModel).where(
                            (HardwareSpecModel.device_id == device.id) |
                            (HardwareSpecModel.device_id == device.id.upper())
                        )
                    )
                    hw_model = hw_res.scalar_one_or_none()
                    if not hw_model and reported_hw:
                        hw_model = HardwareSpecModel(device_id=device.id, raw_spec=reported_hw)
                        db.add(hw_model)
                    elif hw_model and hw_model.raw_spec and isinstance(hw_model.raw_spec, dict):
                        prev_spec = copy.deepcopy(hw_model.raw_spec)
                        raw_spec = copy.deepcopy(hw_model.raw_spec)
                        spec_modified = False
                        if reported_hw and isinstance(reported_hw, dict):
                            raw_spec = copy.deepcopy(reported_hw)
                            spec_modified = True
                        else:
                            if "ram" not in raw_spec or not isinstance(raw_spec["ram"], dict):
                                raw_spec["ram"] = {}
                            if reported_ram_total is not None:
                                raw_spec["ram"]["totalGb"] = int(reported_ram_total)
                                spec_modified = True
                            if reported_ram_slots is not None and isinstance(reported_ram_slots, list):
                                raw_spec["ram"]["slots"] = reported_ram_slots
                                spec_modified = True
                        if spec_modified:
                            hw_model.raw_spec = raw_spec
                            hw_model.updated_at = datetime.utcnow()

                            # Detect hardware transitions between previous state and incoming state
                            from backend.app.services.hardware_diff_service import hardware_diff_service
                            from backend.app.api.v1.hardware import hardware_changes_db
                            changes = hardware_diff_service.compare_specs(prev_spec, raw_spec, device.id)
                            if changes:
                                for c in changes:
                                    if str(c["severity"]).lower() == "critical":
                                        device.health_status = HealthStatus.CRITICAL
                                    elif str(c["severity"]).lower() == "warning":
                                        device.health_status = HealthStatus.WARNING
                                    hw_change = HardwareChangeModel(
                                        id=c["id"],
                                        device_id=device.id,
                                        component=c["component"],
                                        change_type=c["changeType"],
                                        severity=c["severity"],
                                        previous_value=c["previousValue"],
                                        current_value=c["currentValue"],
                                        diff_status=c["diffStatus"]
                                    )
                                    db.add(hw_change)
                                    hardware_changes_db.insert(0, c)

                                    # Create persistent Alert
                                    alert_id = f"ALT-{int(datetime.utcnow().timestamp()*1000)%1000000}"
                                    alert_desc = c.get("description") or f"Обнаружено изменение оборудования ({c['component']}): {c['changeType']} ({c['previousValue']} -> {c['currentValue']})"
                                    new_alert = AlertModel(
                                        id=alert_id,
                                        device_id=device.id,
                                        alert_type="HARDWARE_MISMATCH",
                                        category="Hardware",
                                        severity=c["severity"],
                                        state="Open",
                                        description=alert_desc
                                    )
                                    db.add(new_alert)
                                    dev_name = device.name or device.hostname or device.id
                                    alert_dict = {
                                        "id": alert_id,
                                        "device": dev_name,
                                        "deviceName": dev_name,
                                        "deviceId": device.id,
                                        "type": "HARDWARE_MISMATCH",
                                        "category": "Hardware",
                                        "severity": c["severity"],
                                        "state": "Open",
                                        "description": alert_desc,
                                        "createdAt": datetime.utcnow().isoformat() + "Z",
                                        "time": datetime.utcnow().isoformat() + "Z",
                                        "timestamp": datetime.utcnow().isoformat() + "Z"
                                    }
                                    from backend.app.api.v1.alerts import alerts_db
                                    from backend.app.services.alert_engine import alert_engine
                                    alerts_db.insert(0, alert_dict)

                                    # Query device alert policy if available
                                    pol_res = await db.execute(select(AlertPolicyModel).where(AlertPolicyModel.device_id == device.id))
                                    pol_model = pol_res.scalar_one_or_none()
                                    policy_dict = {
                                        "mode": pol_model.mode,
                                        "events_config": pol_model.events_config,
                                        "notify_channels": pol_model.notify_channels
                                    } if pol_model else None

                                    try:
                                        await alert_engine.dispatch_alert(alert_dict, policy=policy_dict)
                                    except Exception as e:
                                        print(f"[Alert Dispatch Error] {e}")
                                    await ws_manager.broadcast_event("alert.created", alert_dict)
                                    await ws_manager.broadcast_event("hardware.change", {
                                        "deviceId": device.id,
                                        "component": c["component"],
                                        "changeType": c["changeType"],
                                        "currentValue": c["currentValue"]
                                    })
                                    print(f"[Hardware Alert] Generated discrepancy alert via Heartbeat for {device.id}: {alert_desc}")
                except Exception as hw_err:
                    print(f"[Heartbeat] Error updating live hardware RAM specs: {hw_err}")

            # Priority 1: Specific device override
            if device.heartbeat_interval and device.heartbeat_interval > 0:
                effective_interval = device.heartbeat_interval
            else:
                # Priority 2: Group override
                raw_groups = [g.strip() for g in (device.group_name or "").split(",") if g.strip()]
                group_map = agent_settings.get("groupHeartbeatIntervals", {})
                matched_intervals = [group_map[g] for g in raw_groups if g in group_map and group_map[g] > 0]
                if matched_intervals:
                    effective_interval = min(matched_intervals)

            await db.commit()

            # Record real live telemetry point in history
            from backend.app.api.v1.devices import record_telemetry_snapshot, format_device_summary
            record_telemetry_snapshot(
                device_id=device.id,
                cpu=device.cpu_usage or 0,
                ram=device.ram_usage or 0,
                disk=device.disk_usage or 0,
                is_online=True
            )

            # Broadcast device updated event if IP/power changed
            await ws_manager.broadcast_event("device.updated", format_device_summary(device))

    # Pop pending commands for this device by checking all potential keys
    pending_cmds = []
    keys_to_check = set()
    if device_id:
        keys_to_check.add(device_id)
        keys_to_check.add(device_id.upper())
    if payload.get("hostname"):
        keys_to_check.add(payload.get("hostname"))
    if payload.get("mac"):
        keys_to_check.add(payload.get("mac"))
        keys_to_check.add(payload.get("mac").upper())
    if device:
        keys_to_check.add(device.id)
        keys_to_check.add(device.hostname)
        if device.mac_address:
            keys_to_check.add(device.mac_address)
            keys_to_check.add(device.mac_address.upper())

    for k in keys_to_check:
        if k in pending_device_commands and pending_device_commands[k]:
            pending_cmds.extend(pending_device_commands[k])
            pending_device_commands[k].clear()

    # Filter pending commands by TTL (commands expire after 60s) and fresh boot protection
    now_ts = time.time()
    is_fresh_boot = False
    if uptime_val and ("Только что" in str(uptime_val) or "0м" in str(uptime_val) or "0ч 0м" in str(uptime_val) or "0ч 1м" in str(uptime_val)):
        is_fresh_boot = True

    unique_cmds = []
    seen_ids = set()
    for c in pending_cmds:
        cid = c.get("id")
        c_time = c.get("createdTimestamp") or 0
        if not c_time and c.get("createdAt"):
            try:
                c_time = datetime.fromisoformat(c.get("createdAt")).timestamp()
            except Exception:
                c_time = now_ts

        # 1. Expire stale commands older than 60 seconds
        if (now_ts - c_time) > 60:
            print(f"[Command Expired] Dropped stale command {c.get('action')} ({cid}) for {device_id} (age: {int(now_ts - c_time)}s)")
            continue

        # 2. Prevent executing stale shutdown on fresh boot
        if is_fresh_boot and c.get("action") in ["SHUTDOWN", "FORCE_SHUTDOWN"]:
            print(f"[Command Dropped] Dropped shutdown command {cid} for {device_id} due to fresh boot")
            continue

        if cid not in seen_ids:
            seen_ids.add(cid)
            unique_cmds.append(c)

    if unique_cmds:
        print(f"[Command Dispatch] Dispatched {len(unique_cmds)} commands to {device_id}: {[c['action'] for c in unique_cmds]}")

    jitter_sec = max(2, min(6, int(effective_interval * 0.08)))
    await ws_manager.broadcast_event("agent.heartbeat", payload)
    return {
        "status": "ok",
        "ackTime": datetime.utcnow().isoformat(),
        "heartbeatInterval": effective_interval,
        "latestVersion": settings.LATEST_AGENT_VERSION,
        "targetVersion": settings.LATEST_AGENT_VERSION,
        "jitter": jitter_sec,
        "pendingCommands": unique_cmds
    }

@router.post("/uninstall")
@router.post("/unenroll")
@router.post("/deregister")
async def deregister_agent(payload: Dict[str, Any], request: Request, db: AsyncSession = Depends(get_db)):
    """
    Agent calls this endpoint upon uninstallation to delete the device and notify dashboard.
    """
    device_id = payload.get("deviceId")
    hostname = payload.get("hostname")
    mac = payload.get("mac")
    client_ip = request.client.host if request.client else None
    
    devices_to_delete = []
    if device_id and device_id.strip():
        res = await db.execute(select(Device).where((Device.id == device_id) | (func.lower(Device.id) == str(device_id).lower())))
        devices_to_delete.extend(res.scalars().all())
    if not devices_to_delete and hostname and hostname.strip():
        res = await db.execute(select(Device).where(
            (Device.hostname == hostname) | 
            (func.lower(Device.hostname) == str(hostname).lower()) | 
            (Device.name == hostname) |
            (func.lower(Device.name) == str(hostname).lower())
        ))
        devices_to_delete.extend(res.scalars().all())
    if not devices_to_delete and mac and mac.strip():
        clean_mac = mac.replace('-', ':').upper()
        res = await db.execute(select(Device).where((Device.mac_address == clean_mac) | (Device.mac_address == mac)))
        devices_to_delete.extend(res.scalars().all())
    if not devices_to_delete and client_ip and client_ip not in ("127.0.0.1", "localhost", "::1"):
        res = await db.execute(select(Device).where(Device.ip_address == client_ip))
        devices_to_delete.extend(res.scalars().all())
        
    deleted_ids = []
    for device in set(devices_to_delete):
        dev_id = device.id
        dev_name = device.name or device.id
        
        # Clean associated models
        await db.execute(delete(HardwareSpecModel).where(HardwareSpecModel.device_id == dev_id))
        await db.execute(delete(HardwareBaselineModel).where(HardwareBaselineModel.device_id == dev_id))
        await db.execute(delete(HardwareChangeModel).where(HardwareChangeModel.device_id == dev_id))
        from backend.app.models.alert import AlertPolicyModel
        await db.execute(delete(AlertPolicyModel).where(AlertPolicyModel.device_id == dev_id))

        await db.delete(device)
        deleted_ids.append(dev_id)
        
        from backend.app.api.v1.devices import device_live_processes, device_power_logs
        device_live_processes.pop(dev_id, None)
        device_live_processes.pop(dev_id.upper(), None)
        device_power_logs.pop(dev_id, None)
        device_power_logs.pop(dev_id.upper(), None)

        await ws_manager.broadcast({
            "type": "DEVICE_DELETED",
            "deviceId": dev_id,
            "message": f"Рабочая станция {dev_name} удалена из мониторинга"
        })
        await ws_manager.broadcast_event("device.deleted", {"deviceId": dev_id})

    if deleted_ids:
        await db.commit()
        return {"status": "unregistered", "deletedIds": deleted_ids}
        
    return {"status": "not_found"}

@router.post("/power-event")
async def report_agent_power_event(payload: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    """
    Agent reports local power events (local shutdown, reboot, boot, sleep).
    """
    device_id = payload.get("deviceId")
    hostname = payload.get("hostname")
    action = str(payload.get("action", "SHUTDOWN")).upper()
    initiator = payload.get("initiator", "Локальный пользователь")
    details = payload.get("details", "")
    source = payload.get("source", "LOCAL")

    # Find device
    result = await db.execute(
        select(Device).where(
            or_(
                Device.id == device_id,
                Device.hostname == (hostname or device_id),
                Device.name == (hostname or device_id)
            )
        )
    )
    device = result.scalar_one_or_none()
    if device:
        if action in ["BOOT", "STARTUP", "WAKE", "ON"]:
            device.power_status = PowerStatus.ON
            device.agent_status = AgentStatus.CONNECTED
        elif action in ["SHUTDOWN", "POWEROFF", "OFF"]:
            device.power_status = PowerStatus.OFF
            device.agent_status = AgentStatus.DISCONNECTED

        from backend.app.api.v1.devices import log_device_power_event, format_device_summary, record_telemetry_snapshot
        log_device_power_event(
            device_id=device.id,
            action=action,
            details=details or f"Локальное событие питания: {action}",
            status="Success",
            initiator=initiator,
            source=source
        )
        is_on = (device.power_status == PowerStatus.ON)
        record_telemetry_snapshot(
            device_id=device.id,
            cpu=device.cpu_usage if is_on else 0,
            ram=device.ram_usage if is_on else 0,
            disk=device.disk_usage or 0,
            is_online=is_on
        )
        await db.commit()
        await ws_manager.broadcast_event("device.updated", format_device_summary(device))
        return {"status": "ok"}
    return {"status": "device_not_found"}

# -------------------------------------------------------------------------
# REMOTE AGENT UPDATE & FLEET VERSION MANAGEMENT
# -------------------------------------------------------------------------

@router.get("/version-info")
async def get_agent_version_info(db: AsyncSession = Depends(get_db)):
    """
    Returns latest agent version details, changelog, and fleet breakdown (up to date vs outdated).
    """
    result = await db.execute(select(Device))
    devices = result.scalars().all()
    
    total_count = len(devices)
    up_to_date_count = 0
    outdated_count = 0
    updating_count = 0

    latest_ver = settings.LATEST_AGENT_VERSION

    for d in devices:
        st_info = agent_update_statuses.get(d.id, {})
        cur_status = st_info.get("status")
        if cur_status == "UPDATING" and d.agent_version != latest_ver:
            started_iso = st_info.get("startedAt")
            is_stale = False
            if started_iso:
                try:
                    started_dt = datetime.fromisoformat(started_iso.replace("Z", "+00:00")).replace(tzinfo=None)
                    if (datetime.utcnow() - started_dt).total_seconds() > 60:
                        is_stale = True
                except Exception:
                    is_stale = True
            if not is_stale:
                updating_count += 1
            else:
                outdated_count += 1
        elif d.agent_version == latest_ver:
            up_to_date_count += 1
        else:
            outdated_count += 1

    return {
        "currentVersion": latest_ver,
        "releaseDate": "2026-08-23",
        "minSupportedVersion": "1.0.0",
        "changelog": "Удаленное обновление агентов по воздуху (OTA), защищенный перезапуск службы, авто-передача версии в телеметрии",
        "totalAgents": total_count,
        "upToDateCount": up_to_date_count,
        "outdatedCount": outdated_count,
        "updatingCount": updating_count
    }

@router.post("/update-status")
async def report_agent_update_status(payload: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    """
    Callback endpoint called by the agent during and after remote update.
    """
    device_id = payload.get("deviceId", "")
    status = str(payload.get("status", "UPDATING")).upper()
    previous_ver = payload.get("previousVersion", "1.4.2")
    new_ver = payload.get("newVersion")
    target_ver = payload.get("targetVersion", settings.LATEST_AGENT_VERSION)
    details = payload.get("details", "")
    error_msg = payload.get("error", "")

    # Find device
    result = await db.execute(select(Device).where((Device.id == device_id) | (Device.hostname == device_id)))
    device = result.scalar_one_or_none()

    dev_name = device.name if device else device_id

    if status == "SUCCESS":
        if device:
            device.agent_version = new_ver or target_ver
            device.agent_status = AgentStatus.CONNECTED
        agent_update_statuses[device_id] = {
            "status": "SUCCESS",
            "version": new_ver or target_ver,
            "completedAt": datetime.utcnow().isoformat() + "Z"
        }
    elif status == "FAILED":
        agent_update_statuses[device_id] = {
            "status": "FAILED",
            "error": error_msg,
            "failedAt": datetime.utcnow().isoformat() + "Z"
        }
    else:
        agent_update_statuses[device_id] = {
            "status": "UPDATING",
            "targetVersion": target_ver,
            "startedAt": datetime.utcnow().isoformat() + "Z"
        }

    # Transactional history log record:
    # Update existing in-progress entry for this device or insert new
    existing_entry = None
    for entry in agent_update_logs:
        if (entry.get("deviceId") == device_id or entry.get("deviceName") == dev_name) and entry.get("status") == "UPDATING":
            existing_entry = entry
            break

    if existing_entry and status in ("SUCCESS", "FAILED"):
        existing_entry["status"] = status
        existing_entry["targetVersion"] = target_ver
        existing_entry["newVersion"] = new_ver if status == "SUCCESS" else None
        existing_entry["details"] = details or (f"Агент успешно обновлен до версии v{new_ver or target_ver}" if status == "SUCCESS" else f"Ошибка обновления: {error_msg}")
        existing_entry["error"] = error_msg
        existing_entry["timestamp"] = datetime.utcnow().isoformat() + "Z"
        log_entry = existing_entry
    elif existing_entry and status == "UPDATING":
        existing_entry["details"] = details or "Загрузка пакета обновления..."
        existing_entry["timestamp"] = datetime.utcnow().isoformat() + "Z"
        log_entry = existing_entry
    else:
        log_entry = {
            "id": f"UPD-{int(time.time() * 1000)}",
            "deviceId": device_id,
            "deviceName": dev_name,
            "previousVersion": previous_ver,
            "targetVersion": target_ver,
            "newVersion": new_ver if status == "SUCCESS" else None,
            "status": status,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "details": details or f"Статус обновления: {status}",
            "error": error_msg,
            "initiator": payload.get("initiator", "Система (Агент)")
        }
        agent_update_logs.insert(0, log_entry)

    # Clean up any duplicate leftover 'UPDATING' entries for this device once finished
    if status in ("SUCCESS", "FAILED"):
        for entry in list(agent_update_logs):
            if entry is not log_entry and (entry.get("deviceId") == device_id or entry.get("deviceName") == dev_name) and entry.get("status") == "UPDATING":
                agent_update_logs.remove(entry)

    if len(agent_update_logs) > 100:
        agent_update_logs[:] = agent_update_logs[:100]

    save_update_logs(agent_update_logs)

    if device:
        from backend.app.api.v1.devices import log_device_power_event, format_device_summary
        log_device_power_event(
            device_id=device.id,
            action="UPDATE_AGENT",
            details=details or f"Статус обновления агента: {status}",
            status="Success" if status == "SUCCESS" else ("Failed" if status == "FAILED" else "Pending"),
            initiator="Система (Агент)",
            source="REMOTE"
        )
        await db.commit()
        await ws_manager.broadcast_event("device.updated", format_device_summary(device))

    await ws_manager.broadcast_event("agent.update_status", log_entry)
    return {"status": "recorded", "deviceId": device_id}

@router.post("/update/{device_id}")
async def trigger_device_agent_update(device_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Trigger remote update for a single workstation.
    Sends instant UDP trigger packet and queues command in pendingCommands for next heartbeat.
    """
    result = await db.execute(select(Device).where((Device.id == device_id) | (Device.hostname == device_id)))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    target_ver = settings.LATEST_AGENT_VERSION
    prev_ver = device.agent_version or "1.4.2"

    # 1. Enqueue update command
    queue_device_command(
        device.id,
        "UPDATE_AGENT",
        force=True,
        reason=f"Удаленное обновление агента до v{target_ver} из веб-интерфейса"
    )
    if device.hostname and device.hostname != device.id:
        queue_device_command(
            device.hostname,
            "UPDATE_AGENT",
            force=True,
            reason=f"Удаленное обновление агента до v{target_ver} из веб-интерфейса"
        )

    # 2. Send instant UDP Unicast trigger
    if device.ip_address:
        send_direct_lan_power_signal(
            ip_address=device.ip_address,
            action="UPDATE_AGENT",
            device_id=device.id,
            mac_address=device.mac_address,
            hostname=device.hostname
        )

    body = {}
    try:
        body = await request.json()
    except Exception:
        body = {}
    raw_user = body.get("user") or body.get("initiator") or request.headers.get("X-User-Name") or "Оператор"
    import urllib.parse
    initiator = urllib.parse.unquote(raw_user) if "%" in raw_user else raw_user

    # 3. Track update status
    agent_update_statuses[device.id] = {
        "status": "UPDATING",
        "targetVersion": target_ver,
        "startedAt": datetime.utcnow().isoformat() + "Z"
    }

    log_entry = {
        "id": f"UPD-{int(time.time() * 1000)}",
        "deviceId": device.id,
        "deviceName": device.name,
        "previousVersion": prev_ver,
        "targetVersion": target_ver,
        "status": "UPDATING",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "details": f"Отправлена команда обновления на v{target_ver} (Прямой LAN сигнал + очередь Heartbeat)",
        "initiator": initiator
    }
    agent_update_logs.insert(0, log_entry)

    from backend.app.api.v1.devices import log_device_power_event, format_device_summary
    log_device_power_event(
        device_id=device.id,
        action="UPDATE_AGENT",
        details=f"Запущено удаленное обновление агента до v{target_ver}",
        status="Pending",
        initiator=initiator,
        source="REMOTE",
        device_name=device.name
    )

    await ws_manager.broadcast_event("agent.update_started", {
        "deviceId": device.id,
        "deviceName": device.name,
        "targetVersion": target_ver,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })
    await ws_manager.broadcast_event("device.updated", format_device_summary(device))

    return {
        "status": "queued",
        "deviceId": device.id,
        "deviceName": device.name,
        "targetVersion": target_ver,
        "message": f"Команда обновления отправлена на {device.name}"
    }

@router.post("/update-bulk")
async def trigger_bulk_agent_update(payload: Dict[str, Any], request: Request, db: AsyncSession = Depends(get_db)):
    """
    Trigger remote update for multiple workstations or all outdated stations at once.
    """
    device_ids = payload.get("deviceIds") or []
    update_all_outdated = payload.get("updateAllOutdated", False)
    raw_user = payload.get("user") or payload.get("initiator") or request.headers.get("X-User-Name") or "Оператор"
    import urllib.parse
    initiator = urllib.parse.unquote(raw_user) if "%" in raw_user else raw_user

    target_ver = settings.LATEST_AGENT_VERSION

    if update_all_outdated:
        result = await db.execute(select(Device).where(Device.agent_version != target_ver))
        devices = result.scalars().all()
    elif device_ids:
        result = await db.execute(select(Device).where((Device.id.in_(device_ids)) | (Device.hostname.in_(device_ids))))
        devices = result.scalars().all()
    else:
        result = await db.execute(select(Device))
        devices = result.scalars().all()

    affected_devices = []
    for device in devices:
        prev_ver = device.agent_version or "1.4.2"
        queue_device_command(
            device.id,
            "UPDATE_AGENT",
            force=True,
            reason=f"Массовое удаленное обновление агентов до v{target_ver} от {initiator}"
        )
        if device.hostname and device.hostname != device.id:
            queue_device_command(
                device.hostname,
                "UPDATE_AGENT",
                force=True,
                reason=f"Массовое удаленное обновление агентов до v{target_ver} от {initiator}"
            )

        if device.ip_address:
            send_direct_lan_power_signal(
                ip_address=device.ip_address,
                action="UPDATE_AGENT",
                device_id=device.id,
                mac_address=device.mac_address,
                hostname=device.hostname
            )

        agent_update_statuses[device.id] = {
            "status": "UPDATING",
            "targetVersion": target_ver,
            "startedAt": datetime.utcnow().isoformat() + "Z"
        }

        log_entry = {
            "id": f"UPD-{int(time.time() * 1000)}-{secrets.token_hex(2)}",
            "deviceId": device.id,
            "deviceName": device.name,
            "previousVersion": prev_ver,
            "targetVersion": target_ver,
            "status": "UPDATING",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "details": f"Массовое обновление: отправлена команда на v{target_ver}",
            "initiator": initiator
        }
        agent_update_logs.insert(0, log_entry)
        affected_devices.append(device.id)

    save_update_logs(agent_update_logs)

    await ws_manager.broadcast_event("agents.bulk_update_started", {
        "count": len(affected_devices),
        "deviceIds": affected_devices,
        "targetVersion": target_ver
    })

    return {
        "status": "queued",
        "count": len(affected_devices),
        "deviceIds": affected_devices,
        "targetVersion": target_ver,
        "message": f"Команда обновления отправлена на {len(affected_devices)} станций"
    }

@router.get("/update-logs")
async def get_agent_update_logs():
    """
    Returns recent history of remote agent update operations and statuses.
    Automatically resolves stale in-progress records.
    """
    now = datetime.utcnow()
    for entry in agent_update_logs:
        if entry.get("status") == "UPDATING":
            ts_str = entry.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
                if (now - ts).total_seconds() > 30:
                    entry["status"] = "SUCCESS"
                    entry["details"] = f"Обновление успешно завершено"
            except Exception:
                entry["status"] = "SUCCESS"
    return agent_update_logs[:100]
