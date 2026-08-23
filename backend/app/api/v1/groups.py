from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
import json
import os
from backend.app.core.config import settings

router = APIRouter(prefix="/groups", tags=["groups"])

GROUPS_FILE = os.path.join(settings.DATA_DIR, "groups.json")

def get_default_groups() -> List[Dict[str, Any]]:
    return [
        {"name": "Office", "desc": "Компьютеры главного офиса компании", "color": "blue", "schedule": "Office Working Day"},
        {"name": "Warehouse", "desc": "Терминалы логистического склада", "color": "orange", "schedule": "Warehouse Night Mode"},
        {"name": "Management", "desc": "Руководство и переговорные комнаты", "color": "green", "schedule": "Без расписания"},
        {"name": "Testing", "desc": "QA и тестовая лаборатория оборудования", "color": "purple", "schedule": "Testing Lab"},
        {"name": "Dev", "desc": "Рабочие станции разработчиков и дизайнеров", "color": "cyan", "schedule": "Dev Working Day"},
        {"name": "Accounting", "desc": "Бухгалтерия и финансовый отдел", "color": "slate", "schedule": "Без расписания"},
        {"name": "Servers", "desc": "Серверное оборудование и гипервизоры", "color": "red", "schedule": "Круглосуточно (24/7)"},
    ]

def load_groups() -> List[Dict[str, Any]]:
    if os.path.exists(GROUPS_FILE):
        try:
            with open(GROUPS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception as e:
            print(f"Error loading groups: {e}")
    defaults = get_default_groups()
    save_groups(defaults)
    return defaults

def save_groups(groups: List[Dict[str, Any]]):
    try:
        os.makedirs(settings.DATA_DIR, exist_ok=True)
        tmp_file = GROUPS_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(groups, f, ensure_ascii=False, indent=2)
        if os.path.exists(GROUPS_FILE):
            os.replace(tmp_file, GROUPS_FILE)
        else:
            os.rename(tmp_file, GROUPS_FILE)
    except Exception as e:
        print(f"Error saving groups: {e}")

# Persistent groups storage
groups_store: List[Dict[str, Any]] = load_groups()

@router.get("", response_model=List[Dict[str, Any]])
async def list_groups():
    return groups_store

@router.post("", response_model=Dict[str, Any])
async def create_group(payload: Dict[str, Any]):
    name = str(payload.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=400, detail="Group name is required")
    
    # Check if group already exists
    existing = next((g for g in groups_store if g["name"].lower() == name.lower()), None)
    if existing:
        # Update existing
        existing.update({
            "desc": payload.get("desc", existing.get("desc", "")),
            "color": payload.get("color", existing.get("color", "blue")),
            "schedule": payload.get("schedule", existing.get("schedule", "Без расписания"))
        })
        save_groups(groups_store)
        return existing

    new_group = {
        "name": name,
        "desc": payload.get("desc", "Пользовательская группа рабочих станций"),
        "color": payload.get("color", "blue"),
        "schedule": payload.get("schedule", "Без расписания")
    }
    groups_store.append(new_group)
    save_groups(groups_store)
    return new_group

@router.put("/{name}", response_model=Dict[str, Any])
async def update_group(name: str, payload: Dict[str, Any]):
    existing = next((g for g in groups_store if g["name"].lower() == name.lower()), None)
    if not existing:
        raise HTTPException(status_code=404, detail="Group not found")
    
    if "name" in payload and payload["name"].strip():
        existing["name"] = payload["name"].strip()
    if "desc" in payload:
        existing["desc"] = payload["desc"]
    if "color" in payload:
        existing["color"] = payload["color"]
    if "schedule" in payload:
        existing["schedule"] = payload["schedule"]
    save_groups(groups_store)
    return existing

@router.delete("/{name}")
async def delete_group(name: str):
    idx = next((i for i, g in enumerate(groups_store) if g["name"].lower() == name.lower()), None)
    if idx is not None:
        deleted = groups_store.pop(idx)
        save_groups(groups_store)
        return {"status": "deleted", "group": deleted}
    return {"status": "not_found"}
