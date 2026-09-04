import json
import os
from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, List
from pydantic import BaseModel
from backend.app.core.config import settings
from backend.app.api.v1.users import require_superadmin

router = APIRouter(prefix="/roles", tags=["roles"])

ROLES_FILE = os.path.join(settings.DATA_DIR, "roles.json")

def load_roles() -> List[Dict[str, Any]]:
    default = [
        {
            "id": "ROLE-01",
            "name": "Суперадминистратор",
            "description": "Полный неограниченный доступ ко всем рабочим станциям, железу, политикам и настройкам.",
            "isBuiltIn": True,
            "permissions": [
                "devices.view", "devices.create", "devices.edit", "devices.delete",
                "devices.wake", "devices.reboot", "devices.shutdown", "devices.force_shutdown",
                "sessions.view", "sessions.logoff", "monitoring.view", "alerts.view",
                "audit.view", "settings.edit", "hardware.baseline_edit", "agents.tokens_manage"
            ],
            "scopeType": "Все устройства",
            "scopeValues": [],
            "userCount": 1,
            "tone": "blue",
        },
        {
            "id": "ROLE-02",
            "name": "Администратор парка",
            "description": "Управление питанием, настройками устройств и мониторингом аппаратного обеспечения.",
            "isBuiltIn": False,
            "permissions": [
                "devices.view", "devices.create", "devices.edit",
                "devices.wake", "devices.reboot", "devices.shutdown",
                "sessions.view", "sessions.logoff", "monitoring.view", "alerts.view",
                "audit.view", "hardware.baseline_edit"
            ],
            "scopeType": "Все устройства",
            "scopeValues": [],
            "userCount": 1,
            "tone": "blue",
        },
        {
            "id": "ROLE-03",
            "name": "Дежурный оператор",
            "description": "Оперативное наблюдение, пробуждение рабочих станций и завершение сессий RDP.",
            "isBuiltIn": False,
            "permissions": [
                "devices.view", "devices.wake", "devices.reboot",
                "sessions.view", "sessions.logoff", "alerts.view"
            ],
            "scopeType": "Выбранные группы",
            "scopeValues": [],
            "userCount": 1,
            "tone": "green",
        },
        {
            "id": "ROLE-04",
            "name": "Наблюдатель",
            "description": "Только просмотр статусов и телеметрии станций без права отправки команд.",
            "isBuiltIn": False,
            "permissions": [
                "devices.view", "monitoring.view", "alerts.view", "audit.view"
            ],
            "scopeType": "Все устройства",
            "scopeValues": [],
            "userCount": 1,
            "tone": "slate",
        },
    ]
    if os.path.exists(ROLES_FILE):
        try:
            with open(ROLES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception:
            pass
    return default

def save_roles(roles: List[Dict[str, Any]]):
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    with open(ROLES_FILE, "w", encoding="utf-8") as f:
        json.dump(roles, f, ensure_ascii=False, indent=2)

@router.get("")
async def list_roles():
    return load_roles()

@router.post("")
async def create_role(payload: Dict[str, Any], request: Request):
    require_superadmin(request)
    roles = load_roles()
    new_role = {
        "id": f"ROLE-{len(roles) + 1:02d}",
        "name": payload.get("name", "Новая роль"),
        "description": payload.get("description", ""),
        "isBuiltIn": False,
        "permissions": payload.get("permissions", ["devices.view", "monitoring.view"]),
        "scopeType": payload.get("scopeType", "Все устройства"),
        "scopeValues": payload.get("scopeValues", []),
        "userCount": 0,
        "tone": payload.get("tone", "blue"),
    }
    roles.append(new_role)
    save_roles(roles)
    return new_role

@router.put("/{role_id_or_name}")
async def update_role(role_id_or_name: str, payload: Dict[str, Any], request: Request):
    require_superadmin(request)
    import urllib.parse
    target = urllib.parse.unquote(role_id_or_name).strip()
    roles = load_roles()
    for r in roles:
        if r.get("id", "").strip().lower() == target.lower() or r.get("name", "").strip().lower() == target.lower():
            if "name" in payload:
                r["name"] = payload["name"]
            if "description" in payload:
                r["description"] = payload["description"]
            if "permissions" in payload:
                r["permissions"] = payload["permissions"]
            if "scopeType" in payload:
                r["scopeType"] = payload["scopeType"]
            if "scopeValues" in payload:
                r["scopeValues"] = payload["scopeValues"]
            if "tone" in payload:
                r["tone"] = payload["tone"]
            save_roles(roles)
            return r
    # Upsert: if role not found by exact ID or name, create it
    new_role = {
        "id": f"ROLE-{len(roles) + 1:02d}",
        "name": payload.get("name") or target,
        "description": payload.get("description", ""),
        "isBuiltIn": False,
        "permissions": payload.get("permissions", ["devices.view", "monitoring.view"]),
        "scopeType": payload.get("scopeType", "Все устройства"),
        "scopeValues": payload.get("scopeValues", []),
        "userCount": 0,
        "tone": payload.get("tone", "blue"),
    }
    roles.append(new_role)
    save_roles(roles)
    return new_role

