import json
import os
from datetime import datetime, timezone
from fastapi import APIRouter
from typing import Dict, Any, List

router = APIRouter(prefix="/audit", tags=["audit"])

DATA_DIR = os.path.join(os.getcwd(), "data")
AUDIT_FILE = os.path.join(DATA_DIR, "audit_logs.json")

def load_audit_logs() -> List[Dict[str, Any]]:
    if os.path.exists(AUDIT_FILE):
        try:
            with open(AUDIT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []

def save_audit_logs(logs: List[Dict[str, Any]]):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(AUDIT_FILE, "w", encoding="utf-8") as f:
        json.dump(logs[:500], f, ensure_ascii=False, indent=2)

def record_audit(user: str, action: str, target: str, result: str = "SUCCESS", details: str = "") -> Dict[str, Any]:
    logs = load_audit_logs()
    entry = {
        "id": f"AUD-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
        "timestamp": datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M:%S"),
        "user": user or "System",
        "action": action.upper(),
        "target": target or "Fleet",
        "result": result,
        "details": details or "",
    }
    logs.insert(0, entry)
    save_audit_logs(logs)
    return entry

@router.get("")
async def list_audit_logs():
    return load_audit_logs()
