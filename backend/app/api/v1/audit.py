import json
import os
from datetime import datetime, timezone
from fastapi import APIRouter
from typing import Dict, Any, List, Optional
from backend.app.core.config import settings

router = APIRouter(prefix="/audit", tags=["audit"])

AUDIT_FILE = os.path.join(settings.DATA_DIR, "audit_logs.json")

def load_audit_logs() -> List[Dict[str, Any]]:
    if os.path.exists(AUDIT_FILE):
        try:
            with open(AUDIT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            print(f"Error reading audit logs: {e}")
    return []

def save_audit_logs(logs: List[Dict[str, Any]]):
    try:
        os.makedirs(settings.DATA_DIR, exist_ok=True)
        tmp_file = AUDIT_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(logs[:2000], f, ensure_ascii=False, indent=2)
        if os.path.exists(AUDIT_FILE):
            os.replace(tmp_file, AUDIT_FILE)
        else:
            os.rename(tmp_file, AUDIT_FILE)
    except Exception as e:
        print(f"Error saving audit logs: {e}")

def record_audit(user: str, action: str, target: str, result: str = "SUCCESS", details: str = "", device_name: Optional[str] = None) -> Dict[str, Any]:
    logs = load_audit_logs()
    now_utc = datetime.now(timezone.utc)
    iso_time = now_utc.isoformat()
    
    target_display = device_name or target or "Fleet"
    
    entry = {
        "id": f"AUD-{int(now_utc.timestamp() * 1000)}",
        "timestamp": iso_time,
        "user": user or "Система",
        "action": action.upper(),
        "target": target_display,
        "result": result.upper(),
        "details": details or "",
    }
    logs.insert(0, entry)
    save_audit_logs(logs)
    return entry

@router.get("")
async def list_audit_logs():
    return load_audit_logs()

