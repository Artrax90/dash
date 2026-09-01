import sys
import os
import re
import time
import json
import socket
import platform
import subprocess
import threading
from datetime import datetime, timedelta
import urllib.request
import urllib.error

AGENT_VERSION = "2.5.0"

def execute_power_command(action: str, extra: dict = None):
    act = str(action).upper().strip()
    print(f"[*] Executing power command: {act} (extra={extra})")
    is_win = platform.system() == "Windows"
    
    if act in ["UPDATE_AGENT", "UPGRADE_AGENT", "UPDATE"]:
        cfg = load_config()
        server_base = cfg.get("server_url", "http://localhost:2301/api/v1").rstrip("/")
        execute_agent_update(server_base, cfg, "2.5.0")
        return
    elif act in ["REBOOT", "RESTART"]:
        if is_win:
            subprocess.run("shutdown /r /f /t 0", shell=True)
        else:
            subprocess.run("systemctl reboot || reboot || shutdown -r now", shell=True)
    elif act in ["SHUTDOWN", "FORCE_SHUTDOWN", "POWEROFF"]:
        if is_win:
            subprocess.run("shutdown /s /f /t 0", shell=True)
        else:
            subprocess.run("systemctl poweroff || poweroff || shutdown -h now", shell=True)
    elif act in ["SLEEP", "SUSPEND"]:
        if is_win:
            subprocess.run("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
        else:
            subprocess.run("systemctl suspend", shell=True)
    elif act in ["LOGOFF", "RESET_SESSION", "RDP_CLEANUP"]:
        sess_id = extra.get("sessionId") if extra else None
        if is_win:
            if sess_id is not None:
                subprocess.run(f"logoff {sess_id} 2>nul & rwinsta {sess_id} 2>nul", shell=True)
            else:
                subprocess.run("shutdown /l /f", shell=True)
        else:
            if sess_id is not None:
                subprocess.run(f"loginctl terminate-session {sess_id} 2>/dev/null || pkill -KILL -s {sess_id} 2>/dev/null", shell=True)
            else:
                user = get_current_user()
                if user and user not in ["root", "User"]:
                    subprocess.run(f"pkill -KILL -u {user}", shell=True)
    elif act in ["LOCK"]:
        if is_win:
            subprocess.run("rundll32.exe user32.dll,LockWorkStation", shell=True)
        else:
            subprocess.run("loginctl lock-session || xdg-screensaver lock || true", shell=True)

def get_rdp_sessions() -> list:
    sessions = []
    seen_ids = set()
    is_win = platform.system() == "Windows"
    
    if is_win:
        # 1. Incoming RDP sessions via quser / qwinsta
        try:
            out = subprocess.check_output("quser 2>nul || qwinsta 2>nul || true", shell=True, text=True, errors="ignore")
            for line in out.splitlines():
                line = line.strip().lstrip(">").strip()
                if not line or line.startswith("SESSIONNAME") or line.startswith("СЕАНС") or line.startswith("---"):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    s_name = parts[0]
                    u_name = ""
                    s_id = -1
                    is_rdp = "rdp" in s_name.lower() or "tcp" in s_name.lower()
                    if len(parts) >= 4 and parts[2].isdigit():
                        u_name = parts[1]
                        s_id = int(parts[2])
                    elif len(parts) >= 3 and parts[1].isdigit():
                        s_id = int(parts[1])
                    
                    if s_id >= 0 and s_id not in seen_ids and u_name and u_name != "65536":
                        sessions.append({
                            "id": s_id,
                            "username": u_name,
                            "sessionName": s_name,
                            "type": "Входящий RDP" if is_rdp else "Локальный сеанс",
                            "state": "Active",
                            "idleTime": "0 мин",
                            "logonTime": datetime.now().strftime("%Y-%m-%d %H:%M")
                        })
                        seen_ids.add(s_id)
        except Exception:
            pass
        
        # 2. Outgoing RDP client connections (mstsc -> RemotePort 3389)
        try:
            ps_cmd = 'Get-NetTCPConnection -RemotePort 3389 -State Established -ErrorAction SilentlyContinue | Select-Object RemoteAddress | ConvertTo-Json'
            raw = run_ps_json(ps_cmd)
            out_idx = 100
            for item in normalize_list(raw):
                rem_ip = item.get("RemoteAddress")
                if rem_ip:
                    sessions.append({
                        "id": out_idx,
                        "username": get_current_user(),
                        "sessionName": f"mstsc -> {rem_ip}",
                        "type": f"Исходящий RDP ({rem_ip})",
                        "state": "Active",
                        "idleTime": "0 мин",
                        "logonTime": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "clientIp": rem_ip
                    })
                    out_idx += 1
        except Exception:
            pass
    else:
        # Linux sessions
        try:
            out = subprocess.check_output("who -u 2>/dev/null || true", shell=True, text=True, timeout=3)
            for idx, line in enumerate(out.strip().splitlines()):
                parts = line.split()
                if len(parts) >= 4:
                    uname = parts[0]
                    terminal = parts[1]
                    logon_date = f"{parts[2]} {parts[3]}"
                    idle = parts[4] if len(parts) > 4 and parts[4] != "." else "0 мин"
                    host = parts[-1].strip("()") if parts[-1].startswith("(") else "Local"
                    is_remote = host != "Local" and host != ":0" and host != ""
                    sessions.append({
                        "id": idx + 1,
                        "username": uname,
                        "sessionName": f"pts/{terminal}",
                        "type": f"Входящий сеанс ({host})" if is_remote else "Локальный сеанс",
                        "state": "Active" if idle == "0 мин" or idle == "." else "Idle",
                        "idleTime": idle,
                        "logonTime": logon_date,
                        "clientIp": host if is_remote else ""
                    })
        except Exception:
            pass
        
        # Linux outgoing RDP/SSH
        try:
            out_conns = subprocess.check_output("ss -nt '( dport = :3389 )' 2>/dev/null || netstat -nt 2>/dev/null | grep :3389 || true", shell=True, text=True, timeout=3)
            for idx, line in enumerate(out_conns.strip().splitlines()):
                if "ESTAB" in line.upper() or "ESTABLISHED" in line.upper():
                    parts = line.split()
                    rem = parts[-1] if len(parts) > 0 else "Remote"
                    sessions.append({
                        "id": 100 + idx,
                        "username": get_current_user(),
                        "sessionName": f"rdp -> {rem}",
                        "type": f"Исходящий RDP ({rem})",
                        "state": "Active",
                        "idleTime": "0 мин",
                        "logonTime": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "clientIp": rem
                    })
        except Exception:
            pass

    return sessions

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.environ.get("WM_CONFIG_PATH", os.path.join(SCRIPT_DIR, "config.json"))

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    return {
        "server_url": os.environ.get("WM_SERVER", "http://localhost:2301/api/v1"),
        "enrollment_token": os.environ.get("WM_TOKEN", ""),
        "device_id": "",
        "agent_secret": "",
        "heartbeat_interval_seconds": 10
    }

def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

AGENT_VERSION = "2.4.0"

def http_post(url, data):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": f"WorkstationAgent/{AGENT_VERSION}"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_cpu_usage():
    try:
        import psutil
        return int(psutil.cpu_percent(interval=0.5))
    except Exception:
        return 5

def get_memory_info():
    try:
        import psutil
        mem = psutil.virtual_memory()
        return round(mem.total / (1024**3)), int(mem.percent)
    except Exception:
        return 16, 30

def get_disk_info():
    try:
        import psutil
        path = "C:\\" if platform.system() == "Windows" else "/"
        return int(psutil.disk_usage(path).percent)
    except Exception:
        return 40

def get_top_processes():
    procs = []
    # 1. Try psutil
    try:
        import psutil
        for p in sorted(psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'memory_info', 'username', 'status']), key=lambda x: (x.info.get('cpu_percent') or 0, x.info.get('memory_percent') or 0), reverse=True)[:15]:
            try:
                info = p.info
                name = info.get('name') or 'unknown'
                pid = info.get('pid') or 0
                cpu = info.get('cpu_percent') or 0.0
                mem_info = info.get('memory_info')
                ram_mb = round(mem_info.rss / (1024 * 1024)) if mem_info else int(info.get('memory_percent') or 0) * 10
                user = info.get('username') or ('root' if platform.system() == 'Linux' else 'SYSTEM')
                procs.append({
                    "pid": pid,
                    "name": name,
                    "cpu": f"{cpu:.1f}",
                    "ram": ram_mb,
                    "diskIo": "0.1 MB/s",
                    "user": user.split('\\')[-1] if user else 'SYSTEM',
                    "status": "Running"
                })
            except Exception:
                continue
    except Exception:
        pass
    
    # 2. Linux ps command fallback
    if not procs and platform.system() == "Linux":
        try:
            out = subprocess.check_output("ps -eo pid,comm,%cpu,%mem,user --sort=-%cpu | head -n 16", shell=True, text=True)
            lines = [l.strip() for l in out.splitlines() if l.strip()]
            for line in lines[1:]:
                parts = line.split(None, 4)
                if len(parts) >= 5:
                    pid_str, comm, cpu_s, mem_s, usr = parts[0], parts[1], parts[2], parts[3], parts[4]
                    procs.append({
                        "pid": int(pid_str),
                        "name": comm,
                        "cpu": cpu_s,
                        "ram": round(float(mem_s) * 80),
                        "diskIo": "0.1 MB/s",
                        "user": usr,
                        "status": "Running"
                    })
        except Exception:
            pass

    # 3. Windows PowerShell Get-Process fallback
    if not procs and platform.system() == "Windows":
        try:
            ps_cmd = 'Get-Process | Sort-Object CPU -Descending | Select-Object -First 12 Id, ProcessName, CPU, WorkingSet64 | ConvertTo-Json'
            raw = run_ps_json(ps_cmd)
            for item in normalize_list(raw):
                if item.get("ProcessName"):
                    procs.append({
                        "pid": item.get("Id", 0),
                        "name": f"{item.get('ProcessName')}.exe",
                        "cpu": f"{round(float(item.get('CPU') or 0) % 100, 1)}",
                        "ram": round((item.get("WorkingSet64") or 0) / (1024*1024)),
                        "diskIo": "0.2 MB/s",
                        "user": get_current_user() or "SYSTEM",
                        "status": "Running"
                    })
        except Exception:
            pass

    return procs

def get_rdp_sessions():
    sessions = []
    seen_ids = set()
    is_win = platform.system() == "Windows"
    
    if is_win:
        try:
            quser_path = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32", "quser.exe")
            if os.path.exists(quser_path):
                proc = subprocess.run([quser_path], capture_output=True, timeout=3)
                raw_out = ""
                for enc in ["cp866", "utf-8", "cp1251"]:
                    try:
                        raw_out = proc.stdout.decode(enc)
                        break
                    except Exception:
                        pass
                if raw_out:
                    lines = [l.strip() for l in raw_out.splitlines() if l.strip()]
                    if len(lines) > 1:
                        for line in lines[1:]:
                            clean = line.lstrip(">").strip()
                            parts = clean.split()
                            if len(parts) >= 3:
                                u_name = parts[0]
                                s_name = ""
                                s_id = 0
                                s_state = "Active"
                                idle = "0 мин"
                                logon = ""
                                if parts[1].isdigit():
                                    s_id = int(parts[1])
                                    s_state = parts[2]
                                    if len(parts) >= 4: idle = parts[3]
                                    if len(parts) >= 5: logon = " ".join(parts[4:])
                                else:
                                    s_name = parts[1]
                                    if len(parts) >= 3 and parts[2].isdigit(): s_id = int(parts[2])
                                    if len(parts) >= 4: s_state = parts[3]
                                    if len(parts) >= 5: idle = parts[4]
                                    if len(parts) >= 6: logon = " ".join(parts[5:])
                                
                                std_state = "Disconnected" if ("disc" in s_state.lower() or "откл" in s_state.lower()) else "Active"
                                is_rdp = bool("rdp" in s_name.lower() or "tcp" in s_name.lower() or s_id > 0)
                                s_obj = {
                                    "id": s_id,
                                    "username": u_name,
                                    "sessionName": s_name or f"rdp-tcp#{s_id}",
                                    "type": "Входящий RDP" if is_rdp else "Локальный сеанс",
                                    "state": std_state,
                                    "idleTime": "0 мин" if (not idle or any(x in idle.lower() for x in [".", "none", "нет", "отсут"])) else idle,
                                    "logonTime": logon or datetime.utcnow().strftime("%Y-%m-%d %H:%M")
                                }
                                sessions.append(s_obj)
                                seen_ids.add(s_id)
        except Exception:
            pass
        
        try:
            import psutil
            mstsc_pids = set()
            mstsc_owners = {}
            for p in psutil.process_iter(['pid', 'name', 'username', 'cmdline']):
                p_name = (p.info.get('name') or '').lower()
                if p_name in ['mstsc.exe', 'msrdc.exe', 'remotedesktop.exe']:
                    pid = p.info.get('pid')
                    mstsc_pids.add(pid)
                    u = (p.info.get('username') or '').split('\\')[-1]
                    if u and u.lower() not in ['system', 'network service', 'local service']:
                        mstsc_owners[pid] = u
            
            out_idx = 100
            for conn in psutil.net_connections(kind='tcp'):
                if conn.status == 'ESTABLISHED':
                    is_mstsc = conn.pid in mstsc_pids
                    rem_port = conn.raddr.port if conn.raddr else 0
                    rem_ip = conn.raddr.ip if conn.raddr else ''
                    if (is_mstsc or (rem_port >= 3389 and rem_port <= 3399)) and rem_ip and rem_ip not in ['127.0.0.1', '0.0.0.0', '::1']:
                        u_name = mstsc_owners.get(conn.pid) or get_current_user() or 'User'
                        target_label = f"{rem_ip}:{rem_port}" if rem_port != 3389 else rem_ip
                        sessions.append({
                            "id": out_idx,
                            "username": u_name,
                            "sessionName": f"mstsc -> {target_label}",
                            "type": f"Исходящий RDP ({rem_ip})",
                            "state": "Active",
                            "idleTime": "0 мин",
                            "logonTime": datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
                            "clientIp": rem_ip
                        })
                        out_idx += 1
        except Exception:
            pass
    else:
        try:
            out = subprocess.check_output("who -u || w -h", shell=True, text=True, timeout=2)
            idx = 1
            for line in out.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2:
                    u_name = parts[0]
                    tty = parts[1]
                    is_remote = ":" in tty or "pts" in tty
                    sessions.append({
                        "id": idx,
                        "username": u_name,
                        "sessionName": tty,
                        "type": "SSH / Remote" if is_remote else "Локальный сеанс",
                        "state": "Active",
                        "idleTime": parts[4] if len(parts) >= 5 and parts[4] != "." else "0 мин",
                        "logonTime": f"{parts[2]} {parts[3]}" if len(parts) >= 4 else datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
                        "clientIp": parts[-1].strip("()") if (len(parts) >= 6 and parts[-1].startswith("(") and parts[-1].endswith(")")) else ""
                    })
                    idx += 1
        except Exception:
            pass

    return sessions

def get_current_user():
    # 1. Try psutil users
    try:
        import psutil
        users = [u.name for u in psutil.users()]
        if users:
            return users[0]
    except Exception:
        pass

    # 2. Try environment variables
    user = os.environ.get("USERNAME") or os.environ.get("USER")
    if user and user.lower() not in ["system", "local service", "network service"]:
        return user

    # 3. Try WMIC on Windows
    if platform.system() == "Windows":
        try:
            out = subprocess.check_output("wmic computersystem get username", shell=True, text=True, timeout=2)
            lines = [l.strip() for l in out.splitlines() if l.strip() and "UserName" not in l]
            if lines and lines[0]:
                return lines[0].split("\\")[-1]
        except Exception:
            pass

    return user or "User"

def get_uptime_info():
    uptime_sec = 0
    boot_time_iso = None
    try:
        if platform.system() == "Windows":
            try:
                import psutil
                btime = psutil.boot_time()
                uptime_sec = int(time.time() - btime)
                boot_time_iso = datetime.utcfromtimestamp(btime).isoformat() + "Z"
            except Exception:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                tick_ms = kernel32.GetTickCount64()
                uptime_sec = int(tick_ms / 1000.0)
                boot_time_iso = (datetime.utcnow() - timedelta(seconds=uptime_sec)).isoformat() + "Z"
        else:
            try:
                with open("/proc/uptime", "r") as f:
                    uptime_sec = int(float(f.readline().split()[0]))
                boot_time_iso = (datetime.utcnow() - timedelta(seconds=uptime_sec)).isoformat() + "Z"
            except Exception:
                import psutil
                btime = psutil.boot_time()
                uptime_sec = int(time.time() - btime)
                boot_time_iso = datetime.utcfromtimestamp(btime).isoformat() + "Z"
    except Exception:
        uptime_sec = 0

    if uptime_sec > 0:
        if not boot_time_iso:
            boot_time_iso = (datetime.utcnow() - timedelta(seconds=uptime_sec)).isoformat() + "Z"
        days = uptime_sec // 86400
        hours = (uptime_sec % 86400) // 3600
        mins = (uptime_sec % 3600) // 60
        if days > 0:
            uptime_str = f"{days}д {hours:02d}ч"
        elif hours > 0:
            uptime_str = f"{hours}ч {mins:02d}м"
        else:
            uptime_str = f"{mins}м" if mins > 0 else "Менее 1 мин"
    else:
        uptime_str = "Только что"

    return uptime_str, uptime_sec, boot_time_iso

def get_os_info():
    sys_type = platform.system()
    if sys_type == "Windows":
        try:
            cmd = "(Get-CimInstance Win32_OperatingSystem).Caption"
            proc = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd], capture_output=True, text=True, timeout=3)
            out = proc.stdout.strip().replace("Microsoft ", "").strip()
            if out:
                return "Windows", out
        except Exception:
            pass
        return "Windows", f"Windows {platform.release()}"
    elif sys_type == "Linux":
        distro_name = "Linux"
        try:
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release", "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("PRETTY_NAME="):
                            distro_name = line.split("=", 1)[1].strip().strip('"')
                            break
                        elif line.startswith("NAME=") and distro_name == "Linux":
                            distro_name = line.split("=", 1)[1].strip().strip('"')
        except Exception:
            pass
        return "Linux", distro_name
    elif sys_type == "Darwin":
        return "macOS", f"macOS {platform.mac_ver()[0]}"
    return sys_type, sys_type

def get_primary_mac_and_ip():
    hostname = socket.gethostname()
    ip = "127.0.0.1"
    mac = "00:00:00:00:00:00"

    # 1. Detect primary outgoing LAN IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        try:
            ip = socket.gethostbyname(hostname)
        except Exception:
            pass

    # 2. Detect corresponding physical MAC address on Windows
    if platform.system() == "Windows":
        try:
            cmd = f'(Get-NetAdapter -InterfaceIndex (Get-NetIPAddress -IPAddress {ip}).InterfaceIndex).MacAddress'
            proc = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd], capture_output=True, text=True, timeout=3)
            out = proc.stdout.strip()
            if out and len(out) >= 12:
                mac = out.replace("-", ":").upper()
        except Exception:
            pass

    # 3. Detect corresponding MAC address on Linux
    if platform.system() == "Linux" and mac == "00:00:00:00:00:00":
        try:
            route_out = subprocess.check_output("ip route get 8.8.8.8", shell=True, text=True, timeout=2)
            dev_match = re.search(r'dev\s+([^\s]+)', route_out)
            if dev_match:
                iface = dev_match.group(1)
                with open(f"/sys/class/net/{iface}/address", "r") as f:
                    mac = f.read().strip().upper()
        except Exception:
            pass

    # 4. Fallback to uuid node
    if mac == "00:00:00:00:00:00":
        try:
            import uuid
            raw_mac = uuid.getnode()
            mac = ":".join(("%012X" % raw_mac)[i:i+2] for i in range(0, 12, 2))
        except Exception:
            pass

    return hostname, ip, mac

def run_ps_json(cmd: str):
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True,
            text=True,
            timeout=8
        )
        out = proc.stdout.strip()
        if out:
            return json.loads(out)
    except Exception:
        pass
    return None

def normalize_list(data):
    if data is None:
        return []
    if isinstance(data, list):
        return data
    return [data]

def collect_hardware():
    hostname, ip, mac = get_primary_mac_and_ip()
    total_ram, _ = get_memory_info()
    cores = os.cpu_count() or 4

    # Default baseline spec in case of non-Windows or restricted env
    spec = {
        "motherboard": {
            "manufacturer": "OEM / Motherboard",
            "model": "System Board",
            "serialNumber": f"MB-{mac.replace(':', '')[:8]}",
            "version": "1.0"
        },
        "bios": {
            "vendor": "UEFI BIOS",
            "version": "1.0",
            "releaseDate": "2025-01-01"
        },
        "cpu": {
            "model": platform.processor() or f"{platform.machine()} Processor",
            "cores": cores,
            "threads": cores * 2,
            "baseFrequencyGhz": 3.0,
            "socket": "LGA"
        },
        "ram": {
            "totalGb": total_ram,
            "slots": []
        },
        "storage": [],
        "gpus": [],
        "network": [],
        "sound": []
    }

    if platform.system() == "Windows":
        try:
            # 1. CPU
            cpu_raw = run_ps_json("Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed, SocketDesignation | ConvertTo-Json")
            cpu_items = normalize_list(cpu_raw)
            if cpu_items:
                c = cpu_items[0]
                spec["cpu"]["model"] = c.get("Name") or spec["cpu"]["model"]
                spec["cpu"]["cores"] = c.get("NumberOfCores") or spec["cpu"]["cores"]
                spec["cpu"]["threads"] = c.get("NumberOfLogicalProcessors") or spec["cpu"]["threads"]
                if c.get("MaxClockSpeed"):
                    spec["cpu"]["baseFrequencyGhz"] = round(c.get("MaxClockSpeed") / 1000.0, 2)
                if c.get("SocketDesignation"):
                    spec["cpu"]["socket"] = c.get("SocketDesignation")

            # 2. Motherboard
            mb_raw = run_ps_json("Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer, Product, SerialNumber, Version | ConvertTo-Json")
            mb_items = normalize_list(mb_raw)
            if mb_items:
                m = mb_items[0]
                spec["motherboard"]["manufacturer"] = m.get("Manufacturer") or "OEM"
                spec["motherboard"]["model"] = m.get("Product") or "Motherboard"
                spec["motherboard"]["serialNumber"] = m.get("SerialNumber") or f"MB-{mac.replace(':', '')[:8]}"
                spec["motherboard"]["version"] = m.get("Version") or "Rev 1.0"

            # 3. BIOS
            bios_raw = run_ps_json("Get-CimInstance Win32_BIOS | Select-Object Manufacturer, SMBIOSBIOSVersion, ReleaseDate | ConvertTo-Json")
            bios_items = normalize_list(bios_raw)
            if bios_items:
                b = bios_items[0]
                spec["bios"]["vendor"] = b.get("Manufacturer") or "AMI"
                spec["bios"]["version"] = b.get("SMBIOSBIOSVersion") or "v1.0"
                rel_date = b.get("ReleaseDate")
                if isinstance(rel_date, str) and "Date(" in rel_date:
                    try:
                        ms = int(re.search(r'\d+', rel_date).group())
                        spec["bios"]["releaseDate"] = datetime.utcfromtimestamp(ms / 1000.0).strftime("%Y-%m-%d")
                    except Exception:
                        spec["bios"]["releaseDate"] = "2025-01-01"
                elif isinstance(rel_date, str):
                    spec["bios"]["releaseDate"] = rel_date[:10]

            # 4. RAM Slots
            ram_raw = run_ps_json("Get-CimInstance Win32_PhysicalMemory | Select-Object DeviceLocator, Capacity, Speed, Manufacturer, PartNumber, SerialNumber | ConvertTo-Json")
            ram_items = normalize_list(ram_raw)
            slots = []
            total_bytes = 0
            for idx, r in enumerate(ram_items):
                cap = r.get("Capacity") or (8 * 1024**3)
                total_bytes += cap
                size_gb = int(round(cap / (1024**3)))
                speed = r.get("Speed") or 4800
                ram_type = "DDR5" if speed >= 4800 else "DDR4"
                slots.append({
                    "slot": r.get("DeviceLocator") or f"DIMM_{idx+1}",
                    "sizeGb": size_gb,
                    "type": ram_type,
                    "frequencyMhz": speed,
                    "manufacturer": (r.get("Manufacturer") or "Unknown").strip(),
                    "partNumber": (r.get("PartNumber") or "OEM-RAM").strip(),
                    "serialNumber": str(r.get("SerialNumber") or "").strip()
                })
            if slots:
                spec["ram"]["slots"] = slots
                spec["ram"]["totalGb"] = int(round(total_bytes / (1024**3)))

            # 5. Physical Disks
            disks_raw = run_ps_json("Get-PhysicalDisk | Select-Object FriendlyName, MediaType, BusType, OperationalStatus, HealthStatus, Size, SerialNumber | ConvertTo-Json")
            if not disks_raw:
                disks_raw = run_ps_json("Get-CimInstance Win32_DiskDrive | Select-Object Model, InterfaceType, Size, SerialNumber, MediaType | ConvertTo-Json")
            
            disk_items = normalize_list(disks_raw)
            disks = []
            for idx, d in enumerate(disk_items):
                model = (d.get("FriendlyName") or d.get("Model") or f"Disk #{idx}").strip()
                size_bytes = d.get("Size") or (500 * 1000**3)
                size_gb = int(round(size_bytes / (1000**3)))
                serial = str(d.get("SerialNumber") or f"SN-{idx}").strip()
                bus = str(d.get("BusType") or d.get("InterfaceType") or "").upper()
                media = str(d.get("MediaType") or "").upper()
                
                # Determine accurate drive type
                if "NVME" in bus or "NVME" in model.upper() or "SNVS" in model.upper():
                    dtype = "NVMe SSD"
                elif "SSD" in media or "SSD" in model.upper() or "SOLID" in media:
                    dtype = "SATA SSD"
                else:
                    dtype = "HDD"

                disks.append({
                    "id": f"disk{idx}",
                    "model": model,
                    "serialNumber": serial,
                    "type": dtype,
                    "busType": bus or ("NVMe" if "NVMe" in dtype else "SATA"),
                    "capacityGb": size_gb,
                    "healthPercent": 100,
                    "temperatureC": 32 + (idx * 2)
                })
            if disks:
                spec["storage"] = disks

            # 6. GPUs (with nvidia-smi precision if available)
            gpus = []
            try:
                smi_out = subprocess.check_output(
                    "nvidia-smi --query-gpu=name,memory.total,driver_version,temperature.gpu --format=csv,noheader,nounits",
                    shell=True, text=True, timeout=2
                ).strip()
                for line in smi_out.splitlines():
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 3:
                        gname = parts[0]
                        vram_mb = int(parts[1]) if parts[1].isdigit() else 8192
                        drv = parts[2]
                        temp = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 35
                        gpus.append({
                            "model": gname,
                            "vramGb": int(round(vram_mb / 1024)),
                            "driverVersion": drv,
                            "temperatureC": temp,
                            "resolution": "2560 x 1440 @ 144Hz"
                        })
            except Exception:
                pass

            if not gpus:
                gpu_raw = run_ps_json("Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, AdapterRAM, VideoModeDescription | ConvertTo-Json")
                gpu_items = normalize_list(gpu_raw)
                for g in gpu_items:
                    name = (g.get("Name") or "").strip()
                    if not name:
                        continue
                    vram_bytes = g.get("AdapterRAM") or (8 * 1024**3)
                    vram_gb = int(round(vram_bytes / (1024**3)))
                    if vram_gb < 1:
                        vram_gb = 8
                    gpus.append({
                        "model": name,
                        "vramGb": vram_gb,
                        "driverVersion": g.get("DriverVersion") or "Latest",
                        "resolution": g.get("VideoModeDescription") or "1920 x 1080"
                    })
            if gpus:
                spec["gpus"] = gpus

            # 7. Network Adapters (filter physical & active interfaces)
            net_raw = run_ps_json("Get-NetAdapter | Select-Object Name, InterfaceDescription, MacAddress, LinkSpeed, Status, PhysicalMediaType | ConvertTo-Json")
            net_items = normalize_list(net_raw)
            net_list = []
            for n in net_items:
                mac_addr = n.get("MacAddress") or ""
                desc = n.get("InterfaceDescription") or n.get("Name") or ""
                status = n.get("Status") or "Disconnected"
                # Exclude virtual tunnels like TAP, Cisco, VPN, Hamachi from physical view unless active
                if mac_addr and desc and not ("WAN" in desc or "Fortinet" in desc or "Hamachi" in desc or "Cisco" in desc):
                    net_list.append({
                        "name": desc,
                        "mac": mac_addr,
                        "ip": ip if (mac_addr.replace("-", ":").upper() == mac.upper()) else "",
                        "speed": n.get("LinkSpeed") or "1 Gbps",
                        "status": status
                    })
            if net_list:
                spec["network"] = net_list
            else:
                spec["network"] = [{"name": "Realtek 2.5GbE", "mac": mac, "ip": ip, "speed": "2.5 Gbps", "status": "Up"}]

            # 8. Sound Devices
            sound_raw = run_ps_json("Get-CimInstance Win32_SoundDevice | Select-Object Name, Manufacturer | ConvertTo-Json")
            sound_items = normalize_list(sound_raw)
            spec["sound"] = [{"name": s.get("Name"), "manufacturer": s.get("Manufacturer") or "Realtek/NVIDIA"} for s in sound_items if s.get("Name")]

            # 9. PCI / PCIe Expansion Devices
            pci_raw = run_ps_json("Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPDeviceID -and $_.PNPDeviceID -like 'PCI*' -and $_.PNPClass -ne 'System' -and $_.PNPClass -ne 'Volume' -and $_.PNPClass -ne 'SoftwareDevice' } | Select-Object Name, DeviceID, PNPDeviceID, Manufacturer, Status | ConvertTo-Json")
            pci_items = normalize_list(pci_raw)
            pci_list = []
            for idx, p in enumerate(pci_items):
                pname = (p.get("Name") or "").strip()
                if not pname or any(ign in pname.lower() for ign in [
                    "мост", "bridge", "root port", "root complex", "dma", "direct memory",
                    "таймер", "timer", "interrupt", "чипсет", "chipset", "host cpu",
                    "system board", "системн", "espi", "spi flash", "management engine",
                    "smbus", "serial io", "sram", "iommu", "renoir", "cezanne", "rembrandt",
                    "phoenix", "raphael", "alder lake", "raptor lake", "meteor lake",
                    "amd-vi", "intel vt-d", "memory controller", "encryption controller",
                    "security processor", "psp", "ccp", "co-processor", "non-essential instrumentation"
                ]):
                    continue
                pci_list.append({
                    "id": f"pci-{idx}",
                    "name": pname,
                    "deviceId": p.get("DeviceID") or f"PCI-{idx}",
                    "pnpDeviceId": p.get("PNPDeviceID") or "",
                    "manufacturer": p.get("Manufacturer") or "",
                    "status": p.get("Status") or "OK"
                })
            spec["pciDevices"] = pci_list

        except Exception as e:
            print(f"[!] Warning collecting real hardware: {e}")

    elif platform.system() == "Linux":
        try:
            # 1. CPU Info
            if os.path.exists("/proc/cpuinfo"):
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if line.startswith("model name"):
                            spec["cpu"]["model"] = line.split(":", 1)[1].strip()
                            break

            # 2. Motherboard & BIOS
            try:
                if os.path.exists("/sys/class/dmi/id/board_vendor"):
                    with open("/sys/class/dmi/id/board_vendor", "r") as f:
                        spec["motherboard"]["manufacturer"] = f.read().strip() or "OEM"
                if os.path.exists("/sys/class/dmi/id/board_name"):
                    with open("/sys/class/dmi/id/board_name", "r") as f:
                        spec["motherboard"]["model"] = f.read().strip() or "Motherboard"
                if os.path.exists("/sys/class/dmi/id/bios_vendor"):
                    with open("/sys/class/dmi/id/bios_vendor", "r") as f:
                        spec["bios"]["vendor"] = f.read().strip() or "UEFI BIOS"
                if os.path.exists("/sys/class/dmi/id/bios_version"):
                    with open("/sys/class/dmi/id/bios_version", "r") as f:
                        spec["bios"]["version"] = f.read().strip() or "1.0"
            except Exception:
                pass

            # 3. Disks & Storage
            disks = []
            try:
                lsblk_out = subprocess.check_output(
                    "lsblk -b -d -o NAME,SIZE,TYPE,MODEL,SERIAL,ROTA -n",
                    shell=True, text=True, timeout=2
                )
                for idx, line in enumerate(lsblk_out.strip().splitlines()):
                    parts = line.split()
                    if len(parts) >= 3 and parts[2] == "disk":
                        dname = parts[0]
                        size_bytes = int(parts[1]) if parts[1].isdigit() else 0
                        size_gb = int(round(size_bytes / (1000**3))) if size_bytes else 500
                        model = " ".join(parts[3:5]) if len(parts) >= 4 else f"Disk /dev/{dname}"
                        serial = parts[5] if len(parts) >= 6 else f"SN-{idx}"
                        rota = parts[-1] if len(parts) >= 6 else "1"
                        dtype = "HDD" if rota == "1" else ("NVMe SSD" if "nvme" in dname else "SATA SSD")
                        disks.append({
                            "id": f"disk{idx}",
                            "model": model,
                            "serialNumber": serial,
                            "type": dtype,
                            "busType": "NVMe" if "nvme" in dname else "SATA",
                            "capacityGb": size_gb,
                            "healthPercent": 100,
                            "temperatureC": 35
                        })
            except Exception:
                pass

            if not disks:
                import shutil
                total, used, free = shutil.disk_usage("/")
                disks.append({
                    "id": "disk0",
                    "model": "Root Storage Drive",
                    "serialNumber": "ROOT-DISK-01",
                    "type": "SSD",
                    "busType": "SATA",
                    "capacityGb": int(round(total / (1000**3))),
                    "healthPercent": 100,
                    "temperatureC": 35
                })
            spec["storage"] = disks

            # 4. RAM / Memory Modules (dmidecode or /proc/meminfo)
            slots = []
            tot_ram_gb = 0
            try:
                # Discover dmidecode binary across standard system paths
                dmi_bin = None
                for p in ["/usr/sbin/dmidecode", "/sbin/dmidecode", "/usr/bin/dmidecode", "dmidecode"]:
                    if shutil.which(p) or os.path.exists(p):
                        dmi_bin = p
                        break
                if dmi_bin:
                    dmi_out = subprocess.check_output(f"{dmi_bin} -t memory 2>/dev/null || true", shell=True, text=True, timeout=3)
                    curr_dev = {}
                    for line in dmi_out.splitlines():
                        line = line.strip()
                        if line.startswith("Memory Device"):
                            if curr_dev and curr_dev.get("sizeGb", 0) > 0:
                                slots.append(curr_dev)
                            curr_dev = {"type": "DDR4", "speedMhz": 3200, "frequencyMhz": 3200, "manufacturer": "Kingston", "serialNumber": "", "partNumber": "KF432C16BB1/8"}
                        elif "Size:" in line:
                            val = line.split(":", 1)[1].strip()
                            if "MB" in val:
                                mb = int("".join(c for c in val.split()[0] if c.isdigit()) or "0")
                                if mb > 0:
                                    curr_dev["sizeGb"] = int(round(mb / 1024))
                                    curr_dev["capacityGb"] = curr_dev["sizeGb"]
                            elif "GB" in val:
                                gb = int("".join(c for c in val.split()[0] if c.isdigit()) or "0")
                                if gb > 0:
                                    curr_dev["sizeGb"] = gb
                                    curr_dev["capacityGb"] = gb
                        elif "Locator:" in line and "Bank" not in line:
                            curr_dev["slot"] = line.split(":", 1)[1].strip()
                        elif "Type:" in line and "Detail" not in line and "Error" not in line:
                            t_val = line.split(":", 1)[1].strip()
                            if t_val and "Unknown" not in t_val:
                                curr_dev["type"] = t_val
                        elif "Speed:" in line and "Configured" not in line:
                            sp_s = "".join([c for c in line.split(":", 1)[1] if c.isdigit()])
                            if sp_s:
                                curr_dev["frequencyMhz"] = int(sp_s)
                                curr_dev["speedMhz"] = int(sp_s)
                        elif "Manufacturer:" in line:
                            m_val = line.split(":", 1)[1].strip()
                            if m_val and "Unknown" not in m_val:
                                curr_dev["manufacturer"] = m_val
                        elif "Serial Number:" in line:
                            s_val = line.split(":", 1)[1].strip()
                            if s_val and "Unknown" not in s_val:
                                curr_dev["serialNumber"] = s_val
                        elif "Part Number:" in line:
                            p_val = line.split(":", 1)[1].strip()
                            if p_val and "Unknown" not in p_val:
                                curr_dev["partNumber"] = p_val
                    if curr_dev and curr_dev.get("sizeGb", 0) > 0:
                        slots.append(curr_dev)
            except Exception:
                pass

            # If dmidecode didn't find multiple slots, verify against /proc/meminfo
            try:
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            kb = int(line.split()[1])
                            tot_ram_gb = int(round(kb / (1024 * 1024)))
                            break
            except Exception:
                if not tot_ram_gb:
                    tot_ram_gb = 16

            if not slots:
                if tot_ram_gb >= 28:
                    slots.append({"slot": "DIMM_1", "sizeGb": 16, "capacityGb": 16, "type": "DDR4", "frequencyMhz": 3200, "manufacturer": "Kingston", "serialNumber": "SN-RAM-01", "partNumber": "KF432C16BB1/16"})
                    slots.append({"slot": "DIMM_2", "sizeGb": 16, "capacityGb": 16, "type": "DDR4", "frequencyMhz": 3200, "manufacturer": "Kingston", "serialNumber": "SN-RAM-02", "partNumber": "KF432C16BB1/16"})
                elif tot_ram_gb >= 14:
                    slots.append({"slot": "DIMM_1", "sizeGb": 8, "capacityGb": 8, "type": "DDR4", "frequencyMhz": 3200, "manufacturer": "Kingston", "serialNumber": "SN-RAM-01", "partNumber": "KF432C16BB1/8"})
                    slots.append({"slot": "DIMM_2", "sizeGb": 8, "capacityGb": 8, "type": "DDR4", "frequencyMhz": 3200, "manufacturer": "Kingston", "serialNumber": "SN-RAM-02", "partNumber": "KF432C16BB1/8"})
                else:
                    slots.append({"slot": "DIMM_1", "sizeGb": tot_ram_gb or 8, "capacityGb": tot_ram_gb or 8, "type": "DDR4", "frequencyMhz": 3200, "manufacturer": "Kingston", "serialNumber": "SN-RAM-01", "partNumber": f"KF432C16BB1/{tot_ram_gb or 8}"})

            total_calc_gb = sum(s.get("sizeGb", 0) for s in slots) or tot_ram_gb
            spec["ram"] = {
                "totalGb": total_calc_gb,
                "slots": slots
            }

            # 5. Network
            spec["network"] = [{
                "name": "Ethernet / Primary NIC",
                "mac": mac,
                "ip": ip,
                "speed": "1 Gbps",
                "status": "Up"
            }]

            # 6. PCI / PCIe Expansion Devices via lspci
            pci_list = []
            try:
                lspci_out = subprocess.check_output("lspci -mm 2>/dev/null || true", shell=True, text=True, timeout=3)
                for idx, line in enumerate(lspci_out.strip().splitlines()):
                    parts = [p.strip('"') for p in line.split('" "')]
                    if len(parts) >= 4:
                        full_name = f"{parts[2]} {parts[3]}".strip()
                        pclass = parts[1].strip()
                        if any(ign in full_name.lower() or ign in pclass.lower() for ign in [
                            "host bridge", "isa bridge", "pci bridge", "system peripheral", "signal processing",
                            "smbus", "dma controller", "timer", "iommu", "renoir", "cezanne", "rembrandt",
                            "phoenix", "raphael", "alder lake", "raptor lake", "meteor lake", "amd-vi",
                            "intel vt-d", "memory controller", "encryption controller", "security processor",
                            "psp", "ccp", "co-processor", "non-essential instrumentation"
                        ]):
                            continue
                        pci_list.append({
                            "id": f"pci-{idx}",
                            "name": full_name,
                            "slot": parts[0].replace('"', ''),
                            "class": parts[1],
                            "manufacturer": parts[2],
                            "status": "OK"
                        })
            except Exception:
                pass
            spec["pciDevices"] = pci_list

        except Exception as e:
            print(f"[!] Warning collecting Linux hardware: {e}")

    return spec

def execute_agent_update(server_base: str, cfg: dict, update_url: str = "", target_version: str = "2.4.0"):
    print(f"[*] Initiating remote agent update to v{target_version}...")
    device_id = cfg.get("device_id", "")
    prev_ver = AGENT_VERSION
    
    # 1. Report update in progress
    try:
        http_post(f"{server_base}/agents/update-status", {
            "deviceId": device_id,
            "status": "UPDATING",
            "previousVersion": prev_ver,
            "targetVersion": target_version,
            "details": f"Начата загрузка пакета обновления до v{target_version}"
        })
    except Exception as e:
        print(f"[!] Warning reporting update start: {e}")

    # 2. Download updated payload
    effective_url = update_url
    if not effective_url:
        root_server = server_base.replace("/api/v1", "").rstrip("/")
        effective_url = f"{root_server}/agent.py"

    print(f"[*] Downloading updated agent code from: {effective_url}")
    try:
        req = urllib.request.Request(effective_url, headers={"User-Agent": f"WorkstationAgent/{AGENT_VERSION}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            new_code = resp.read().decode("utf-8")
        
        if len(new_code) < 1000 or "Workstation Manager" not in new_code:
            raise ValueError("Downloaded payload is invalid or truncated")

        # 3. Validate python syntax
        compile(new_code, "<update_test>", "exec")

        # 4. Write to current script path
        script_path = os.path.abspath(sys.argv[0])
        backup_path = f"{script_path}.bak"
        tmp_path = f"{script_path}.new"

        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(new_code)

        try:
            if os.path.exists(backup_path):
                os.remove(backup_path)
            if os.path.exists(script_path):
                os.replace(script_path, backup_path)
            os.replace(tmp_path, script_path)
        except Exception:
            # Fallback direct write
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(new_code)

        print(f"[OK] Successfully wrote updated script to {script_path}")

        # 5. Report success
        try:
            http_post(f"{server_base}/agents/update-status", {
                "deviceId": device_id,
                "status": "SUCCESS",
                "previousVersion": prev_ver,
                "newVersion": target_version,
                "details": f"Агент успешно обновлен до версии v{target_version}"
            })
        except Exception as e:
            print(f"[!] Warning reporting update success: {e}")

        # 6. Restart agent process
        print("[*] Spawning updated agent process and exiting old instance...")
        python_exe = sys.executable
        if platform.system() == "Windows":
            subprocess.Popen([python_exe, script_path], creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        else:
            subprocess.Popen([python_exe, script_path])
        
        # Clean exit
        os._exit(0)

    except Exception as e:
        err_msg = str(e)
        print(f"[!] Agent update failed: {err_msg}")
        try:
            http_post(f"{server_base}/agents/update-status", {
                "deviceId": device_id,
                "status": "FAILED",
                "previousVersion": prev_ver,
                "targetVersion": target_version,
                "details": f"Ошибка при обновлении агента: {err_msg}",
                "error": err_msg
            })
        except Exception:
            pass

def get_rdp_sessions() -> list:
    sessions = []
    try:
        if platform.system() != "Windows":
            # Linux active user and remote session collection
            try:
                out = subprocess.check_output("who -u 2>/dev/null || true", shell=True, text=True, timeout=3)
                for idx, line in enumerate(out.strip().splitlines()):
                    parts = line.split()
                    if len(parts) >= 4:
                        uname = parts[0]
                        terminal = parts[1]
                        logon_date = f"{parts[2]} {parts[3]}"
                        idle = parts[4] if len(parts) > 4 and parts[4] != "." else "0 мин"
                        host = parts[-1].strip("()") if parts[-1].startswith("(") else "Local"
                        
                        state = "Active"
                        if idle != "." and idle != "0 мин" and idle != "old":
                            state = "Idle"
                        
                        sessions.append({
                            "id": idx + 1,
                            "username": uname,
                            "terminal": terminal,
                            "sessionName": f"pts/{terminal}",
                            "state": state,
                            "idleTime": idle,
                            "logonTime": logon_date,
                            "host": host
                        })
            except Exception:
                pass
        else:
            # Windows active session collection
            try:
                quser_out = subprocess.check_output("quser 2>nul || true", shell=True, text=True, timeout=3)
                lines = [l.strip() for l in quser_out.splitlines() if l.strip()]
                if len(lines) > 1:
                    for line in lines[1:]:
                        clean = line.lstrip(">").strip()
                        parts = clean.split()
                        if len(parts) >= 5:
                            uname = parts[0]
                            if parts[1].isdigit():
                                sid = int(parts[1])
                                sstate = parts[2]
                                idle = parts[3]
                                logon = " ".join(parts[4:])
                                sname = ""
                            else:
                                sname = parts[1]
                                sid = int(parts[2]) if parts[2].isdigit() else 0
                                sstate = parts[3]
                                idle = parts[4]
                                logon = " ".join(parts[5:])
                            
                            std_state = "Active"
                            if "disc" in sstate.lower() or "откл" in sstate.lower():
                                std_state = "Disconnected"
                            elif idle not in [".", "none", "нет", "00:00", "0 мин"]:
                                std_state = "Idle"
                            
                            sessions.append({
                                "id": sid,
                                "username": uname,
                                "sessionName": sname,
                                "state": std_state,
                                "idleTime": "0 мин" if idle in [".", "нет"] else idle,
                                "logonTime": logon
                            })
            except Exception:
                pass
    except Exception as e:
        print(f"[!] Warning collecting sessions: {e}")
    return sessions

def execute_power_command(action: str, extra: dict = None):
    act = (action or "").strip().upper()
    print(f"[*] Executing administrative action: {act}")
    is_win = platform.system() == "Windows"
    try:
        if act in ["REBOOT", "RESTART"]:
            if is_win:
                subprocess.Popen("shutdown /r /f /t 0", shell=True)
            else:
                subprocess.Popen("systemctl reboot || reboot || shutdown -r now", shell=True)
        elif act in ["SHUTDOWN", "FORCE_SHUTDOWN", "POWEROFF"]:
            if is_win:
                subprocess.Popen("shutdown /s /f /t 0", shell=True)
            else:
                subprocess.Popen("systemctl poweroff || poweroff || shutdown -h now", shell=True)
        elif act in ["SLEEP", "SUSPEND"]:
            if is_win:
                subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
            else:
                subprocess.Popen("systemctl suspend", shell=True)
        elif act in ["LOGOFF", "RESET_SESSION", "RDP_CLEANUP"]:
            sess_id = (extra or {}).get("sessionId")
            if is_win:
                if sess_id is not None:
                    subprocess.Popen(f"logoff {sess_id} || rwinsta {sess_id}", shell=True)
                else:
                    subprocess.Popen("shutdown /l /f", shell=True)
            else:
                if sess_id is not None:
                    subprocess.Popen(f"loginctl terminate-session {sess_id} || true", shell=True)
                else:
                    subprocess.Popen("pkill -KILL -u $(whoami) || true", shell=True)
        elif act in ["LOCK"]:
            if is_win:
                subprocess.Popen("rundll32.exe user32.dll,LockWorkStation", shell=True)
            else:
                subprocess.Popen("loginctl lock-session || true", shell=True)
    except Exception as e:
        print(f"[!] Error executing action {act}: {e}")

def main():
    print("==================================================")
    print(f" Workstation Manager Background Agent v{AGENT_VERSION}")
    print("==================================================")
    cfg = load_config()
    server_base = cfg["server_url"].rstrip("/")
    if not server_base.endswith("/api/v1"):
        server_base = f"{server_base}/api/v1"

    # 1. Check enrollment
    if not cfg.get("device_id"):
        hostname, ip, mac = get_primary_mac_and_ip()
        token = cfg.get("enrollment_token") or os.environ.get("WM_TOKEN", "")
        os_type, os_ver = get_os_info()
        print(f"[*] Enrolling device ({hostname} / {ip} / {mac} / {os_ver}) to server: {server_base}")
        try:
            res = http_post(f"{server_base}/agents/enroll", {
                "token": token,
                "hostname": hostname,
                "ip": ip,
                "mac": mac,
                "osType": os_type,
                "osVersion": os_ver,
                "currentUser": get_current_user(),
                "agentVersion": AGENT_VERSION
            })
            cfg["device_id"] = res.get("deviceId", f"PC-{mac.replace(':', '')[-4:]}")
            cfg["agent_secret"] = res.get("agentSecret", "sec_live")
            save_config(cfg)
            print(f"[OK] Successfully enrolled! Device ID: {cfg['device_id']}")
        except Exception as e:
            print(f"[!] Enrollment failed: {e}. Retrying in 10 seconds...")
            time.sleep(10)
            return

    # 2. Send hardware inventory
    print("[*] Sending hardware inventory...")
    try:
        hw = collect_hardware()
        http_post(f"{server_base}/agents/inventory", {
            "deviceId": cfg["device_id"],
            "hardwareSpec": hw
        })
        print("[OK] Hardware inventory accepted.")
    except Exception as e:
        print(f"[!] Hardware report error: {e}")

    # 3. Start background UDP direct command listener (port 48123)
    def udp_listener_loop():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(("0.0.0.0", 48123))
            while True:
                data, addr = sock.recvfrom(1024)
                if data:
                    msg = data.decode("utf-8", errors="ignore").strip()
                    if msg.startswith("WM_CMD:"):
                        parts = msg.split(":")
                        if len(parts) >= 2:
                            cmd_act = parts[1].strip()
                            tgt_id = parts[2].strip() if len(parts) >= 3 else ""
                            tgt_mac = parts[3].strip() if len(parts) >= 4 else ""
                            tgt_host = parts[4].strip() if len(parts) >= 5 else ""
                            
                            my_id = (cfg.get("device_id") or "").upper()
                            _, _, my_mac = get_primary_mac_and_ip()
                            my_mac_clean = my_mac.replace(":", "").replace("-", "").upper()
                            tgt_mac_clean = tgt_mac.replace(":", "").replace("-", "").upper()
                            my_host = socket.gethostname().upper()
                            
                            matched = True
                            if tgt_id or tgt_mac or tgt_host:
                                matched = (
                                    (tgt_id and tgt_id.upper() == my_id) or
                                    (tgt_mac_clean and tgt_mac_clean == my_mac_clean) or
                                    (tgt_host and tgt_host.upper() == my_host)
                                )
                            if matched:
                                if cmd_act.upper() in ["UPDATE_AGENT", "UPGRADE_AGENT", "UPDATE"]:
                                    threading.Thread(target=execute_agent_update, args=(server_base, cfg), daemon=True).start()
                                else:
                                    execute_power_command(cmd_act)
        except Exception:
            pass

    t = threading.Thread(target=udp_listener_loop, daemon=True)
    t.start()

    # 4. Heartbeat loop
    print("[*] Entering live heartbeat & telemetry loop (30s interval)...")
    is_startup = True

    import signal
    def handle_shutdown(signum, frame):
        print("\n[*] Detected system shutdown / termination signal. Reporting to server...")
        try:
            http_post(f"{server_base}/agents/power-event", {
                "deviceId": cfg["device_id"],
                "action": "SHUTDOWN",
                "initiator": "Локальный пользователь (Завершение работы ОС)",
                "source": "LOCAL",
                "details": "Локальное выключение через ОС"
            })
        except Exception:
            pass
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)
    except Exception:
        pass

    last_ram_stick_count = -1
    last_ram_total_gb = -1
    last_pci_count = -1
    last_pci_sig = ""
    last_disk_count = -1
    last_gpu_count = -1
    last_net_count = -1

    while True:
        try:
            total_ram, ram_percent = get_memory_info()
            cpu_percent = get_cpu_usage()
            disk_percent = get_disk_info()
            user = get_current_user()
            uptime_str, uptime_sec, boot_time_iso = get_uptime_info()

            # Dynamic hardware scan
            hw = collect_hardware()
            ram_spec = hw.get("ram", {})
            ram_slots = ram_spec.get("slots", [])
            total_ram_gb = ram_spec.get("totalGb", total_ram)
            pci_devs = hw.get("pciDevices", [])
            pci_sig = ";".join(str(p.get("pnpDeviceId") or p.get("slot") or p.get("name")) for p in pci_devs)
            disk_count = len(hw.get("storage", []))
            gpu_count = len(hw.get("gpus", []))
            net_count = len(hw.get("network", []))

            if is_startup or \
               (last_ram_stick_count >= 0 and last_ram_stick_count != len(ram_slots)) or \
               (last_ram_total_gb >= 0 and last_ram_total_gb != total_ram_gb) or \
               (last_pci_count >= 0 and last_pci_count != len(pci_devs)) or \
               (last_pci_sig != "" and last_pci_sig != pci_sig) or \
               (last_disk_count >= 0 and last_disk_count != disk_count) or \
               (last_gpu_count >= 0 and last_gpu_count != gpu_count) or \
               (last_net_count >= 0 and last_net_count != net_count):
                try:
                    http_post(f"{server_base}/agents/inventory", {
                        "deviceId": cfg["device_id"],
                        "hardwareSpec": hw
                    })
                    print(f"[*] Hardware inventory updated: {total_ram_gb} GB RAM, {len(pci_devs)} PCI, {disk_count} Disks, {gpu_count} GPUs")
                except Exception as inv_e:
                    print(f"[!] Hardware inventory report error: {inv_e}")

            last_ram_stick_count = len(ram_slots)
            last_ram_total_gb = total_ram_gb
            last_pci_count = len(pci_devs)
            last_pci_sig = pci_sig
            last_disk_count = disk_count
            last_gpu_count = gpu_count
            last_net_count = net_count

            os_type, os_ver = get_os_info()

            resp = http_post(f"{server_base}/agents/heartbeat", {
                "deviceId": cfg["device_id"],
                "cpuPercent": cpu_percent,
                "ramPercent": ram_percent,
                "diskPercent": disk_percent,
                "totalRamGb": total_ram_gb,
                "ramSlots": ram_slots,
                "ramModulesCount": len(ram_slots),
                "hardwareSpec": hw,
                "pciDevices": pci_devs,
                "gpus": hw.get("gpus", []),
                "storage": hw.get("storage", []),
                "network": hw.get("network", []),
                "currentUser": user,
                "uptime": uptime_str,
                "uptimeSeconds": uptime_sec,
                "bootTime": boot_time_iso,
                "osType": os_type,
                "osVersion": os_ver,
                "agentVersion": AGENT_VERSION,
                "isStartup": is_startup,
                "rdpSessions": get_rdp_sessions(),
                "processes": get_top_processes()
            })
            print(f"[Heartbeat] CPU: {cpu_percent}% | RAM: {ram_percent}% ({total_ram_gb} GB, {len(ram_slots)} slots) | PCI: {len(pci_devs)} | User: {user} | v{AGENT_VERSION}")
            is_startup = False

            if resp and isinstance(resp, dict):
                if resp.get("heartbeatInterval"):
                    cfg["heartbeat_interval_seconds"] = int(resp.get("heartbeatInterval"))
                
                # Automatic OTA self-update if server advertises newer version
                latest_srv_ver = resp.get("latestVersion") or resp.get("targetVersion")
                if latest_srv_ver and latest_srv_ver != AGENT_VERSION:
                    print(f"[*] Auto-update triggered by heartbeat: v{AGENT_VERSION} -> v{latest_srv_ver}")
                    execute_agent_update(server_base, cfg, target_version=latest_srv_ver)

                for cmd in resp.get("pendingCommands", []):
                    if isinstance(cmd, dict) and cmd.get("action"):
                        c_act = cmd.get("action", "").upper()
                        if c_act in ["UPDATE_AGENT", "UPGRADE_AGENT", "UPDATE"]:
                            t_ver = cmd.get("targetVersion") or latest_srv_ver or "2.5.0"
                            u_url = cmd.get("updateUrl") or ""
                            execute_agent_update(server_base, cfg, update_url=u_url, target_version=t_ver)
                        else:
                            execute_power_command(c_act, extra=cmd)
        except Exception as e:
            print(f"[Heartbeat Error] {e}")

        time.sleep(cfg.get("heartbeat_interval_seconds", 30))

if __name__ == "__main__":
    main()
