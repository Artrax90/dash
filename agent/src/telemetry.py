import psutil
import platform
import os
from typing import Dict, Any, List
from datetime import datetime

class TelemetryCollector:
    @staticmethod
    def get_live_metrics() -> Dict[str, Any]:
        """
        Collect real-time CPU, RAM, Disk utilization, uptime, and user sessions.
        """
        uptime_sec = 0
        try:
            if platform.system() == "Windows":
                import ctypes
                kernel32 = ctypes.windll.kernel32
                tick_ms = kernel32.GetTickCount64()
                uptime_sec = int(tick_ms / 1000.0)
            else:
                with open("/proc/uptime", "r") as f:
                    uptime_sec = int(float(f.readline().split()[0]))
        except Exception:
            try:
                btime = psutil.boot_time()
                uptime_sec = int(datetime.now().timestamp() - btime)
            except Exception:
                uptime_sec = 0

        days = uptime_sec // 86400
        hours = (uptime_sec % 86400) // 3600
        mins = (uptime_sec % 3600) // 60
        if days > 0:
            uptime_str = f"{days}д {hours:02d}ч"
        elif hours > 0:
            uptime_str = f"{hours}ч {mins:02d}м"
        else:
            uptime_str = f"{mins}м" if mins > 0 else "Менее 1 мин"
        
        users = [u.name for u in psutil.users()]
        primary_user = users[0] if users else "—"

        boot_time_iso = None
        if uptime_sec > 0:
            try:
                from datetime import timedelta
                boot_time_iso = (datetime.utcnow() - timedelta(seconds=uptime_sec)).isoformat() + "Z"
            except Exception:
                pass

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "cpuPercent": int(psutil.cpu_percent(interval=0.5)),
            "ramPercent": int(psutil.virtual_memory().percent),
            "diskPercent": int(psutil.disk_usage('/').percent if platform.system() != 'Windows' else psutil.disk_usage('C:').percent),
            "uptime": uptime_str,
            "uptimeSeconds": uptime_sec,
            "bootTime": boot_time_iso,
            "currentUser": primary_user,
            "osType": platform.system(),
            "osVersion": f"{platform.system()} {platform.release()}",
            "rdpSessions": TelemetryCollector.get_rdp_sessions(),
        }

    @staticmethod
    def get_rdp_sessions() -> List[Dict[str, Any]]:
        """
        Query logged-in users / RDP sessions.
        """
        sessions = []
        try:
            for idx, user in enumerate(psutil.users()):
                sessions.append({
                    "id": idx + 1,
                    "username": user.name,
                    "state": "Active",
                    "terminal": user.terminal or "Console",
                    "started": datetime.fromtimestamp(user.started).strftime("%Y-%m-%d %H:%M"),
                })
        except Exception:
            pass
        return sessions
