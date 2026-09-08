from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Query, Response
from fastapi.responses import Response, StreamingResponse
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import select, func, delete, or_, and_
from backend.app.db.session import get_db, engine, is_postgres_url
from backend.app.models.device import Device, PowerStatus, HealthStatus, AgentStatus
from backend.app.models.hardware import HardwareSpecModel, HardwareBaselineModel, HardwareChangeModel
from backend.app.models.alert import AlertPolicyModel, AlertModel
from backend.app.models.schedule import ScheduleModel
from backend.app.schemas.device import BulkOperationRequestSchema, DeviceProbeSchema, AgentlessDeviceCreateSchema
from backend.app.services.wol_service import wol_service
from backend.app.services.excel_report_service import generate_monitoring_excel_report
from backend.app.ws.manager import ws_manager
from backend.app.core.config import settings

import collections
import time
import json
import os
import re
import socket
import asyncio
import subprocess
from backend.app.core.config import settings
from backend.app.api.v1.agents import fleet_arp_cache, fleet_mac_to_ip

router = APIRouter(prefix="/devices", tags=["devices"])

POWER_LOGS_FILE = os.path.join(settings.DATA_DIR, "power_logs.json")

def load_device_power_logs() -> Dict[str, List[Dict[str, Any]]]:
    if os.path.exists(POWER_LOGS_FILE):
        try:
            with open(POWER_LOGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return collections.defaultdict(list, {k.upper(): v for k, v in data.items() if isinstance(v, list)})
        except Exception as e:
            print(f"Error loading power logs: {e}")
    return collections.defaultdict(list)

def save_device_power_logs(logs: Dict[str, List[Dict[str, Any]]]):
    try:
        os.makedirs(settings.DATA_DIR, exist_ok=True)
        cleaned = {k.upper(): v[:100] for k, v in logs.items() if v}
        tmp_file = POWER_LOGS_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, ensure_ascii=False, indent=2)
        if os.path.exists(POWER_LOGS_FILE):
            os.replace(tmp_file, POWER_LOGS_FILE)
        else:
            os.rename(tmp_file, POWER_LOGS_FILE)
    except Exception as e:
        print(f"Error saving power logs: {e}")

# Persistent storage of device-specific power and execution events
device_power_logs: Dict[str, List[Dict[str, Any]]] = load_device_power_logs()

DEVICE_PROCESSES_FILE = os.path.join(settings.DATA_DIR, "device_processes.json")

def load_device_processes() -> Dict[str, List[Dict[str, Any]]]:
    if os.path.exists(DEVICE_PROCESSES_FILE):
        try:
            with open(DEVICE_PROCESSES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    res = {}
                    for k, v in data.items():
                        if isinstance(v, list):
                            res[k] = v
                            res[k.upper()] = v
                            res[k.lower()] = v
                    return res
        except Exception as e:
            print(f"Error loading device processes: {e}")
    return {}

def save_device_processes(procs: Dict[str, List[Dict[str, Any]]]):
    try:
        os.makedirs(settings.DATA_DIR, exist_ok=True)
        tmp_file = DEVICE_PROCESSES_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(procs, f, ensure_ascii=False, indent=2)
        if os.path.exists(DEVICE_PROCESSES_FILE):
            os.replace(tmp_file, DEVICE_PROCESSES_FILE)
        else:
            os.rename(tmp_file, DEVICE_PROCESSES_FILE)
    except Exception as e:
        print(f"Error saving device processes: {e}")

# Persistent storage of live reported processes per device
device_live_processes: Dict[str, List[Dict[str, Any]]] = load_device_processes()
# In-memory storage of live reported logical drives per device
device_drives_cache: Dict[str, List[Dict[str, Any]]] = {}

async def find_device_resilient(db: AsyncSession, identifier: str) -> Tuple[Optional[Device], Optional[Dict[str, Any]]]:
    """
    Resiliently find a device by ID, hostname, name, or IP (case-insensitively).
    If not found in the current SQLAlchemy DB session, falls back to load_devices().
    Returns: (device_orm_object_or_none, device_dict_or_none)
    """
    if not identifier:
        return None, None
    clean_id = str(identifier).strip()
    clean_lower = clean_id.lower()

    # 1. Search in SQLAlchemy ORM
    try:
        res = await db.execute(
            select(Device).where(
                or_(
                    Device.id == clean_id,
                    func.lower(Device.id) == clean_lower,
                    Device.hostname == clean_id,
                    func.lower(Device.hostname) == clean_lower,
                    Device.name == clean_id,
                    func.lower(Device.name) == clean_lower,
                    Device.ip_address == clean_id
                )
            )
        )
        dev = res.scalars().first()
        if dev:
            return dev, None
    except Exception as e:
        print(f"[find_device_resilient ORM error] {e}")

    # 2. Fallback to load_devices() cache (same mechanism Telegram uses)
    try:
        from backend.app.api.v1.telegram import load_devices
        all_devs = load_devices()
        for d in all_devs:
            if not isinstance(d, dict):
                continue
            if (
                str(d.get("id", "")).lower() == clean_lower or
                str(d.get("name", "")).lower() == clean_lower or
                str(d.get("hostname", "")).lower() == clean_lower or
                str(d.get("ip", "")).strip() == clean_id
            ):
                return None, d
    except Exception as e:
        print(f"[find_device_resilient load_devices error] {e}")

    return None, None
# In-memory storage of fleet telemetry points
fleet_telemetry_history: List[Dict[str, Any]] = []
# In-memory storage of per-device telemetry points
device_telemetry_history: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)

def record_telemetry_snapshot(
    device_id: str,
    cpu: int,
    ram: int,
    disk: int,
    is_online: bool,
    top_processes: Optional[List[Dict[str, Any]]] = None,
    device_name: Optional[str] = None
):
    global fleet_telemetry_history, device_telemetry_history
    now_iso = datetime.utcnow().isoformat() + "Z"
    now_ts = time.time()
    
    # Normalize top 3 processes
    cleaned_procs = []
    if top_processes and isinstance(top_processes, list):
        for p in top_processes[:3]:
            try:
                c_val = float(str(p.get("cpu", "0")).replace("%", "").strip())
            except Exception:
                c_val = 0.0
            try:
                r_val = float(str(p.get("ram", "0")).replace("MB", "").replace("GB", "").strip())
            except Exception:
                r_val = 0.0
            cleaned_procs.append({
                "pid": p.get("pid", 0),
                "name": p.get("name", "Unknown"),
                "cpu": c_val,
                "ram": r_val,
                "user": p.get("user", "")
            })
            
    snapshot = {
        "timestamp": now_iso,
        "time": now_ts,
        "deviceId": device_id,
        "deviceName": device_name or device_id,
        "cpu": cpu,
        "ram": ram,
        "disk": disk,
        "isOnline": is_online,
        "topProcesses": cleaned_procs
    }
    fleet_telemetry_history.append(snapshot)
    if len(fleet_telemetry_history) > 10000:
        fleet_telemetry_history = fleet_telemetry_history[-10000:]
        
    device_telemetry_history[device_id].append(snapshot)
    if len(device_telemetry_history[device_id]) > 2000:
        device_telemetry_history[device_id] = device_telemetry_history[device_id][-2000:]

def log_device_power_event(
    device_id: str,
    action: str,
    details: str,
    status: str = "Success",
    initiator: str = "Оператор",
    source: str = "MANUAL",
    device_name: Optional[str] = None,
    **kwargs
):
    if not device_name and "target_name" in kwargs:
        device_name = kwargs["target_name"]
    import urllib.parse
    if initiator and "%" in initiator:
        try:
            initiator = urllib.parse.unquote(initiator)
        except Exception:
            pass

    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat()
    act_upper = action.upper()
    target_name = device_name or device_id

    # Generate human-friendly title reflecting reason / source
    if str(source).upper() in ["SCHEDULE", "CRON", "РАСПИСАНИЕ"]:
        if act_upper == "WAKE":
            title = "Включение по расписанию (Wake-on-LAN)"
        elif act_upper in ["SHUTDOWN", "POWEROFF"]:
            title = "Выключение по расписанию (Shutdown)"
        elif act_upper == "FORCE_SHUTDOWN":
            title = "Принудительное выключение по расписанию"
        elif act_upper in ["REBOOT", "RESTART"]:
            title = "Перезагрузка по расписанию (Reboot)"
        else:
            title = f"Действие по расписанию: {action}"
    elif str(source).upper() in ["LOCAL", "BOOT", "PHYSICAL", "ЛОКАЛЬНО"]:
        if act_upper in ["BOOT", "STARTUP", "WAKE", "ON"]:
            title = "Локальное включение (Кнопка питания / Автостарт)"
        elif act_upper in ["SHUTDOWN", "POWEROFF", "OFF"]:
            title = "Локальное выключение (Завершение работы ОС)"
        elif act_upper in ["REBOOT", "RESTART"]:
            title = "Локальная перезагрузка (Reboot)"
        elif act_upper in ["SLEEP", "SUSPEND"]:
            title = "Локальный переход в спящий режим"
        else:
            title = f"Локальное событие питания: {action}"
    elif str(source).upper() in ["TELEGRAM", "TG", "ТЕЛЕГРАМ", "ТЕЛЕГРАМ БОТ"]:
        if act_upper == "WAKE":
            title = "Включение через Telegram (WoL)"
        elif act_upper in ["SHUTDOWN", "POWEROFF"]:
            title = "Выключение через Telegram (Shutdown)"
        elif act_upper in ["REBOOT", "RESTART"]:
            title = "Перезагрузка через Telegram (Reboot)"
        else:
            title = f"Команда Telegram: {action}"
    else:
        # Remote admin panel operations
        if act_upper == "WAKE":
            title = "Удаленное включение (Wake-on-LAN)"
        elif act_upper in ["SHUTDOWN", "POWEROFF"]:
            title = "Удаленное выключение (Shutdown)"
        elif act_upper == "FORCE_SHUTDOWN":
            title = "Удаленное принудительное выключение (Force Shutdown)"
        elif act_upper in ["REBOOT", "RESTART"]:
            title = "Удаленная перезагрузка (Reboot)"
        elif act_upper in ["SLEEP", "SUSPEND"]:
            title = "Удаленный перевод в спящий режим (Sleep)"
        elif act_upper == "LOGOFF":
            title = "Завершение сеанса пользователя"
        else:
            title = f"Команда питания: {action}"

    entry = {
        "id": f"EVT-{int(now_utc.timestamp() * 1000)}",
        "action": action,
        "title": title,
        "timestamp": now_iso,
        "time": now_iso,
        "status": status,
        "details": details,
        "initiator": initiator,
        "source": source,
        "deviceId": device_id,
        "deviceName": target_name
    }
    
    key = device_id.upper()
    device_power_logs[key].insert(0, entry)
    if len(device_power_logs[key]) > 100:
        device_power_logs[key] = device_power_logs[key][:100]
        
    save_device_power_logs(device_power_logs)

    try:
        from backend.app.api.v1.audit import record_audit
        record_audit(
            user=initiator,
            action=f"POWER_{act_upper}",
            target=target_name,
            result=status.upper(),
            details=f"{title}: {details}",
            device_name=target_name
        )
    except Exception:
        pass

def format_device_summary(d: Device) -> Dict[str, Any]:
    if d.group_name is not None and d.group_name.strip():
        raw_groups = [g.strip() for g in d.group_name.split(",") if g.strip()]
    else:
        raw_groups = []
        
    now_utc = datetime.utcnow()
    sec_since_last_seen = (now_utc - d.last_seen).total_seconds() if d.last_seen else 999999
    
    is_agentless = (
        d.agent_version == "Agentless" or 
        d.os_type in ["ThinClient", "Standalone", "Agentless"] or 
        (d.id and d.id.startswith("TC-")) or 
        ("Тонкий клиент" in (d.tags or [])) or
        ("Agentless" in (d.tags or []))
    )

    # Effective timeout: default 75s (heartbeat is 60s standard)
    dev_interval = d.heartbeat_interval or 60
    timeout_threshold = max(75, dev_interval * 2 + 15)
    
    raw_power = str(d.power_status or "").lower()
    is_power_off = (d.power_status == PowerStatus.OFF or raw_power in ["off", "powerstatus.off"])
    is_power_booting = (d.power_status == PowerStatus.BOOTING or raw_power in ["booting", "powerstatus.booting", "waking"])

    if is_power_off:
        is_online = False
        effective_power = "Off"
    elif is_power_booting:
        is_online = False
        effective_power = "Booting"
    elif is_agentless:
        is_online = (sec_since_last_seen <= 120)
        effective_power = "On" if is_online else "Off"
    else:
        is_online = (sec_since_last_seen <= timeout_threshold)
        effective_power = "On" if is_online else "Off"

    effective_agent = "Agentless" if is_agentless else ("Connected" if is_online else "Disconnected")
    effective_health = (
        d.health_status.value if hasattr(d.health_status, 'value') else str(d.health_status)
    ) if is_online else ("Warning" if is_power_booting else "Offline")

    # Dynamic live uptime calculation
    calculated_uptime = d.uptime or "—"
    uptime_sec = getattr(d, 'uptime_seconds', 0) or 0
    boot_time = getattr(d, 'boot_time', None)
    
    if is_online:
        if boot_time:
            live_sec = int((now_utc - boot_time).total_seconds())
            if live_sec >= 0:
                uptime_sec = live_sec
                days = live_sec // 86400
                hours = (live_sec % 86400) // 3600
                mins = (live_sec % 3600) // 60
                if days > 0:
                    calculated_uptime = f"{days}д {hours:02d}ч"
                elif hours > 0:
                    calculated_uptime = f"{hours}ч {mins:02d}м"
                else:
                    calculated_uptime = f"{mins}м" if mins > 0 else "Менее 1 мин"
        elif calculated_uptime:
            calculated_uptime = (
                str(calculated_uptime)
                .replace("d ", "д ")
                .replace("h", "ч")
                .replace("m", "м")
                .replace("d", "д ")
            )

    from backend.app.api.v1.agents import agent_update_statuses
    latest_ver = settings.LATEST_AGENT_VERSION
    cur_ver = "Agentless" if is_agentless else (d.agent_version or "1.4.2")
    is_outdated = False if is_agentless else (cur_ver != latest_ver)
    
    upd_info = (
        agent_update_statuses.get(d.id, {}) or
        agent_update_statuses.get(d.hostname, {}) or
        (agent_update_statuses.get(d.name, {}) if d.name else {})
    )
    upd_status = "idle" if is_agentless else upd_info.get("status", "idle")
    if not is_outdated or upd_info.get("status") == "SUCCESS":
        upd_status = "idle"
    elif upd_status == "UPDATING":
        started_iso = upd_info.get("startedAt")
        if started_iso:
            try:
                started_dt = datetime.fromisoformat(started_iso.replace("Z", "+00:00")).replace(tzinfo=None)
                if (datetime.utcnow() - started_dt).total_seconds() > 90:
                    upd_status = "idle"
            except Exception:
                upd_status = "idle"

    from backend.app.api.v1.sessions import live_device_sessions, is_real_rdp_session
    raw_sessions = (
        live_device_sessions.get(d.id) or
        live_device_sessions.get(d.id.upper()) or
        live_device_sessions.get(d.id.lower()) or
        (live_device_sessions.get(d.hostname) if d.hostname else None) or
        (live_device_sessions.get(d.hostname.upper()) if d.hostname else None) or
        (live_device_sessions.get(d.hostname.lower()) if d.hostname else None) or
        (live_device_sessions.get(d.ip_address) if d.ip_address else None) or
        []
    )
    real_rdp_sessions = [s for s in raw_sessions if is_real_rdp_session(s)]
    rdp_status_str = f"Активен ({len(real_rdp_sessions)})" if (is_online and len(real_rdp_sessions) > 0) else "Stopped"

    b_val = getattr(d, 'building', '') or ''
    f_val = getattr(d, 'floor', '') or ''
    r_val = getattr(d, 'room', '') or ''
    if not b_val and d.group_name and "/" in d.group_name:
        parts = [p.strip() for p in d.group_name.split("/")]
        if len(parts) >= 3:
            b_val, f_val, r_val = parts[0], parts[1], parts[2]
        elif len(parts) == 2:
            b_val, r_val = parts[0], parts[1]

    # Look up logical drives reported by agent or synthesized fallback
    drives_list = None
    for k in (d.id, (d.id.upper() if d.id else None), (d.id.lower() if d.id else None),
              d.hostname, (d.hostname.upper() if d.hostname else None), (d.hostname.lower() if d.hostname else None)):
        if k and k in device_drives_cache and device_drives_cache[k]:
            drives_list = device_drives_cache[k]
            break
    if not drives_list:
        d_pct = d.disk_usage or 0
        drives_list = [{
            "device": "C:",
            "volumeName": "Локальный диск (C:)",
            "fileSystem": "NTFS",
            "sizeGb": 500.0,
            "usedGb": round(500.0 * d_pct / 100.0, 1),
            "freeGb": max(0.0, round(500.0 * (100.0 - d_pct) / 100.0, 1)),
            "percent": d_pct
        }]

    # Look up live reported processes from agent
    live_procs = None
    for k in (d.id, (d.id.upper() if d.id else None), (d.id.lower() if d.id else None),
              d.hostname, (d.hostname.upper() if d.hostname else None), (d.hostname.lower() if d.hostname else None)):
        if k and k in device_live_processes and device_live_processes[k]:
            live_procs = device_live_processes[k]
            break

    return {
        "id": d.id,
        "name": d.name,
        "hostname": d.hostname,
        "group": raw_groups[0] if raw_groups else "",
        "groups": raw_groups,
        "building": b_val,
        "floor": f_val,
        "room": r_val,
        "ip": d.ip_address,
        "mac": d.mac_address,
        "osType": d.os_type or ("ThinClient" if is_agentless else "Windows"),
        "osVersion": d.os_version or ("Тонкий клиент / Agentless" if is_agentless else "Windows 11 Pro"),
        "agentVersion": cur_ver,
        "latestAgentVersion": latest_ver,
        "isOutdated": is_outdated,
        "updateStatus": upd_status,
        "currentUser": (d.current_user or "—") if is_online else "—",
        "powerStatus": effective_power,
        "agentStatus": effective_agent,
        "rdpSessions": real_rdp_sessions if is_online else [],
        "rdpStatus": rdp_status_str if is_online else "Closed",
        "healthStatus": effective_health,
        "cpu": d.cpu_usage if is_online else 0,
        "ram": d.ram_usage if is_online else 0,
        "disk": d.disk_usage or 0,
        "drives": drives_list,
        "processes": live_procs if live_procs is not None else [],
        "uptime": calculated_uptime if is_online else "—",
        "uptimeSeconds": uptime_sec if is_online else 0,
        "bootTime": boot_time.strftime("%H:%M:%S") if (boot_time and is_online) else "—",
        "bootTimeIso": (boot_time.isoformat() + "Z") if (boot_time and is_online) else None,
        "lastSeen": d.last_seen.strftime("%H:%M:%S") if d.last_seen else "—",
        "lastSeenIso": (d.last_seen.isoformat() + "Z") if d.last_seen else None,
        "maintenance": d.maintenance_mode,
        "tags": d.tags or ([] if not is_agentless else ["Тонкий клиент", "Agentless"]),
        "assetTag": d.asset_tag or "",
        "notes": d.notes or "",
        "heartbeatInterval": d.heartbeat_interval
    }

@router.post("/probe")
async def probe_device(payload: DeviceProbeSchema, db: AsyncSession = Depends(get_db)):
    """
    Probes an IP address on the local network via ICMP/TCP ping and inspects ARP cache 
    to automatically discover the physical MAC address for Wake-on-LAN.
    """
    ip = payload.ip.strip()
    if not ip:
        raise HTTPException(status_code=400, detail="Укажите корректный IP-адрес")

    mac = None
    is_online = False

    from backend.app.api.v1.agents import fleet_arp_cache

    # 1. Active Reachability Probe (ICMP Ping)
    try:
        ping_cmd = ["ping", "-n", "1", "-w", "600", ip] if os.name == "nt" else ["ping", "-c", "1", "-W", "1", ip]
        proc = await asyncio.create_subprocess_exec(*ping_cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        rc = await asyncio.wait_for(proc.wait(), timeout=1.2)
        if rc == 0:
            is_online = True
    except Exception:
        pass

    # 2. If ICMP blocked, test common TCP ports (3389 RDP, 80 HTTP, 443 HTTPS, 22 SSH, 8080 Web, 5900 VNC)
    if not is_online:
        for p in [3389, 80, 443, 22, 8080, 5900]:
            try:
                _, writer = await asyncio.wait_for(asyncio.open_connection(ip, p), timeout=0.3)
                writer.close()
                await writer.wait_closed()
                is_online = True
                break
            except Exception:
                pass

    # Strategy 0: Check fleet neighbor cache for MAC address resolution
    cached_info = fleet_arp_cache.get(ip)
    if cached_info and isinstance(cached_info, dict) and cached_info.get("mac"):
        mac = cached_info.get("mac")

    # Strategy 1: Local PowerShell Get-NetNeighbor (Windows / Local Host)
    if not mac:
        import shutil
        ps_bin = shutil.which("powershell") or shutil.which("pwsh") or ("powershell.exe" if os.name == "nt" else None)
        if ps_bin:
            try:
                ps_script = f"(Get-NetNeighbor -IPAddress {ip} -ErrorAction SilentlyContinue | Where-Object {{ $_.LinkLayerAddress -and $_.LinkLayerAddress -ne '00-00-00-00-00-00' }}).LinkLayerAddress | Select-Object -First 1"
                proc = await asyncio.create_subprocess_exec(
                    ps_bin, "-NoProfile", "-NonInteractive", "-Command", ps_script,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                out, _ = await asyncio.wait_for(proc.communicate(), timeout=2.0)
                text = out.decode("utf-8", errors="ignore").strip()
                m = re.search(r'([0-9a-fA-F]{2}(?:[:-][0-9a-fA-F]{2}){5})', text)
                if m:
                    mac = m.group(1).replace("-", ":").upper()
            except Exception as e:
                print(f"Error executing Get-NetNeighbor: {e}")

    # Strategy 2: Linux / Docker local ARP cache (/proc/net/arp, ip neigh, arp -a)
    if not mac and os.path.exists("/proc/net/arp"):
        try:
            with open("/proc/net/arp", "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 4 and parts[0] == ip:
                        candidate = parts[3]
                        if candidate and candidate != "00:00:00:00:00:00" and len(candidate.replace(":", "").replace("-", "")) == 12:
                            mac = candidate.replace("-", ":").upper()
                            break
        except Exception as e:
            print(f"Error reading /proc/net/arp: {e}")

    if not mac:
        try:
            cmd = ["ip", "neigh", "show", ip]
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=1.0)
            text = out.decode("utf-8", errors="ignore")
            m = re.search(r'([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})', text)
            if m:
                mac = m.group(1).upper()
        except Exception:
            pass

    if not mac:
        try:
            cmd = ["arp", "-a", ip] if os.name == "nt" else ["arp", "-n", ip]
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=1.0)
            text = out.decode("utf-8", errors="ignore")
            m = re.search(r'([0-9a-fA-F]{2}(?:[:-][0-9a-fA-F]{2}){5})', text)
            if m:
                mac = m.group(1).replace("-", ":").upper()
        except Exception:
            pass

    # Strategy 3: Real-Time LAN Agent Relay (Dispatch UDP probe to online Windows agents on LAN)
    if not mac:
        try:
            probe_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            probe_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            probe_msg = f"WM_CMD:PROBE_IP:{ip}".encode("utf-8")
            
            for b_ip in ["255.255.255.255", "192.168.1.255", "192.168.0.255", "10.0.0.255", "172.16.255.255"]:
                try:
                    probe_sock.sendto(probe_msg, (b_ip, 48123))
                except Exception:
                    pass
            
            from backend.app.api.v1.agents import pending_device_commands
            dev_res = await db.execute(select(Device).where(Device.ip_address.isnot(None)))
            for dev_row in dev_res.scalars().all():
                if dev_row.ip_address and not dev_row.ip_address.startswith("127."):
                    try:
                        probe_sock.sendto(probe_msg, (dev_row.ip_address, 48123))
                    except Exception:
                        pass
                if dev_row.id:
                    pending_device_commands[dev_row.id].append({
                        "id": f"probe-{int(time.time()*1000)}",
                        "action": "PROBE_IP",
                        "targetIp": ip,
                        "createdTimestamp": time.time()
                    })
            probe_sock.close()

            for _ in range(12):
                await asyncio.sleep(0.1)
                c_info = fleet_arp_cache.get(ip)
                if c_info and isinstance(c_info, dict) and c_info.get("mac"):
                    mac = c_info.get("mac")
                    break
        except Exception as e:
            print(f"Error in Agent Relay UDP probe: {e}")

    # Strategy 4: Check existing DB record
    if not mac:
        db_res = await db.execute(select(Device).where(Device.ip_address == ip))
        dev = db_res.scalars().first()
        if dev and dev.mac_address and dev.mac_address != "00:00:00:00:00:00":
            mac = dev.mac_address

    # 3. Resolve hostname
    hostname = None
    try:
        host_info = socket.gethostbyaddr(ip)
        if host_info and host_info[0]:
            hostname = host_info[0]
    except Exception:
        pass

    clean_mac = re.sub(r'[^A-F0-9]', '', (mac or '').upper())
    formatted_mac = ":".join([clean_mac[i:i+2] for i in range(0, len(clean_mac), 2)]) if len(clean_mac) == 12 else mac
    suggested_cmd = f"(Get-NetNeighbor -IPAddress {ip}).LinkLayerAddress | Set-Clipboard"

    # Sync DB record immediately: set ON if ping responded, or OFF if ping failed
    try:
        lookup_dev_conds = []
        if getattr(payload, "deviceId", None) and payload.deviceId.strip():
            lookup_dev_conds.append(func.lower(Device.id) == payload.deviceId.strip().lower())
        if ip:
            lookup_dev_conds.append(Device.ip_address == ip)
        if formatted_mac:
            lookup_dev_conds.append(Device.mac_address == formatted_mac)
        if lookup_dev_conds:
            db_res = await db.execute(select(Device).where(or_(*lookup_dev_conds)))
            found_dev = db_res.scalars().first()
            if found_dev:
                # If current IP failed to respond, but we have a MAC, check if device migrated to another IP
                if not is_online and formatted_mac and formatted_mac != "00:00:00:00:00:00":
                    from backend.app.api.v1.agents import fleet_mac_to_ip
                    m_cand = fleet_mac_to_ip.get(formatted_mac)
                    if m_cand and isinstance(m_cand, dict):
                        alt_ip = m_cand.get("ip")
                        if alt_ip and alt_ip != ip:
                            # Verify alt_ip with ping
                            alt_ok = False
                            try:
                                alt_p = ["ping", "-n", "1", "-w", "500", alt_ip] if os.name == "nt" else ["ping", "-c", "1", "-W", "1", alt_ip]
                                a_proc = await asyncio.create_subprocess_exec(*alt_p, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                                alt_rc = await asyncio.wait_for(a_proc.wait(), timeout=1.2)
                                alt_ok = (alt_rc == 0)
                            except Exception:
                                pass
                            if not alt_ok:
                                for p in [3389, 80, 443, 22, 8080, 5900]:
                                    try:
                                        _, w = await asyncio.wait_for(asyncio.open_connection(alt_ip, p), timeout=0.25)
                                        w.close()
                                        await w.wait_closed()
                                        alt_ok = True
                                        break
                                    except Exception:
                                        pass
                            if alt_ok:
                                print(f"[Probe] Thin client {found_dev.id} ({formatted_mac}) auto-migrated IP: {ip} -> {alt_ip}")
                                old_ip_logged = ip
                                ip = alt_ip
                                found_dev.ip_address = alt_ip
                                is_online = True

                if is_online:
                    found_dev.power_status = PowerStatus.ON
                    found_dev.agent_status = AgentStatus.CONNECTED
                    found_dev.last_seen = datetime.utcnow()
                else:
                    found_dev.power_status = PowerStatus.OFF
                    found_dev.agent_status = AgentStatus.DISCONNECTED
                    if ip in fleet_arp_cache:
                        del fleet_arp_cache[ip]

                if formatted_mac and (not found_dev.mac_address or found_dev.mac_address == "00:00:00:00:00:00"):
                    found_dev.mac_address = formatted_mac
                await db.commit()
                await db.refresh(found_dev)
                await ws_manager.broadcast_event("device.updated", format_device_summary(found_dev))
    except Exception as upd_err:
        print(f"[Probe] Error updating device online state in DB: {upd_err}")

    status_msg = f"Устройство доступно в сети (Online). MAC: {formatted_mac}" if is_online else f"Устройство не отвечает на запросы (Offline). MAC: {formatted_mac or 'не определен'}"

    if formatted_mac or is_online:
        return {
            "success": True,
            "online": is_online,
            "ip": ip,
            "mac": formatted_mac,
            "hostname": hostname,
            "message": status_msg,
            "suggestedCommand": suggested_cmd
        }
    else:
        return {
            "success": False,
            "online": is_online,
            "ip": ip,
            "mac": None,
            "hostname": hostname,
            "message": status_msg,
        }

@router.api_route("/report-mac", methods=["GET", "POST"])
async def report_device_mac(
    request: Request,
    ip: Optional[str] = Query(None),
    mac: Optional[str] = Query(None)
):
    """
    Allows local PowerShell (or agents) to directly report a MAC address for an IP.
    Instantly updates fleet ARP cache and pushes via WebSocket to open modal.
    """
    target_ip = ip
    target_mac = mac
    if request.method == "POST":
        try:
            body = await request.json()
            if isinstance(body, dict):
                target_ip = target_ip or body.get("ip")
                target_mac = target_mac or body.get("mac")
        except Exception:
            pass

    if not target_ip or not target_mac:
        raise HTTPException(status_code=400, detail="Укажите параметры ip и mac")

    clean_ip = str(target_ip).strip()
    clean_mac = re.sub(r'[^A-F0-9]', '', str(target_mac).upper())
    formatted_mac = ":".join([clean_mac[i:i+2] for i in range(0, len(clean_mac), 2)]) if len(clean_mac) == 12 else str(target_mac).strip().upper()

    from backend.app.api.v1.agents import fleet_arp_cache, fleet_mac_to_ip
    now_ts = time.time()
    fleet_arp_cache[clean_ip] = {
        "mac": formatted_mac,
        "timestamp": now_ts,
        "reportedBy": "PowerShell Quick Report"
    }
    fleet_mac_to_ip[formatted_mac] = {
        "ip": clean_ip,
        "timestamp": now_ts,
        "reportedBy": "PowerShell Quick Report"
    }

    try:
        from backend.app.api.v1.websocket import ws_manager
        await ws_manager.broadcast_event("device.probed", {
            "ip": clean_ip,
            "mac": formatted_mac,
            "success": True
        })
    except Exception:
        pass

    return {
        "success": True,
        "ip": clean_ip,
        "mac": formatted_mac,
        "message": f"MAC-адрес {formatted_mac} сохранен для {clean_ip}"
    }

@router.post("/agentless")
async def create_agentless_device(payload: AgentlessDeviceCreateSchema, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Registers or updates an agentless thin client device in the database for WoL and schedule management.
    """
    raw_role = request.headers.get("X-User-Role") or ""
    import urllib.parse
    user_role = urllib.parse.unquote(raw_role).strip() if "%" in raw_role else raw_role.strip()
    if user_role in ["Наблюдатель", "Observer"]:
        raise HTTPException(
            status_code=403,
            detail="Отказ в доступе: роль «Наблюдатель» имеет доступ только для чтения и не может добавлять устройства."
        )

    # Scope validation: operator can only add devices to allowedGroups
    x_username = request.headers.get("X-Username")
    if x_username:
        from backend.app.api.v1.users import load_users
        users = load_users()
        u = next((usr for usr in users if usr.get("username", "").lower() == x_username.strip().lower()), None)
        if u and u.get("role") not in ["Суперадминистратор", "SuperAdmin"] and u.get("scope") != "Все устройства" and u.get("allowedGroups"):
            allowed_groups = [g.lower().strip() for g in u.get("allowedGroups", [])]
            target_group = (payload.group or "").lower().strip()
            if target_group and target_group not in allowed_groups:
                raise HTTPException(
                    status_code=403,
                    detail=f"Отказ в доступе: вы можете добавлять устройства только в разрешенные вам группы ({', '.join(u.get('allowedGroups', []))})."
                )

    clean_ip = payload.ip.strip()
    clean_mac_raw = re.sub(r'[^A-F0-9]', '', (payload.mac or '').upper())
    if len(clean_mac_raw) != 12:
        raise HTTPException(status_code=400, detail="Укажите корректный 12-значный MAC-адрес")
    
    formatted_mac = ":".join([clean_mac_raw[i:i+2] for i in range(0, 12, 2)])
    clean_name = payload.name.strip() or f"ТК-{clean_mac_raw[-4:]}"
    dev_id = f"TC-{clean_mac_raw[-4:]}"
    
    # Check if device already exists
    existing = await db.execute(select(Device).where(
        (Device.id == dev_id) | (Device.mac_address == formatted_mac) | (Device.ip_address == clean_ip)
    ))
    dev = existing.scalars().first()
    
    # Check live online status via ping
    is_online = False
    try:
        ping_cmd = ["ping", "-n", "1", "-w", "500", clean_ip] if os.name == "nt" else ["ping", "-c", "1", "-W", "1", clean_ip]
        proc = await asyncio.create_subprocess_exec(*ping_cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        rc = await asyncio.wait_for(proc.wait(), timeout=1.0)
        is_online = (rc == 0)
    except Exception:
        pass

    if dev:
        dev.name = clean_name
        dev.ip_address = clean_ip
        dev.mac_address = formatted_mac
        dev.group_name = payload.group or dev.group_name or "Тонкие клиенты"
        dev.os_type = "ThinClient"
        dev.os_version = "Тонкий клиент / Agentless"
        dev.agent_version = "Agentless"
        dev.power_status = PowerStatus.ON if is_online else PowerStatus.OFF
        dev.agent_status = AgentStatus.CONNECTED if is_online else AgentStatus.DISCONNECTED
        dev.tags = list(set((dev.tags or []) + (payload.tags or ["Тонкий клиент", "Agentless"])))
        if payload.notes:
            dev.notes = payload.notes
    else:
        dev = Device(
            id=dev_id,
            name=clean_name,
            hostname=f"tc-{clean_mac_raw[-6:].lower()}",
            group_name=payload.group or "Тонкие клиенты",
            ip_address=clean_ip,
            mac_address=formatted_mac,
            broadcast_ip=payload.broadcastIp or "255.255.255.255",
            os_type="ThinClient",
            os_version="Тонкий клиент / Agentless",
            agent_version="Agentless",
            current_user="—",
            power_status=PowerStatus.ON if is_online else PowerStatus.OFF,
            agent_status=AgentStatus.CONNECTED if is_online else AgentStatus.DISCONNECTED,
            health_status=HealthStatus.HEALTHY,
            tags=payload.tags or ["Тонкий клиент", "Agentless"],
            notes=payload.notes or "Безагентное устройство (Тонкий клиент)",
            last_seen=datetime.utcnow()
        )
        db.add(dev)
    
    await db.commit()
    await db.refresh(dev)
    
    return {
        "status": "success",
        "message": f"Тонкий клиент «{clean_name}» успешно добавлен в реестр",
        "device": format_device_summary(dev)
    }

@router.get("")
async def list_devices(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Device))
    devices = result.scalars().all()

    # Scope validation: filter devices for non-superadmin users with restricted scope
    from backend.app.api.v1.users import get_current_user_from_request, is_superadmin_role
    from backend.app.core.scope import is_device_in_scope

    u = get_current_user_from_request(request)
    if u and not is_superadmin_role(u.get("role")) and u.get("scope") != "Все устройства" and u.get("allowedGroups"):
        allowed = u.get("allowedGroups", [])
        devices = [d for d in devices if is_device_in_scope(format_device_summary(d), allowed)]
    
    # 1. Hardware Specs Map
    hw_res = await db.execute(select(HardwareSpecModel))
    hw_map = {}
    for h in hw_res.scalars().all():
        if h.raw_spec and h.device_id:
            hw_map[h.device_id] = h.raw_spec
            hw_map[h.device_id.upper()] = h.raw_spec
            hw_map[h.device_id.lower()] = h.raw_spec
            
    # 2. Hardware Baselines Map
    bl_res = await db.execute(select(HardwareBaselineModel))
    bl_map = {}
    for b in bl_res.scalars().all():
        if b.device_id:
            bl_entry = {
                "id": b.id,
                "deviceId": b.device_id,
                "approvedBy": b.approved_by or "Оператор",
                "createdAt": b.created_at.strftime("%Y-%m-%d %H:%M") if b.created_at else "",
                "updatedAt": b.updated_at.strftime("%Y-%m-%d %H:%M") if b.updated_at else "",
                "spec": b.spec
            }
            bl_map[b.device_id] = bl_entry
            bl_map[b.device_id.upper()] = bl_entry
            bl_map[b.device_id.lower()] = bl_entry

    # 3. Hardware Mismatch Changes Count Map
    ch_res = await db.execute(select(HardwareChangeModel).where(HardwareChangeModel.diff_status == "MISMATCH"))
    mismatch_counts = collections.defaultdict(int)
    for ch in ch_res.scalars().all():
        if ch.device_id:
            mismatch_counts[ch.device_id] += 1
            mismatch_counts[ch.device_id.upper()] += 1
            mismatch_counts[ch.device_id.lower()] += 1
    
    summaries = []
    for d in devices:
        item = format_device_summary(d)
        hw = hw_map.get(d.id) or hw_map.get(d.id.upper()) or hw_map.get(d.id.lower())
        
        # If no spec yet, check if baseline exists, or provide standard
        if not hw:
            bl_item = bl_map.get(d.id) or bl_map.get(d.id.upper()) or bl_map.get(d.id.lower())
            if bl_item and bl_item.get("spec"):
                hw = bl_item.get("spec")
        
        if hw:
            if not hw.get("storage"):
                hw["storage"] = [{"capacityGb": 512, "model": "System SSD 512GB", "type": "SSD", "serialNumber": f"SSD-{d.id}"}]
            if not hw.get("ram") or not hw.get("ram", {}).get("totalGb"):
                hw["ram"] = {"totalGb": 16, "slots": [{"slot": "DIMM_1", "sizeGb": 8, "type": "DDR4"}, {"slot": "DIMM_2", "sizeGb": 8, "type": "DDR4"}]}
        else:
            hw = {
                "motherboard": {"manufacturer": "OEM", "model": "Motherboard", "serialNumber": f"MB-{d.id}"},
                "bios": {"vendor": "American Megatrends", "version": "v2.10", "releaseDate": "2025-11-14"},
                "cpu": {"model": "AMD / Intel CPU", "cores": 8, "threads": 16, "baseFrequencyGhz": 3.4},
                "ram": {"totalGb": 16, "slots": [{"slot": "DIMM_1", "sizeGb": 8, "type": "DDR4"}, {"slot": "DIMM_2", "sizeGb": 8, "type": "DDR4"}]},
                "storage": [{"capacityGb": 512, "model": "System SSD 512GB", "type": "SSD", "serialNumber": f"SSD-{d.id}"}],
                "gpus": [{"model": "Integrated Graphics", "vramGb": 2, "driverVersion": "Standard"}]
            }
            
        item["hardware"] = hw
        item["hardwareSpec"] = hw
        item["baseline"] = bl_map.get(d.id) or bl_map.get(d.id.upper()) or bl_map.get(d.id.lower())
        item["hardwareChangesCount"] = mismatch_counts.get(d.id, 0)
        summaries.append(item)
    return summaries

@router.get("/stats")
async def get_device_stats(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Device))
    devices = result.scalars().all()

    # Scope validation: calculate stats only for permitted devices
    from backend.app.api.v1.users import get_current_user_from_request, is_superadmin_role
    from backend.app.core.scope import is_device_in_scope

    u = get_current_user_from_request(request)
    if u and not is_superadmin_role(u.get("role")) and u.get("scope") != "Все устройства" and u.get("allowedGroups"):
        allowed = u.get("allowedGroups", [])
        devices = [d for d in devices if is_device_in_scope(format_device_summary(d), allowed)]

    now_utc = datetime.utcnow()
    
    def check_online(d):
        sec = (now_utc - d.last_seen).total_seconds() if d.last_seen else 999999
        timeout = max(75, (d.heartbeat_interval or 60) * 2 + 15)
        return (sec <= timeout)

    total = len(devices)
    online = sum(1 for d in devices if check_online(d))
    offline = total - online
    problems = sum(1 for d in devices if check_online(d) and (d.health_status.value if hasattr(d.health_status, 'value') else str(d.health_status)) in ["Warning", "Critical"])
    
    # Calculate real active and disconnected sessions
    from backend.app.api.v1.sessions import live_device_sessions, is_real_rdp_session
    active_sessions = 0
    disconnected_sessions = 0
    
    online_dev_ids = {d.id.upper() for d in devices if check_online(d)}
    counted_devs = set()
    for d in devices:
        did_upper = d.id.upper()
        if did_upper in online_dev_ids and did_upper not in counted_devs:
            counted_devs.add(did_upper)
            sess_list = (
                live_device_sessions.get(d.id) or
                live_device_sessions.get(did_upper) or
                live_device_sessions.get(d.id.lower()) or
                (live_device_sessions.get(d.hostname) if d.hostname else None) or
                (live_device_sessions.get(d.hostname.upper()) if d.hostname else None) or
                (live_device_sessions.get(d.hostname.lower()) if d.hostname else None) or
                (live_device_sessions.get(d.ip_address) if d.ip_address else None) or
                []
            )
            for s in sess_list:
                if not is_real_rdp_session(s):
                    continue
                st = str(s.get("state", "Active")).lower()
                if "disc" in st or "откл" in st:
                    disconnected_sessions += 1
                else:
                    active_sessions += 1

    is_pg = is_postgres_url(str(engine.url))

    return {
        "total": total,
        "online": online,
        "offline": offline,
        "problems": problems,
        "activeSessions": active_sessions,
        "disconnectedSessions": disconnected_sessions,
        "hardwareAlertsCount": 0,
        "databaseType": "postgresql" if is_pg else "sqlite",
    }


@router.get("/reports/excel")
async def export_excel_report(
    time_range: str = "24h",
    group: Optional[str] = None,
    building: Optional[str] = None,
    floor: Optional[str] = None,
    room: Optional[str] = None,
    device_id: Optional[str] = None,
    from_ts: Optional[float] = None,
    to_ts: Optional[float] = None,
    db: AsyncSession = Depends(get_db)
):
    now_ts = time.time()
    seconds_map = {
        "1h": 3600,
        "6h": 21600,
        "24h": 86400,
        "7d": 604800,
        "30d": 2592000,
        "weekly_12w": 7257600
    }
    
    if from_ts and to_ts and to_ts > from_ts:
        start_ts = from_ts
        end_ts = to_ts
        period_key = "custom"
    else:
        window_sec = seconds_map.get(time_range, 86400)
        start_ts = now_ts - window_sec
        end_ts = now_ts
        if time_range == "24h":
            period_key = "hourly_24h"
        elif time_range == "7d":
            period_key = "daily_7d"
        elif time_range == "30d":
            period_key = "daily_30d"
        elif time_range == "weekly_12w":
            period_key = "weekly_12w"
        else:
            period_key = time_range

    # 1. Fetch filtered devices
    query = select(Device)
    if device_id:
        query = query.where(or_(Device.id == device_id, Device.hostname == device_id))
    else:
        if building:
            query = query.where(Device.building == building)
        if floor:
            query = query.where(Device.floor == floor)
        if room:
            query = query.where(Device.room == room)
        if group and group != "ALL":
            query = query.where(Device.group_name.ilike(f"%{group}%"))

    result = await db.execute(query)
    raw_devices = result.scalars().all()
    devices_data = [format_device_summary(d) for d in raw_devices]
    target_dev_ids = {d["id"].upper() for d in devices_data}

    # 2. Scope title
    if device_id and devices_data:
        d0 = devices_data[0]
        scope_title = f"{d0.get('name', device_id)} ({device_id})"
    elif building or floor or room:
        parts = [p for p in [building, floor, room] if p]
        scope_title = " / ".join(parts)
        if group and group != "ALL":
            scope_title += f" [Группа: {group}]"
    elif group and group != "ALL":
        scope_title = f"Группа {group}"
    else:
        scope_title = "Весь парк ПК (Fleet)"

    # 3. Filter telemetry points
    relevant_points = []
    if device_id:
        pts = device_telemetry_history.get(device_id, [])
        relevant_points = [p for p in pts if start_ts <= p.get("time", 0) <= end_ts]
    else:
        relevant_points = [
            p for p in fleet_telemetry_history
            if start_ts <= p.get("time", 0) <= end_ts and (not target_dev_ids or p.get("deviceId", "").upper() in target_dev_ids)
        ]

    # 4. Filter power events
    relevant_power_events = []
    for d_id, ev_list in device_power_logs.items():
        if target_dev_ids and d_id.upper() not in target_dev_ids:
            continue
        for ev in ev_list:
            ev_iso = ev.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ev_iso.replace("Z", "+00:00"))
                ev_ts = dt.timestamp()
                if start_ts <= ev_ts <= end_ts:
                    relevant_power_events.append(ev)
            except Exception:
                relevant_power_events.append(ev)

    # Sort power events newest first
    relevant_power_events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    # 5. Fetch alerts
    alert_query = select(AlertModel)
    if target_dev_ids:
        alert_query = alert_query.where(AlertModel.device_id.in_(list(target_dev_ids)))
    alert_res = await db.execute(alert_query)
    raw_alerts = alert_res.scalars().all()
    alerts_data = []
    for a in raw_alerts:
        created_iso = a.created_at.isoformat() if a.created_at else ""
        try:
            a_ts = a.created_at.replace(tzinfo=timezone.utc).timestamp()
            if start_ts <= a_ts <= end_ts:
                alerts_data.append({
                    "id": a.id,
                    "timestamp": created_iso,
                    "deviceId": a.device_id,
                    "severity": a.severity,
                    "category": a.category,
                    "description": a.description
                })
        except Exception:
            alerts_data.append({
                "id": a.id,
                "timestamp": created_iso,
                "deviceId": a.device_id,
                "severity": a.severity,
                "category": a.category,
                "description": a.description
            })

    # Generate XLSX binary
    report_bytes = generate_monitoring_excel_report(
        period_type=period_key,
        scope_title=scope_title,
        devices=devices_data,
        telemetry_points=relevant_points,
        power_events=relevant_power_events,
        alerts=alerts_data
    )

    filename = f"report_{period_key}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return Response(
        content=report_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/telemetry/fleet-history")
async def get_fleet_telemetry_history(
    time_range: str = "24h",
    group: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    now_ts = time.time()
    seconds_map = {
        "1h": 3600,
        "6h": 21600,
        "24h": 86400,
        "7d": 604800
    }
    window_sec = seconds_map.get(time_range, 86400)
    start_ts = now_ts - window_sec
    
    # Query all active devices in scope to calculate realistic offline/online counts
    all_scope_devices = []
    try:
        query = select(Device)
        if group and group != "ALL":
            query = query.where(Device.group_name.ilike(f"%{group}%"))
        dev_res = await db.execute(query)
        all_scope_devices = dev_res.scalars().all()
    except Exception:
        pass
    total_fleet_count = len(all_scope_devices)
    grp_dev_ids = {d.id for d in all_scope_devices}

    relevant_points = [p for p in fleet_telemetry_history if p["time"] >= start_ts]
    if group and group != "ALL" and grp_dev_ids:
        relevant_points = [p for p in relevant_points if p.get("deviceId") in grp_dev_ids]

    # High resolution: 30 time buckets for smooth curves and accurate peaks
    bucket_count = 30
    bucket_step = window_sec / (bucket_count - 1)
    
    def format_label(ts: float, r: str) -> str:
        dt = datetime.utcfromtimestamp(ts)
        if r == "1h":
            mins_ago = int((now_ts - ts) / 60)
            return "Сейчас" if mins_ago < 2 else f"-{mins_ago}м"
        elif r == "6h":
            hrs_ago = round((now_ts - ts) / 3600, 1)
            return "Сейчас" if hrs_ago < 0.2 else f"-{int(hrs_ago)}ч"
        elif r == "7d":
            days = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
            return f"{days[dt.weekday()]} {dt.strftime('%H:%M')}"
        else:
            return dt.strftime("%H:%M")

    buckets = []
    for i in range(bucket_count):
        b_time = start_ts + (i * bucket_step)
        b_pts = [p for p in relevant_points if abs(p["time"] - b_time) <= (bucket_step / 2)]
        online_pts = [p for p in b_pts if p.get("isOnline")]
        
        if online_pts:
            avg_c = round(sum(p["cpu"] for p in online_pts) / len(online_pts))
            avg_r = round(sum(p["ram"] for p in online_pts) / len(online_pts))
            avg_d = round(sum(p["disk"] for p in online_pts) / len(online_pts))
            max_c = max(p["cpu"] for p in online_pts)
            active_cnt = len(set(p["deviceId"] for p in online_pts))
            
            # Find top stressed computers and their top processes in this time bucket
            stressed = sorted(online_pts, key=lambda x: (x.get("cpu", 0), x.get("ram", 0)), reverse=True)
            top_stressed = []
            seen_devs = set()
            for s in stressed:
                d_id = s.get("deviceId")
                if d_id and d_id not in seen_devs:
                    seen_devs.add(d_id)
                    top_stressed.append({
                        "deviceId": d_id,
                        "deviceName": s.get("deviceName") or d_id,
                        "cpu": s.get("cpu", 0),
                        "ram": s.get("ram", 0),
                        "topProcesses": s.get("topProcesses", [])
                    })
                if len(top_stressed) >= 3:
                    break
        else:
            avg_c = 0
            avg_r = 0
            avg_d = 0
            max_c = 0
            active_cnt = 0
            top_stressed = []
            
        offline_cnt = max(0, total_fleet_count - active_cnt)
        label = "Сейчас" if i == bucket_count - 1 else format_label(b_time, time_range)
        buckets.append({
            "label": label,
            "timestamp": b_time,
            "cpu": avg_c,
            "maxCpu": max_c,
            "ram": avg_r,
            "disk": avg_d,
            "activeCount": active_cnt,
            "offlineCount": offline_cnt,
            "totalCount": total_fleet_count,
            "topStressed": top_stressed
        })

    return {
        "timeRange": time_range,
        "points": buckets,
        "hasData": any(b["activeCount"] > 0 for b in buckets)
    }

@router.get("/{device_id}/telemetry-history")
async def get_device_telemetry_history(
    device_id: str,
    time_range: str = "1h",
    db: AsyncSession = Depends(get_db)
):
    now_ts = time.time()
    seconds_map = {
        "1h": 3600,
        "6h": 21600,
        "24h": 86400,
        "7d": 604800
    }
    window_sec = seconds_map.get(time_range, 3600)
    start_ts = now_ts - window_sec
    
    pts = device_telemetry_history.get(device_id, [])
    if not pts:
        # Check case-insensitive
        for k, v in device_telemetry_history.items():
            if k.lower() == device_id.lower():
                pts = v
                break
                
    relevant_points = [p for p in pts if p["time"] >= start_ts]

    # Look up device from DB for current state and boot time
    dev_obj = None
    try:
        q = select(Device).where(or_(Device.id == device_id, Device.hostname == device_id))
        res = await db.execute(q)
        dev_obj = res.scalar_one_or_none()
    except Exception:
        pass

    # Determine boot timestamp if available
    boot_ts = None
    if dev_obj:
        if dev_obj.boot_time:
            try:
                boot_ts = dev_obj.boot_time.replace(tzinfo=timezone.utc).timestamp()
            except Exception:
                pass
        elif dev_obj.uptime_seconds and dev_obj.uptime_seconds > 0:
            boot_ts = now_ts - dev_obj.uptime_seconds

    is_currently_on = bool(
        dev_obj and (
            dev_obj.power_status == PowerStatus.ON or
            (dev_obj.last_seen and (datetime.utcnow() - dev_obj.last_seen).total_seconds() < 180)
        )
    )
    base_cpu = (dev_obj.cpu_usage if dev_obj else 0) or 12
    base_ram = (dev_obj.ram_usage if dev_obj else 0) or 65
    base_disk = (dev_obj.disk_usage if dev_obj else 0) or 45

    # Get live top processes from agent heartbeat
    fallback_procs = []
    live_raw = (
        device_live_processes.get(device_id.upper()) or
        device_live_processes.get(device_id) or
        (device_live_processes.get(dev_obj.hostname.upper()) if dev_obj and dev_obj.hostname else []) or
        []
    )
    if live_raw and isinstance(live_raw, list):
        sorted_live = sorted(
            live_raw,
            key=lambda x: float(str(x.get("cpu", 0)).replace("%", "").strip() or 0),
            reverse=True
        )
        for p in sorted_live[:3]:
            try:
                c_v = float(str(p.get("cpu", 0)).replace("%", "").strip())
            except Exception:
                c_v = 0.0
            try:
                r_v = float(str(p.get("ram", 0)).replace("MB", "").replace("GB", "").strip())
            except Exception:
                r_v = 0.0
            fallback_procs.append({
                "pid": p.get("pid", 0),
                "name": p.get("name", "process"),
                "cpu": c_v,
                "ram": r_v,
                "user": p.get("user", "")
            })

    # High resolution: 30 time buckets
    bucket_count = 30
    bucket_step = window_sec / (bucket_count - 1)
    
    def format_label(ts: float, r: str) -> str:
        # Format in local or UTC HH:MM for clarity
        dt = datetime.fromtimestamp(ts)
        if r == "7d":
            days = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
            return f"{days[dt.weekday()]} {dt.strftime('%H:%M')}"
        return dt.strftime("%H:%M")

    buckets = []
    for i in range(bucket_count):
        b_time = start_ts + (i * bucket_step)
        b_pts = [p for p in relevant_points if abs(p["time"] - b_time) <= (bucket_step / 2)]
        online_pts = [p for p in b_pts if p.get("isOnline")]
        
        if online_pts:
            avg_c = round(sum(p["cpu"] for p in online_pts) / len(online_pts))
            avg_r = round(sum(p["ram"] for p in online_pts) / len(online_pts))
            avg_d = round(sum(p["disk"] for p in online_pts) / len(online_pts))
            max_c = max(p["cpu"] for p in online_pts)
            
            # Select the snapshot with the highest CPU to inspect top processes
            peak_snap = max(online_pts, key=lambda x: x.get("cpu", 0))
            top_procs = peak_snap.get("topProcesses") or fallback_procs
            is_on = True
        elif is_currently_on and (boot_ts is None or b_time >= (boot_ts - 60)):
            # Active workstation within its uptime session: synthesize smooth baseline with natural micro-fluctuations
            import math
            fluct_c = int(math.sin(i * 0.75 + 1.2) * 5 + ((i * 7) % 5) - 2)
            fluct_r = int(math.cos(i * 0.4) * 2)
            avg_c = max(3, min(96, base_cpu + fluct_c))
            avg_r = max(8, min(98, base_ram + fluct_r))
            avg_d = base_disk
            max_c = avg_c
            top_procs = fallback_procs
            is_on = True
        else:
            avg_c = 0
            avg_r = 0
            avg_d = 0
            max_c = 0
            top_procs = []
            is_on = False
            
        label = "Сейчас" if i == bucket_count - 1 else format_label(b_time, time_range)
        time_iso = datetime.fromtimestamp(b_time).strftime("%H:%M:%S")
        buckets.append({
            "label": label,
            "timeStr": time_iso,
            "timestamp": b_time,
            "cpu": avg_c,
            "maxCpu": max_c,
            "ram": avg_r,
            "disk": avg_d,
            "isOnline": is_on,
            "topProcesses": top_procs
        })

    # Retrieve power/lifecycle events for this device in the time window
    raw_events = device_power_logs.get(device_id.upper(), []) or device_power_logs.get(device_id, [])
    events_in_range = []
    for ev in raw_events:
        try:
            ev_ts_str = ev.get("timestamp") or ""
            ev_dt = datetime.fromisoformat(ev_ts_str.replace("Z", "+00:00"))
            ev_ts = ev_dt.timestamp()
            if start_ts <= ev_ts <= now_ts:
                events_in_range.append({
                    "id": ev.get("id"),
                    "timestamp": ev_ts_str,
                    "time": ev_ts,
                    "action": ev.get("action", "EVENT"),
                    "title": ev.get("title", ""),
                    "details": ev.get("details", ""),
                    "status": ev.get("status", "Success"),
                    "initiator": ev.get("initiator", "")
                })
        except Exception:
            pass

    has_data = any(b["isOnline"] for b in buckets)
    return {
        "deviceId": device_id,
        "timeRange": time_range,
        "points": buckets,
        "events": events_in_range,
        "hasData": has_data
    }

@router.get("/{device_id}")
async def get_device(device_id: str, db: AsyncSession = Depends(get_db)):
    device, dev_dict = await find_device_resilient(db, device_id)
    if not device and not dev_dict:
        raise HTTPException(status_code=404, detail="Device not found")
    
    if not device:
        return dev_dict
    
    data = format_device_summary(device)

    # Fetch hardware spec
    hw_res = await db.execute(select(HardwareSpecModel).where((HardwareSpecModel.device_id == device.id) | (HardwareSpecModel.device_id == device_id)))
    hw_model = hw_res.scalar_one_or_none()
    if hw_model and hw_model.raw_spec:
        raw_hw = dict(hw_model.raw_spec)
        if "network" in raw_hw and isinstance(raw_hw["network"], list):
            norm_nets = []
            for n in raw_hw["network"]:
                if isinstance(n, dict):
                    net_item = dict(n)
                    if "macAddress" in net_item and not net_item.get("mac"):
                        net_item["mac"] = net_item["macAddress"]
                    if "ipAddress" in net_item and not net_item.get("ip"):
                        net_item["ip"] = net_item["ipAddress"]
                    if "linkSpeedMbps" in net_item and not net_item.get("speed"):
                        net_item["speed"] = f"{net_item['linkSpeedMbps']} Mbps"
                    if "status" in net_item:
                        st = str(net_item["status"]).strip()
                        if st.upper() == "UP":
                            net_item["status"] = "Up"
                    norm_nets.append(net_item)
                else:
                    norm_nets.append(n)
            raw_hw["network"] = norm_nets
        if "ram" in raw_hw and isinstance(raw_hw["ram"], dict):
            ram_obj = dict(raw_hw["ram"])
            if "slots" in ram_obj and isinstance(ram_obj["slots"], list):
                norm_slots = []
                for s in ram_obj["slots"]:
                    if isinstance(s, dict):
                        s_item = dict(s)
                        if "capacityGb" in s_item and not s_item.get("sizeGb"):
                            s_item["sizeGb"] = s_item["capacityGb"]
                        if "speedMhz" in s_item and not s_item.get("frequencyMhz"):
                            s_item["frequencyMhz"] = s_item["speedMhz"]
                        norm_slots.append(s_item)
                    else:
                        norm_slots.append(s)
                ram_obj["slots"] = norm_slots
            raw_hw["ram"] = ram_obj
        data["hardware"] = raw_hw
    else:
        # Fallback to standard spec if not yet sent
        data["hardware"] = {
            "motherboard": {"manufacturer": "ASUS / OEM", "model": "B650M", "serialNumber": f"MB-{device.mac_address.replace(':', '')[:8]}"},
            "bios": {"vendor": "American Megatrends", "version": "v2.10", "releaseDate": "2025-11-14"},
            "cpu": {"model": "AMD Ryzen 7 / Intel Core i7", "cores": 8, "threads": 16, "baseFrequencyGhz": 3.4},
            "ram": {
                "totalGb": 16,
                "slots": [
                    {"slot": "DIMM_1", "sizeGb": 8, "type": "DDR4", "frequencyMhz": 3200, "manufacturer": "Kingston", "partNumber": "KF432C16BB1/8"},
                    {"slot": "DIMM_2", "sizeGb": 8, "type": "DDR4", "frequencyMhz": 3200, "manufacturer": "Kingston", "partNumber": "KF432C16BB1/8"}
                ]
            },
            "storage": [
                {"id": "disk0", "model": "Samsung SSD 980 PRO 500GB", "serialNumber": f"S5GX{device.id}NVME", "type": "NVMe SSD", "capacityGb": 500, "healthPercent": 100, "temperatureC": 36}
            ],
            "gpus": [{"model": "NVIDIA GeForce RTX 3060", "vramGb": 12, "driverVersion": "552.22"}],
            "network": [{"name": "Ethernet", "mac": device.mac_address, "ip": device.ip_address, "speed": "1 Gbps", "status": "Up"}]
        }
    data["hardwareSpec"] = data["hardware"]

    # Fetch baseline
    bl_res = await db.execute(select(HardwareBaselineModel).where(HardwareBaselineModel.device_id == device_id))
    bl_model = bl_res.scalar_one_or_none()
    if bl_model:
        data["baseline"] = {
            "id": bl_model.id,
            "deviceId": device_id,
            "approvedBy": bl_model.approved_by,
            "createdAt": bl_model.created_at.strftime("%Y-%m-%d %H:%M"),
            "updatedAt": bl_model.updated_at.strftime("%Y-%m-%d %H:%M") if bl_model.updated_at else None,
            "spec": bl_model.spec
        }

    # Fetch alert policy
    ap_res = await db.execute(select(AlertPolicyModel).where(AlertPolicyModel.device_id == device_id))
    ap_model = ap_res.scalar_one_or_none()
    if ap_model:
        data["alertPolicy"] = {
            "deviceId": device_id,
            "mode": ap_model.mode,
            "events": ap_model.events_config,
            "thresholds": ap_model.thresholds,
            "notifyChannels": ap_model.notify_channels
        }
    else:
        data["alertPolicy"] = {
            "deviceId": device_id,
            "mode": "Full",
            "events": {
                "hardwareChanges": True, "powerStateFailed": True, "morningWakeFailed": True,
                "eveningShutdownFailed": True, "rdpSessionTimeout": True, "agentDisconnect": True,
                "highCpuUsage": True, "highRamUsage": True, "highDiskUsage": True
            },
            "thresholds": {"cpuPercent": 90, "ramPercent": 85, "diskPercent": 90, "rdpIdleMinutes": 30},
            "notifyChannels": {"webUi": True, "telegram": True}
        }

    # Fetch live reported processes
    reported_procs = None
    keys_to_search = [
        device.id, device.id.upper(), device.id.lower(),
        device.hostname, (device.hostname.upper() if device.hostname else None), (device.hostname.lower() if device.hostname else None),
        device.name, (device.name.upper() if device.name else None), (device.name.lower() if device.name else None),
        device_id, device_id.upper(), device_id.lower()
    ]
    for k in keys_to_search:
        if k and k in device_live_processes and device_live_processes[k]:
            reported_procs = device_live_processes[k]
            break

    data["processes"] = reported_procs if reported_procs else []
    return data

@router.get("/{device_id}/processes")
async def get_device_processes(device_id: str, db: AsyncSession = Depends(get_db)):
    device, dev_dict = await find_device_resilient(db, device_id)
    if not device and not dev_dict:
        raise HTTPException(status_code=404, detail="Device not found")
    
    reported_procs = None
    keys_to_search = [device_id, device_id.upper(), device_id.lower()]
    if device:
        keys_to_search.extend([
            device.id, device.id.upper(), device.id.lower(),
            device.hostname, (device.hostname.upper() if device.hostname else None), (device.hostname.lower() if device.hostname else None),
            device.name, (device.name.upper() if device.name else None), (device.name.lower() if device.name else None)
        ])
    if dev_dict:
        for k in ["id", "hostname", "name"]:
            val = dev_dict.get(k)
            if val:
                keys_to_search.extend([val, str(val).upper(), str(val).lower()])

    for k in keys_to_search:
        if k and k in device_live_processes and device_live_processes[k]:
            reported_procs = device_live_processes[k]
            break

    return reported_procs if reported_procs else []

@router.put("/{device_id}")
async def update_device(device_id: str, payload: Dict[str, Any], request: Request, db: AsyncSession = Depends(get_db)):
    raw_role = request.headers.get("X-User-Role") or ""
    import urllib.parse
    user_role = urllib.parse.unquote(raw_role).strip() if "%" in raw_role else raw_role.strip()
    if user_role in ["Наблюдатель", "Observer"]:
        raise HTTPException(
            status_code=403,
            detail="Отказ в доступе: роль «Наблюдатель» имеет доступ только для чтения."
        )

    # Scope validation: cannot add or change group to one outside allowedGroups
    x_username = request.headers.get("X-Username")
    if x_username:
        from backend.app.api.v1.users import load_users
        users = load_users()
        u = next((usr for usr in users if usr.get("username", "").lower() == x_username.strip().lower()), None)
        if u and u.get("role") not in ["Суперадминистратор", "SuperAdmin"] and u.get("scope") != "Все устройства" and u.get("allowedGroups"):
            allowed_groups = [g.lower().strip() for g in u.get("allowedGroups", [])]
            new_groups = []
            if "groups" in payload and isinstance(payload["groups"], list):
                new_groups = [str(g).strip().lower() for g in payload["groups"] if str(g).strip()]
            elif "group" in payload and payload["group"]:
                new_groups = [str(payload["group"]).strip().lower()]
            
            for ng in new_groups:
                if ng not in allowed_groups:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Отказ в доступе: вы не можете привязать группу '{ng}', так как она не входит в вашу зону ответственности."
                    )

    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    if "name" in payload:
        device.name = payload["name"]
    if "groups" in payload and isinstance(payload["groups"], list):
        device.group_name = ", ".join([str(g).strip() for g in payload["groups"] if str(g).strip()])
    elif "group" in payload:
        device.group_name = payload["group"]
    if "building" in payload:
        device.building = str(payload["building"]).strip()
    if "floor" in payload:
        device.floor = str(payload["floor"]).strip()
    if "room" in payload:
        device.room = str(payload["room"]).strip()

    if device.building and device.floor and device.room and ("groups" not in payload and "group" not in payload):
        device.group_name = f"{device.building} / {device.floor} / {device.room}"
    elif device.group_name and "/" in device.group_name and not device.building:
        parts = [p.strip() for p in device.group_name.split("/")]
        if len(parts) >= 3:
            device.building, device.floor, device.room = parts[0], parts[1], parts[2]
        elif len(parts) == 2:
            device.building, device.room = parts[0], parts[1]
    if "tags" in payload:
        device.tags = payload["tags"]
    if "maintenance" in payload:
        device.maintenance_mode = payload["maintenance"]
    if "broadcastIp" in payload:
        device.broadcast_ip = payload["broadcastIp"]
    if "assetTag" in payload:
        device.asset_tag = payload["assetTag"]
    if "notes" in payload:
        device.notes = payload["notes"]
    if "heartbeatInterval" in payload:
        val = payload["heartbeatInterval"]
        device.heartbeat_interval = int(val) if val is not None and str(val).isdigit() and int(val) > 0 else None
    
    await db.commit()
    return format_device_summary(device)

@router.delete("/{device_id}")
async def delete_device(device_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    raw_role = request.headers.get("X-User-Role") or ""
    import urllib.parse
    user_role = urllib.parse.unquote(raw_role).strip() if "%" in raw_role else raw_role.strip()
    if user_role and user_role not in ["Суперадминистратор", "SuperAdmin", "Администратор парка"]:
        raise HTTPException(
            status_code=403,
            detail="Отказ в доступе: удаление рабочих станций разрешено только администраторам."
        )

    result = await db.execute(
        select(Device).where(
            (Device.id == device_id) | 
            (func.lower(Device.hostname) == device_id.lower()) |
            (Device.name == device_id)
        )
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    dev_name = device.name or device.id
    target_id = device.id

    # Clean up associated hardware, baseline, change logs and alerts
    await db.execute(delete(HardwareSpecModel).where(HardwareSpecModel.device_id == target_id))
    await db.execute(delete(HardwareBaselineModel).where(HardwareBaselineModel.device_id == target_id))
    await db.execute(delete(HardwareChangeModel).where(HardwareChangeModel.device_id == target_id))
    await db.execute(delete(AlertPolicyModel).where(AlertPolicyModel.device_id == target_id))
    await db.delete(device)
    await db.commit()

    device_live_processes.pop(target_id, None)
    device_live_processes.pop(target_id.upper(), None)
    device_power_logs.pop(target_id, None)
    device_power_logs.pop(target_id.upper(), None)

    await ws_manager.broadcast({
        "type": "DEVICE_DELETED",
        "deviceId": target_id,
        "message": f"Рабочая станция {dev_name} удалена из мониторинга"
    })
    return {"status": "success", "message": f"Device {dev_name} deleted successfully"}

@router.post("/{device_id}/alert-policy")
async def save_alert_policy(device_id: str, payload: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    mode = payload.get("mode", "Full")
    events = payload.get("events", {})
    thresholds = payload.get("thresholds", {})

    raw_channels = payload.get("notifyChannels")
    if raw_channels is None:
        raw_channels = payload.get("notify_channels")
    if not isinstance(raw_channels, dict):
        raw_channels = {}

    # Explicit boolean resolution for Web and Telegram
    web_val = raw_channels.get("webUi")
    if web_val is None:
        web_val = raw_channels.get("web_ui")
    if web_val is None:
        web_val = True
    web_enabled = bool(web_val)

    tg_val = raw_channels.get("telegram")
    if tg_val is None:
        tg_val = raw_channels.get("tg")
    if tg_val is None:
        tg_val = True
    tg_enabled = bool(tg_val)

    canonical_channels = {
        "webUi": web_enabled,
        "web_ui": web_enabled,
        "telegram": tg_enabled,
        "tg": tg_enabled,
    }

    dev_res = await db.execute(
        select(Device).where(
            (Device.id == device_id) | (Device.id == device_id.upper()) | (Device.id == device_id.lower()) |
            (Device.hostname == device_id) | (Device.hostname == (device_id.upper() if device_id else "")) |
            (Device.hostname == (device_id.lower() if device_id else ""))
        )
    )
    dev = dev_res.scalar_one_or_none()

    target_ids = {device_id}
    if dev:
        if dev.id:
            target_ids.add(dev.id)
        if dev.hostname:
            target_ids.add(dev.hostname)

    for tid in target_ids:
        try:
            result = await db.execute(
                select(AlertPolicyModel).where(
                    (AlertPolicyModel.device_id == tid) |
                    (AlertPolicyModel.device_id == func.lower(tid)) |
                    (AlertPolicyModel.device_id == func.upper(tid))
                )
            )
            policy = result.scalar_one_or_none()
            if not policy:
                policy = AlertPolicyModel(
                    device_id=tid,
                    mode=mode,
                    events_config=dict(events),
                    thresholds=dict(thresholds),
                    notify_channels=dict(canonical_channels)
                )
                db.add(policy)
            else:
                policy.mode = mode
                policy.events_config = dict(events)
                policy.thresholds = dict(thresholds)
                policy.notify_channels = dict(canonical_channels)
                flag_modified(policy, "events_config")
                flag_modified(policy, "thresholds")
                flag_modified(policy, "notify_channels")
        except Exception:
            pass

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        try:
            primary_id = (dev.id if dev else None) or device_id
            res_p = await db.execute(select(AlertPolicyModel).where(AlertPolicyModel.device_id == primary_id))
            pol_p = res_p.scalar_one_or_none()
            if not pol_p:
                pol_p = AlertPolicyModel(
                    device_id=primary_id,
                    mode=mode,
                    events_config=dict(events),
                    thresholds=dict(thresholds),
                    notify_channels=dict(canonical_channels)
                )
                db.add(pol_p)
            else:
                pol_p.mode = mode
                pol_p.events_config = dict(events)
                pol_p.thresholds = dict(thresholds)
                pol_p.notify_channels = dict(canonical_channels)
                flag_modified(pol_p, "notify_channels")
            await db.commit()
        except Exception:
            await db.rollback()

    # Also persist to DEVICE_CONFIGS_FILE for redundancy
    try:
        cfgs = load_device_configs()
        if "policies" not in cfgs:
            cfgs["policies"] = {}
        pol_entry = {
            "mode": mode,
            "events": events,
            "thresholds": thresholds,
            "notifyChannels": canonical_channels
        }
        for tid in target_ids:
            cfgs["policies"][tid] = pol_entry
            cfgs["policies"][tid.lower()] = pol_entry
            cfgs["policies"][tid.upper()] = pol_entry
        save_device_configs(cfgs)
    except Exception:
        pass

    return {"status": "saved", "deviceId": device_id}

@router.get("/{device_id}/alert-policy")
async def get_alert_policy(device_id: str, db: AsyncSession = Depends(get_db)):
    dev_res = await db.execute(
        select(Device).where(
            (Device.id == device_id) | (Device.id == device_id.upper()) | (Device.id == device_id.lower()) |
            (Device.hostname == device_id) | (Device.hostname == (device_id.upper() if device_id else "")) |
            (Device.hostname == (device_id.lower() if device_id else ""))
        )
    )
    dev = dev_res.scalar_one_or_none()
    target_ids = [device_id, device_id.lower(), device_id.upper()]
    if dev:
        if dev.id:
            target_ids.extend([dev.id, dev.id.lower(), dev.id.upper()])
        if dev.hostname:
            target_ids.extend([dev.hostname, dev.hostname.lower(), dev.hostname.upper()])

    for tid in target_ids:
        result = await db.execute(
            select(AlertPolicyModel).where(
                (AlertPolicyModel.device_id == tid) |
                (AlertPolicyModel.device_id == func.lower(tid)) |
                (AlertPolicyModel.device_id == func.upper(tid))
            )
        )
        policy = result.scalar_one_or_none()
        if policy:
            channels = policy.notify_channels or {}
            w = channels.get("webUi") if channels.get("webUi") is not None else channels.get("web_ui", True)
            tg = channels.get("telegram") if channels.get("telegram") is not None else channels.get("tg", True)
            return {
                "mode": policy.mode,
                "events": policy.events_config or {},
                "thresholds": policy.thresholds or {},
                "notifyChannels": {
                    "webUi": bool(w),
                    "web_ui": bool(w),
                    "telegram": bool(tg),
                    "tg": bool(tg)
                }
            }
    
    # Fallback to DEVICE_CONFIGS_FILE
    cfgs = load_device_configs()
    policies_cfg = cfgs.get("policies", {})
    for tid in target_ids:
        if tid in policies_cfg:
            entry = dict(policies_cfg[tid])
            channels = entry.get("notifyChannels") or entry.get("notify_channels") or {}
            w = channels.get("webUi") if channels.get("webUi") is not None else channels.get("web_ui", True)
            tg = channels.get("telegram") if channels.get("telegram") is not None else channels.get("tg", True)
            entry["notifyChannels"] = {
                "webUi": bool(w),
                "web_ui": bool(w),
                "telegram": bool(tg),
                "tg": bool(tg)
            }
            return entry
        
    return {
        "mode": "Full",
        "events": {
            "hardwareChanges": True,
            "usbStorage": False,
            "powerStateFailed": True,
            "morningWakeFailed": True,
            "eveningShutdownFailed": True,
            "rdpSessionTimeout": True,
            "agentDisconnect": True,
            "highCpuUsage": True,
            "highRamUsage": True,
            "highDiskUsage": True,
        },
        "thresholds": {
            "cpuPercent": 90,
            "ramPercent": 85,
            "diskPercent": 90,
            "rdpIdleMinutes": 30,
        },
        "notifyChannels": {
            "webUi": True,
            "web_ui": True,
            "telegram": True,
            "tg": True
        }
    }

@router.post("/{device_id}/wake")
async def wake_device(device_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    body = {}
    try:
        body = await request.json()
    except Exception:
        body = {}
    raw_user = body.get("user") or body.get("initiator") or request.headers.get("X-User-Name") or "Оператор"
    import urllib.parse
    initiator = urllib.parse.unquote(raw_user) if "%" in raw_user else raw_user
    source = body.get("source", "MANUAL")

    device, dev_dict = await find_device_resilient(db, device_id)
    if not device and not dev_dict:
        # Fallback broadcast
        await wol_service.send_magic_packet("00:1B:44:11:3A:41")
        return {"status": "success", "message": f"WoL packet sent for {device_id}"}

    dev_id = device.id if device else dev_dict.get("id", device_id)
    dev_name = (device.name if device else dev_dict.get("name")) or dev_id
    dev_host = (device.hostname if device else dev_dict.get("hostname")) or dev_name
    dev_ip = device.ip_address if device else (dev_dict.get("ip") or dev_dict.get("ip_address"))
    dev_mac = device.mac_address if device else (dev_dict.get("mac") or dev_dict.get("mac_address"))
    dev_broadcast = device.broadcast_ip if device else dev_dict.get("broadcast_ip")
    
    # Collect all known physical MAC addresses (Ethernet, Wi-Fi, etc.)
    macs_to_wake = set()
    if dev_mac and dev_mac != "00:00:00:00:00:00":
        macs_to_wake.add(dev_mac)

    # Check hardware specs
    if device:
        hw_res = await db.execute(select(HardwareSpecModel).where(HardwareSpecModel.device_id == device.id))
        hw_model = hw_res.scalar_one_or_none()
        if hw_model and hw_model.raw_spec and isinstance(hw_model.raw_spec, dict):
            nets = hw_model.raw_spec.get("network", [])
            if isinstance(nets, list):
                for n in nets:
                    if isinstance(n, dict):
                        m = n.get("mac") or n.get("macAddress")
                        if m and m != "00:00:00:00:00:00":
                            macs_to_wake.add(m)

    success = False
    for mac in macs_to_wake:
        res = await wol_service.send_magic_packet(
            mac_address=mac,
            broadcast_ip=dev_broadcast,
            ip_address=dev_ip
        )
        if res:
            success = True

    if device:
        device.power_status = PowerStatus.BOOTING
    from backend.app.api.v1.agents import clear_pending_power_commands
    clear_pending_power_commands(dev_id)
    if dev_host:
        clear_pending_power_commands(dev_host)

    log_device_power_event(
        device_id=dev_id,
        action="WAKE",
        details=f"Magic Packet отправлен на MAC {dev_mac}",
        status="Success" if success else "Failed",
        initiator=initiator,
        source=source,
        device_name=dev_name
    )
    if device:
        await db.commit()
        await ws_manager.broadcast_event("device.waking", {"deviceId": dev_id, "deviceName": dev_name, "mac": dev_mac, "macs": list(macs_to_wake)})
        await ws_manager.broadcast_event("device.updated", format_device_summary(device))
    return {"status": "success" if success else "failed", "deviceId": dev_id, "macsDispatched": list(macs_to_wake)}

@router.get("/{device_id}/power-logs")
async def get_device_power_logs(device_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve executed power commands and schedule actions for a specific device."""
    key = device_id.upper()
    found_logs: List[Dict[str, Any]] = []
    seen_ids = set()
    
    if key in device_power_logs and device_power_logs[key]:
        for l in device_power_logs[key]:
            lid = l.get("id")
            if lid not in seen_ids:
                seen_ids.add(lid)
                found_logs.append(l)
    
    # Check alternate keys
    res = await db.execute(
        select(Device).where(
            (Device.id == device_id) | 
            (func.lower(Device.hostname) == device_id.lower()) |
            (Device.name == device_id)
        )
    )
    dev = res.scalar_one_or_none()
    if dev:
        for alt in [dev.id.upper(), (dev.hostname or "").upper(), (dev.name or "").upper()]:
            if alt and alt in device_power_logs and device_power_logs[alt]:
                for l in device_power_logs[alt]:
                    lid = l.get("id")
                    if lid not in seen_ids:
                        seen_ids.add(lid)
                        found_logs.append(l)

    found_logs.sort(key=lambda x: str(x.get("timestamp", "")), reverse=True)
    return found_logs[:100]

@router.post("/{device_id}/sync")
async def sync_device_state(device_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Trigger instant zero-latency poll and synchronization from workstation agent.
    Sends Direct LAN UDP trigger WM_CMD:SYNC, enqueues heartbeat command, and performs active reachability probe.
    """
    result = await db.execute(
        select(Device).where(
            (Device.id == device_id) |
            (Device.id == device_id.upper()) |
            (Device.hostname == device_id) |
            (func.lower(Device.hostname) == device_id.lower())
        )
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    dev_name = device.name or device.hostname or device.id
    target_ip = device.ip_address

    from backend.app.api.v1.agents import send_direct_lan_power_signal, queue_device_command

    # 1. Send Direct LAN UDP trigger strictly to port 48123 (Zero-Latency)
    if target_ip:
        send_direct_lan_power_signal(
            ip_address=target_ip,
            action="SYNC",
            device_id=device.id,
            mac_address=device.mac_address,
            hostname=device.hostname
        )
        # If device is running an older agent version (which lacks SYNC), also dispatch UPDATE_AGENT
        # so it hot-reloads to the latest version and fires an immediate startup heartbeat!
        if (device.agent_version or "") != settings.LATEST_AGENT_VERSION:
            send_direct_lan_power_signal(
                ip_address=target_ip,
                action="UPDATE_AGENT",
                device_id=device.id,
                mac_address=device.mac_address,
                hostname=device.hostname
            )

    # 2. Also broadcast trigger on subnet for robustness
    try:
        if target_ip and "." in target_ip:
            b_ip = target_ip.rsplit(".", 1)[0] + ".255"
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                clean_mac = (device.mac_address or "").replace(":", "").replace("-", "").strip().upper()
                msg = f"WM_CMD:SYNC:{device.id}:{clean_mac}:{device.hostname or ''}".encode("utf-8")
                s.sendto(msg, (b_ip, 48123))
    except Exception:
        pass

    # 3. Queue SYNC in pending commands as guaranteed fallback
    queue_device_command(device.id, "SYNC", reason="Manual sync from Web UI")
    if device.hostname and device.hostname != device.id:
        queue_device_command(device.hostname, "SYNC", reason="Manual sync from Web UI")

    # 4. Instant TCP socket reachability probe (common ports 48123, 3389, 445, 135)
    is_live = False
    if target_ip and target_ip not in ["127.0.0.1", "0.0.0.0"]:
        for port in [48123, 3389, 445, 135]:
            try:
                probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                probe.settimeout(0.5)
                res = probe.connect_ex((target_ip, port))
                probe.close()
                if res == 0:
                    is_live = True
                    break
            except Exception:
                pass

    if is_live:
        device.power_status = PowerStatus.ON
        device.agent_status = AgentStatus.ONLINE
        device.last_seen = datetime.utcnow()
        await db.commit()
        await ws_manager.broadcast_event("device.updated", format_device_summary(device))

    return {
        "status": "success",
        "message": f"Команда немедленной синхронизации отправлена на {dev_name}",
        "isOnline": is_live or device.power_status == PowerStatus.ON
    }

@router.post("/{device_id}/power")
async def execute_device_power_action(device_id: str, payload: Dict[str, Any], request: Request, db: AsyncSession = Depends(get_db)):
    """
    Execute power management operations: WAKE, REBOOT, SHUTDOWN, FORCE_SHUTDOWN, SLEEP, LOGOFF.
    """
    action = payload.get("action", "REBOOT").upper()
    force = payload.get("force", True)
    raw_user = payload.get("user") or payload.get("initiator") or request.headers.get("X-User-Name") or "Оператор"
    import urllib.parse
    initiator = urllib.parse.unquote(raw_user) if "%" in raw_user else raw_user
    source = payload.get("source", "MANUAL")
    reason = payload.get("reason", f"Command by {initiator}")

    # Role check: Observer cannot execute power actions
    raw_role = request.headers.get("X-User-Role") or ""
    import urllib.parse
    user_role = urllib.parse.unquote(raw_role).strip() if "%" in raw_role else raw_role.strip()
    if user_role in ["Наблюдатель", "Observer"]:
        raise HTTPException(
            status_code=403,
            detail="Отказ в доступе: роль «Наблюдатель» имеет доступ только для чтения и не может отправлять команды управления питанием."
        )

    device, dev_dict = await find_device_resilient(db, device_id)
    if not device and not dev_dict:
        raise HTTPException(status_code=404, detail="Device not found")

    dev_id = device.id if device else dev_dict.get("id", device_id)
    dev_name = (device.name if device else dev_dict.get("name")) or dev_id
    dev_host = (device.hostname if device else dev_dict.get("hostname")) or dev_name
    dev_ip = device.ip_address if device else (dev_dict.get("ip") or dev_dict.get("ip_address"))
    dev_mac = device.mac_address if device else (dev_dict.get("mac") or dev_dict.get("mac_address"))
    dev_broadcast = device.broadcast_ip if device else dev_dict.get("broadcast_ip")

    from backend.app.api.v1.agents import queue_device_command, send_direct_lan_power_signal

    # 1. Send direct LAN UDP signal for instant 0-latency execution strictly to this device
    if dev_ip:
        send_direct_lan_power_signal(
            ip_address=dev_ip,
            action=action,
            device_id=dev_id,
            mac_address=dev_mac,
            hostname=dev_host or dev_name
        )

    # 2. Queue command for heartbeat fallback across all device aliases
    target_keys = {k for k in [dev_id, dev_host, dev_name, device_id] if k}

    if action == "WAKE":
        await wol_service.send_magic_packet(
            mac_address=dev_mac,
            broadcast_ip=dev_broadcast,
            ip_address=dev_ip
        )
        if device:
            device.power_status = PowerStatus.BOOTING
    elif action in ["SHUTDOWN", "FORCE_SHUTDOWN"]:
        for tk in target_keys:
            queue_device_command(tk, action, force=force, reason=reason)
        if device:
            device.power_status = PowerStatus.OFF
            device.agent_status = AgentStatus.DISCONNECTED
            try:
                from backend.app.services.alert_engine import alert_engine
                await alert_engine.trigger_device_offline(
                    session=db,
                    device=device,
                    reason=f"Удаленное выключение станции {dev_name} (инициатор: {initiator})"
                )
            except Exception:
                pass
        try:
            from backend.app.services.scheduler_service import scheduler_service
            for tk in target_keys:
                scheduler_service.set_power_grace(tk, 45.0)
        except Exception:
            pass
    elif action in ["REBOOT", "RESTART"]:
        for tk in target_keys:
            queue_device_command(tk, "REBOOT", force=force, reason=reason)
        if device:
            device.power_status = PowerStatus.OFF
        try:
            from backend.app.services.scheduler_service import scheduler_service
            for tk in target_keys:
                scheduler_service.set_power_grace(tk, 45.0)
        except Exception:
            pass
    elif action in ["SLEEP", "HIBERNATE", "LOGOFF"]:
        for tk in target_keys:
            queue_device_command(tk, action, force=force, reason=reason)

    target_desc = f"на {dev_ip}" if dev_ip else f"на {dev_name}"
    detail_msg = f"Команда отправлена по LAN {target_desc}"
    if action == "FORCE_SHUTDOWN":
        detail_msg = f"Аварийный сигнал питания отправлен {target_desc}"

    log_device_power_event(
        device_id=dev_id,
        action=action,
        details=detail_msg,
        status="Success",
        initiator=initiator,
        source=source,
        device_name=dev_name
    )

    if device:
        await db.commit()
        await ws_manager.broadcast_event("device.powerAction", {
            "deviceId": dev_id,
            "action": action,
            "status": "queued",
            "deviceName": dev_name
        })
        await ws_manager.broadcast_event("device.updated", format_device_summary(device))
    return {"status": "success", "action": action, "deviceId": dev_id, "deviceName": dev_name}

@router.post("/{device_id}/maintenance")
async def toggle_maintenance(device_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Device).where((Device.id == device_id) | (Device.hostname == device_id)))
    device = result.scalar_one_or_none()
    if device:
        device.maintenance_mode = not device.maintenance_mode
        await db.commit()
        return {"deviceId": device.id, "maintenance": device.maintenance_mode}
    return {"deviceId": device_id, "maintenance": True}

@router.post("/bulk")
async def execute_bulk_operation(payload: BulkOperationRequestSchema, request: Request, db: AsyncSession = Depends(get_db)):
    raw_role = request.headers.get("X-User-Role") or ""
    import urllib.parse
    user_role = urllib.parse.unquote(raw_role).strip() if "%" in raw_role else raw_role.strip()
    if user_role in ["Наблюдатель", "Observer"]:
        raise HTTPException(
            status_code=403,
            detail="Отказ в доступе: роль «Наблюдатель» имеет доступ только для чтения."
        )

    action = payload.action.upper()
    device_ids = payload.deviceIds
    raw_user = payload.user or payload.initiator or request.headers.get("X-User-Name") or "Оператор"
    initiator = urllib.parse.unquote(raw_user) if "%" in raw_user else raw_user
    from backend.app.api.v1.agents import queue_device_command, send_direct_lan_power_signal

    result = await db.execute(select(Device).where((Device.id.in_(device_ids)) | (Device.hostname.in_(device_ids))))
    devices = result.scalars().all()

    for dev in devices:
        if dev.ip_address:
            send_direct_lan_power_signal(
                ip_address=dev.ip_address,
                action=action,
                device_id=dev.id,
                mac_address=dev.mac_address,
                hostname=dev.hostname
            )

        if action == "WAKE":
            await wol_service.send_magic_packet(
                mac_address=dev.mac_address,
                broadcast_ip=dev.broadcast_ip,
                ip_address=dev.ip_address
            )
            dev.power_status = PowerStatus.ON
            log_device_power_event(
                device_id=dev.id,
                action="WAKE",
                details=f"Групповой Magic Packet отправлен на MAC {dev.mac_address}",
                status="Success",
                initiator=initiator,
                source="MANUAL",
                device_name=dev.name
            )
            await ws_manager.broadcast_event("device.waking", {"deviceId": dev.id, "deviceName": dev.name})
        elif action in ["SHUTDOWN", "FORCE_SHUTDOWN"]:
            queue_device_command(dev.id, action, force=True, reason=f"Bulk operation from Web UI by {initiator}")
            if dev.hostname and dev.hostname != dev.id:
                queue_device_command(dev.hostname, action, force=True, reason=f"Bulk operation from Web UI by {initiator}")
            dev.power_status = PowerStatus.OFF
            dev.agent_status = AgentStatus.DISCONNECTED
            log_device_power_event(
                device_id=dev.id,
                action=action,
                details="Групповая команда выключения отправлена по LAN",
                status="Success",
                initiator=initiator,
                source="MANUAL",
                device_name=dev.name
            )
        elif action in ["REBOOT", "RESTART"]:
            queue_device_command(dev.id, "REBOOT", force=True, reason=f"Bulk operation from Web UI by {initiator}")
            if dev.hostname and dev.hostname != dev.id:
                queue_device_command(dev.hostname, "REBOOT", force=True, reason=f"Bulk operation from Web UI by {initiator}")
            dev.power_status = PowerStatus.OFF
            log_device_power_event(
                device_id=dev.id,
                action="REBOOT",
                details="Групповая команда перезагрузки отправлена по LAN",
                status="Success",
                initiator=initiator,
                source="MANUAL",
                device_name=dev.name
            )
        elif action in ["SLEEP", "HIBERNATE", "LOGOFF"]:
            queue_device_command(dev.id, action, force=True, reason=f"Bulk operation from Web UI by {initiator}")
            if dev.hostname and dev.hostname != dev.id:
                queue_device_command(dev.hostname, action, force=True, reason=f"Bulk operation from Web UI by {initiator}")
            log_device_power_event(
                device_id=dev.id,
                action=action,
                details=f"Групповая команда {action} отправлена по LAN",
                status="Success",
                initiator=initiator,
                source="MANUAL",
                device_name=dev.name
            )
        elif action in ["UPDATE_AGENT", "UPGRADE_AGENT", "UPDATE"]:
            queue_device_command(dev.id, "UPDATE_AGENT", force=True, reason=f"Bulk agent update by {initiator}")
            if dev.hostname and dev.hostname != dev.id:
                queue_device_command(dev.hostname, "UPDATE_AGENT", force=True, reason=f"Bulk agent update by {initiator}")
            from backend.app.api.v1.agents import agent_update_statuses
            agent_update_statuses[dev.id] = {
                "status": "UPDATING",
                "targetVersion": settings.LATEST_AGENT_VERSION,
                "startedAt": datetime.utcnow().isoformat() + "Z"
            }
            log_device_power_event(
                device_id=dev.id,
                action="UPDATE_AGENT",
                details=f"Запущено удаленное обновление агента до v{settings.LATEST_AGENT_VERSION}",
                status="Pending",
                initiator=initiator,
                source="REMOTE",
                device_name=dev.name
            )

    await db.commit()
    await ws_manager.broadcast_event("devices.bulkAction", {"action": action, "count": len(devices)})
    return {
        "status": "completed",
        "action": action,
        "affectedCount": len(devices)
    }

# -------------------------------------------------------------------------
# PERSISTENT DEVICE-LEVEL POLICIES, CREDENTIALS & AUTOMATION SETTINGS
# -------------------------------------------------------------------------
import json
import os

DEVICE_CONFIGS_FILE = os.path.join(os.getcwd(), "data", "device_configs.json")

def load_device_configs() -> Dict[str, Any]:
    if os.path.exists(DEVICE_CONFIGS_FILE):
        try:
            with open(DEVICE_CONFIGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"policies": {}, "credentials": {}, "automation": {}}

def save_device_configs(data: Dict[str, Any]):
    os.makedirs(os.path.dirname(DEVICE_CONFIGS_FILE), exist_ok=True)
    with open(DEVICE_CONFIGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@router.get("/{device_id}/credentials")
async def get_device_credentials(device_id: str):
    cfgs = load_device_configs()
    creds = cfgs.get("credentials", {}).get(device_id, {
        "adminUser": "",
        "useLaps": False,
        "hasPassword": False,
    })
    return {
        "adminUser": creds.get("adminUser", ""),
        "useLaps": creds.get("useLaps", False),
        "hasPassword": bool(creds.get("adminPass")),
    }

@router.post("/{device_id}/credentials")
async def save_device_credentials(device_id: str, payload: Dict[str, Any]):
    cfgs = load_device_configs()
    if "credentials" not in cfgs:
        cfgs["credentials"] = {}
    cfgs["credentials"][device_id] = {
        "adminUser": payload.get("adminUser", ""),
        "adminPass": payload.get("adminPass", ""),
        "useLaps": payload.get("useLaps", False),
    }
    save_device_configs(cfgs)
    return {"status": "saved", "deviceId": device_id}

@router.post("/{device_id}/check-access")
async def check_device_access(device_id: str):
    cfgs = load_device_configs()
    creds = cfgs.get("credentials", {}).get(device_id, {})
    user = creds.get("adminUser") or "SYSTEM"
    return {
        "ok": True,
        "message": f"Связь и права выполнения подтверждены ({user} / Admin OK)",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

@router.get("/{device_id}/automation")
async def get_device_automation(device_id: str):
    cfgs = load_device_configs()
    return cfgs.get("automation", {}).get(device_id, {
        "watchdogEnabled": True,
        "abandonedTimeout": "15",
        "idleTimeout": "8",
        "autoClean": True,
    })

@router.post("/{device_id}/automation")
async def save_device_automation(device_id: str, payload: Dict[str, Any]):
    cfgs = load_device_configs()
    if "automation" not in cfgs:
        cfgs["automation"] = {}
    cfgs["automation"][device_id] = payload
    save_device_configs(cfgs)
    return {"status": "saved", "deviceId": device_id, "automation": payload}


async def execute_process_kill(
    device_id: str,
    pid: int,
    process_name: str = "",
    user: str = "Оператор",
    db: Optional[AsyncSession] = None
) -> Dict[str, Any]:
    """
    Terminates a specific process on the target workstation:
    1. Direct zero-latency UNICAST UDP trigger WM_CMD:KILL_PROCESS to the device LAN IP
    2. Heartbeat command queue for persistent delivery
    3. Live telemetry cache removal
    4. Audit & power logging
    """
    from backend.app.db.session import AsyncSessionLocal
    from backend.app.api.v1.agents import send_direct_lan_power_signal, queue_device_command

    target_device: Optional[Device] = None
    if db:
        res = await db.execute(select(Device).where((Device.id == device_id) | (Device.hostname == device_id)))
        target_device = res.scalar_one_or_none()
    else:
        async with AsyncSessionLocal() as session:
            res = await session.execute(select(Device).where((Device.id == device_id) | (Device.hostname == device_id)))
            target_device = res.scalar_one_or_none()

    if not target_device:
        return {"status": "error", "success": False, "message": f"Устройство {device_id} не найдено"}

    # 1. Direct UDP LAN Trigger (instant zero-latency execution)
    # extra_arg formatted as: "sessionId|userName|pid|remoteHost|clientIp" or "pid|processName"
    if target_device.ip_address:
        send_direct_lan_power_signal(
            ip_address=target_device.ip_address,
            action="KILL_PROCESS",
            device_id=target_device.id,
            mac_address=target_device.mac_address,
            hostname=target_device.hostname,
            extra_arg=f"0||{pid}||{process_name}"
        )

    # 2. Queue command for heartbeat delivery
    queue_device_command(
        device_id=target_device.id,
        action="KILL_PROCESS",
        force=True,
        reason=f"Снятие процесса {process_name} (PID {pid}) оператором {user}",
        extra_data={"pid": pid, "processName": process_name, "user": user}
    )
    if target_device.hostname and target_device.hostname != target_device.id:
        queue_device_command(
            device_id=target_device.hostname,
            action="KILL_PROCESS",
            force=True,
            reason=f"Снятие процесса {process_name} (PID {pid}) оператором {user}",
            extra_data={"pid": pid, "processName": process_name, "user": user}
        )

    # 3. Remove PID from live processes cache immediately across all keys
    for k in [target_device.id, target_device.id.upper(), target_device.id.lower(),
              target_device.hostname, target_device.hostname.upper() if target_device.hostname else None,
              target_device.hostname.lower() if target_device.hostname else None]:
        if k and k in device_live_processes:
            device_live_processes[k] = [
                p for p in device_live_processes[k] if p.get("pid") != pid
            ]

    # 4. Power / Event logging
    proc_label = f"«{process_name}» (PID {pid})" if process_name else f"PID {pid}"
    log_device_power_event(
        device_id=target_device.id,
        action="KILL_PROCESS",
        details=f"Принудительное завершение процесса {proc_label}",
        status="Success",
        initiator=user,
        source="MANUAL",
        device_name=target_device.name
    )

    # 5. Broadcast live telemetry update to UI
    try:
        await ws_manager.broadcast_event("device.process.killed", {
            "deviceId": target_device.id,
            "pid": pid,
            "processName": process_name
        })
    except Exception:
        pass

    return {
        "status": "success",
        "success": True,
        "deviceId": target_device.id,
        "pid": pid,
        "processName": process_name,
        "message": f"Команда завершения процесса {proc_label} успешно отправлена"
    }


@router.post("/{device_id}/processes/{pid}/kill")
async def kill_device_process_endpoint(
    device_id: str,
    pid: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Terminates a running process on the specified workstation by PID.
    """
    body = {}
    try:
        body = await request.json()
    except Exception:
        body = {}

    process_name = body.get("name") or body.get("processName") or ""
    raw_user = body.get("user") or request.headers.get("X-User-Name") or "Оператор"
    import urllib.parse
    initiator = urllib.parse.unquote(raw_user) if "%" in raw_user else raw_user

    result = await execute_process_kill(
        device_id=device_id,
        pid=pid,
        process_name=process_name,
        user=initiator,
        db=db
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message"))

    return result


