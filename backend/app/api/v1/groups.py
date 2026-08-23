from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional

router = APIRouter(prefix="/groups", tags=["groups"])

# Persistent in-memory storage of groups
groups_store: List[Dict[str, Any]] = [
    {"name": "Office", "desc": "Компьютеры главного офиса компании", "color": "blue", "schedule": "Office Working Day"},
    {"name": "Warehouse", "desc": "Терминалы логистического склада", "color": "orange", "schedule": "Warehouse Night Mode"},
    {"name": "Management", "desc": "Руководство и переговорные комнаты", "color": "green", "schedule": "Без расписания"},
    {"name": "Testing", "desc": "QA и тестовая лаборатория оборудования", "color": "purple", "schedule": "Testing Lab"},
    {"name": "Dev", "desc": "Рабочие станции разработчиков и дизайнеров", "color": "cyan", "schedule": "Dev Working Day"},
    {"name": "Accounting", "desc": "Бухгалтерия и финансовый отдел", "color": "slate", "schedule": "Без расписания"},
    {"name": "Servers", "desc": "Серверное оборудование и гипервизоры", "color": "red", "schedule": "Круглосуточно (24/7)"},
]

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
        return existing

    new_group = {
        "name": name,
        "desc": payload.get("desc", "Пользовательская группа рабочих станций"),
        "color": payload.get("color", "blue"),
        "schedule": payload.get("schedule", "Без расписания")
    }
    groups_store.append(new_group)
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
    return existing

@router.delete("/{name}")
async def delete_group(name: str):
    idx = next((i for i, g in enumerate(groups_store) if g["name"].lower() == name.lower()), None)
    if idx is not None:
        deleted = groups_store.pop(idx)
        return {"status": "deleted", "group": deleted}
    return {"status": "not_found"}
