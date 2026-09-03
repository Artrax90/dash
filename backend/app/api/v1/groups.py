from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
import json
import os
from backend.app.core.config import settings
from backend.app.db.session import SessionLocal
from backend.app.models.device import Device

router = APIRouter(prefix="/groups", tags=["groups"])

GROUPS_FILE = os.path.join(settings.DATA_DIR, "groups.json")

def unassign_devices_by_scope(building: Optional[str] = None, floor: Optional[str] = None, room: Optional[str] = None, group_name: Optional[str] = None):
    try:
        db = SessionLocal()
        query = db.query(Device)
        if group_name:
            devices = query.filter(Device.group_name == group_name).all()
            for d in devices:
                d.group_name = "Default"
                d.room = ""
        elif building and floor and room:
            devices = query.filter(Device.building == building, Device.floor == floor, Device.room == room).all()
            for d in devices:
                d.group_name = "Default"
                d.room = ""
        elif building and floor:
            devices = query.filter(Device.building == building, Device.floor == floor).all()
            for d in devices:
                d.group_name = "Default"
                d.floor = ""
                d.room = ""
        elif building:
            devices = query.filter(Device.building == building).all()
            for d in devices:
                d.group_name = "Default"
                d.building = ""
                d.floor = ""
                d.room = ""
        db.commit()
        db.close()
    except Exception as e:
        print(f"Error unassigning devices: {e}")

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

BACKUP_GROUPS_FILE = os.path.join(settings.DATA_DIR, "groups.backup.json")

def load_groups() -> List[Dict[str, Any]]:
    # 1. Try loading from main groups.json
    if os.path.exists(GROUPS_FILE):
        try:
            with open(GROUPS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    # Update backup if valid
                    try:
                        with open(BACKUP_GROUPS_FILE, "w", encoding="utf-8") as bf:
                            json.dump(data, bf, ensure_ascii=False, indent=2)
                    except Exception:
                        pass
                    return data
        except Exception as e:
            print(f"Error loading groups: {e}")

    # 2. Resilient fallback: Check backup if main groups.json was reset or lost
    if os.path.exists(BACKUP_GROUPS_FILE):
        try:
            with open(BACKUP_GROUPS_FILE, "r", encoding="utf-8") as bf:
                data = json.load(bf)
                if isinstance(data, list) and len(data) > 0:
                    save_groups(data)
                    return data
        except Exception:
            pass

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
        # Always mirror to resilient backup
        if groups:
            try:
                with open(BACKUP_GROUPS_FILE, "w", encoding="utf-8") as bf:
                    json.dump(groups, bf, ensure_ascii=False, indent=2)
            except Exception:
                pass
    except Exception as e:
        print(f"Error saving groups: {e}")

BUILDINGS_FILE = os.path.join(settings.DATA_DIR, "buildings.json")
BACKUP_BUILDINGS_FILE = os.path.join(settings.DATA_DIR, "buildings.backup.json")

def generate_building_floors(floors_count: int = 3, has_basement: bool = False, has_sub_floor: bool = False) -> List[str]:
    res = []
    if has_sub_floor:
        res.append("-1 этаж")
    if has_basement:
        res.append("Цоколь")
    count = max(1, min(100, int(floors_count or 1)))
    for i in range(1, count + 1):
        res.append(f"{i} этаж")
    return res

def get_default_buildings() -> List[Dict[str, Any]]:
    return [
        {
            "name": "Главный корпус",
            "color": "blue",
            "floorsCount": 3,
            "hasBasement": True,
            "hasSubFloor": False,
            "floors": generate_building_floors(3, True, False)
        },
        {
            "name": "Учебный корпус",
            "color": "purple",
            "floorsCount": 4,
            "hasBasement": False,
            "hasSubFloor": False,
            "floors": generate_building_floors(4, False, False)
        }
    ]

def load_buildings() -> List[Dict[str, Any]]:
    if os.path.exists(BUILDINGS_FILE):
        try:
            with open(BUILDINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception:
            pass
    if os.path.exists(BACKUP_BUILDINGS_FILE):
        try:
            with open(BACKUP_BUILDINGS_FILE, "r", encoding="utf-8") as bf:
                data = json.load(bf)
                if isinstance(data, list) and len(data) > 0:
                    save_buildings(data)
                    return data
        except Exception:
            pass
    defaults = get_default_buildings()
    save_buildings(defaults)
    return defaults

def save_buildings(buildings: List[Dict[str, Any]]):
    try:
        os.makedirs(settings.DATA_DIR, exist_ok=True)
        tmp_file = BUILDINGS_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(buildings, f, ensure_ascii=False, indent=2)
        if os.path.exists(BUILDINGS_FILE):
            os.replace(tmp_file, BUILDINGS_FILE)
        else:
            os.rename(tmp_file, BUILDINGS_FILE)
        if buildings:
            try:
                with open(BACKUP_BUILDINGS_FILE, "w", encoding="utf-8") as bf:
                    json.dump(buildings, bf, ensure_ascii=False, indent=2)
            except Exception:
                pass
    except Exception as e:
        print(f"Error saving buildings: {e}")

# Persistent groups and buildings storage
groups_store: List[Dict[str, Any]] = load_groups()
buildings_store: List[Dict[str, Any]] = load_buildings()

@router.get("", response_model=List[Dict[str, Any]])
async def list_groups():
    return groups_store

@router.get("/buildings", response_model=List[Dict[str, Any]])
async def list_buildings():
    # Sync with any new buildings mentioned in groups
    existing = {b["name"].lower() for b in buildings_store}
    changed = False
    for g in groups_store:
        b_name = g.get("building")
        if not b_name and "/" in g.get("name", ""):
            b_name = g["name"].split("/")[0].strip()
        if b_name and b_name != "Общие группы" and b_name.lower() not in existing:
            new_item = {
                "name": b_name,
                "color": "blue",
                "floorsCount": 3,
                "hasBasement": False,
                "hasSubFloor": False,
                "floors": generate_building_floors(3, False, False)
            }
            buildings_store.append(new_item)
            existing.add(b_name.lower())
            changed = True
    if changed:
        save_buildings(buildings_store)
    return buildings_store

@router.post("/buildings", response_model=Dict[str, Any])
async def create_or_update_building(payload: Dict[str, Any]):
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Название корпуса обязательно")
    
    color = str(payload.get("color") or "blue").strip()
    floors_count = int(payload.get("floorsCount") or 3)
    has_basement = bool(payload.get("hasBasement", False))
    has_sub_floor = bool(payload.get("hasSubFloor", False))
    floors = payload.get("floors") or generate_building_floors(floors_count, has_basement, has_sub_floor)
    
    item = {
        "name": name,
        "color": color,
        "floorsCount": floors_count,
        "hasBasement": has_basement,
        "hasSubFloor": has_sub_floor,
        "floors": floors
    }
    
    idx = next((i for i, b in enumerate(buildings_store) if b["name"].lower() == name.lower()), -1)
    if idx >= 0:
        buildings_store[idx] = item
    else:
        buildings_store.append(item)
    save_buildings(buildings_store)
    return item

@router.put("/buildings/{bld_name}", response_model=Dict[str, Any])
async def update_building(bld_name: str, payload: Dict[str, Any]):
    idx = next((i for i, b in enumerate(buildings_store) if b["name"].lower() == bld_name.lower()), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Корпус не найден")
    
    new_name = str(payload.get("name") or bld_name).strip()
    color = str(payload.get("color") or buildings_store[idx].get("color", "blue")).strip()
    floors_count = int(payload.get("floorsCount") or buildings_store[idx].get("floorsCount", 3))
    has_basement = bool(payload.get("hasBasement", buildings_store[idx].get("hasBasement", False)))
    has_sub_floor = bool(payload.get("hasSubFloor", buildings_store[idx].get("hasSubFloor", False)))
    floors = payload.get("floors") or generate_building_floors(floors_count, has_basement, has_sub_floor)

    updated_item = {
        "name": new_name,
        "color": color,
        "floorsCount": floors_count,
        "hasBasement": has_basement,
        "hasSubFloor": has_sub_floor,
        "floors": floors
    }
    buildings_store[idx] = updated_item
    save_buildings(buildings_store)

    # If name changed, rename in groups and devices
    if new_name.lower() != bld_name.lower():
        for g in groups_store:
            if g.get("building", "").lower() == bld_name.lower():
                g["building"] = new_name
                flr = g.get("floor", "")
                rm = g.get("room", "")
                if flr and rm:
                    g["name"] = f"{new_name} / {flr} / {rm}"
            elif g.get("name", "").startswith(f"{bld_name} /"):
                parts = [p.strip() for p in g["name"].split("/")]
                if len(parts) >= 3:
                    g["name"] = f"{new_name} / {parts[1]} / {parts[2]}"
        save_groups(groups_store)

        try:
            db = SessionLocal()
            devices = db.query(Device).filter(Device.building == bld_name).all()
            for d in devices:
                d.building = new_name
                if d.group_name and d.group_name.startswith(f"{bld_name} /"):
                    parts = [p.strip() for p in d.group_name.split("/")]
                    if len(parts) >= 3:
                        d.group_name = f"{new_name} / {parts[1]} / {parts[2]}"
            db.commit()
            db.close()
        except Exception as e:
            print(f"Error updating device building: {e}")

    return updated_item

@router.delete("/buildings/{bld_name}")
async def delete_building(bld_name: str):
    idx = next((i for i, b in enumerate(buildings_store) if b["name"].lower() == bld_name.lower()), -1)
    if idx >= 0:
        buildings_store.pop(idx)
        save_buildings(buildings_store)

    global groups_store
    groups_store = [
        g for g in groups_store
        if g.get("building", "").lower() != bld_name.lower()
        and not g.get("name", "").lower().startswith(f"{bld_name.lower()} /")
    ]
    save_groups(groups_store)
    unassign_devices_by_scope(building=bld_name)

    return {"status": "deleted", "building": bld_name}

@router.delete("/buildings/{bld_name}/floors/{flr_name}")
async def delete_floor(bld_name: str, flr_name: str):
    idx = next((i for i, b in enumerate(buildings_store) if b["name"].lower() == bld_name.lower()), -1)
    if idx >= 0:
        b = buildings_store[idx]
        b["floors"] = [f for f in b.get("floors", []) if f.lower() != flr_name.lower()]
        save_buildings(buildings_store)

    global groups_store
    groups_store = [
        g for g in groups_store
        if not (
            (g.get("building", "").lower() == bld_name.lower() and g.get("floor", "").lower() == flr_name.lower())
            or g.get("name", "").lower().startswith(f"{bld_name.lower()} / {flr_name.lower()} /")
        )
    ]
    save_groups(groups_store)
    unassign_devices_by_scope(building=bld_name, floor=flr_name)

    return {"status": "deleted", "building": bld_name, "floor": flr_name}

@router.get("/hierarchy")
async def get_groups_hierarchy():
    buildings_map: Dict[str, Dict[str, Any]] = {}
    
    # 1. Pre-populate from configured buildings so all floors exist
    for b in buildings_store:
        b_name = b["name"]
        buildings_map[b_name] = {
            "name": b_name,
            "color": b.get("color", "blue"),
            "floors": {f_name: {"name": f_name, "building": b_name, "rooms": []} for f_name in b.get("floors", [])}
        }

    # 2. Populate rooms from groups_store
    for g in groups_store:
        b = str(g.get("building") or "").strip()
        f = str(g.get("floor") or "").strip()
        r = str(g.get("room") or "").strip()
        name = g.get("name", "")

        # Auto-parse if not explicitly stored
        if (not b or not r) and "/" in name:
            parts = [p.strip() for p in name.split("/")]
            if len(parts) >= 3:
                b, f, r = parts[0], parts[1], parts[2]
            elif len(parts) == 2:
                b, r = parts[0], parts[1]

        if not b:
            b = "Общие группы"
        if not f:
            f = "1 этаж"
        if not r:
            r = name

        if b not in buildings_map:
            buildings_map[b] = {
                "name": b,
                "floors": {}
            }
        
        if f not in buildings_map[b]["floors"]:
            buildings_map[b]["floors"][f] = {
                "name": f,
                "building": b,
                "rooms": []
            }

        buildings_map[b]["floors"][f]["rooms"].append({
            "name": r,
            "fullName": name,
            "building": b,
            "floor": f,
            "desc": g.get("desc", ""),
            "color": g.get("color", "blue"),
            "schedule": g.get("schedule", "Без расписания")
        })

    # Convert to clean nested arrays
    result = []
    for b_name, b_data in buildings_map.items():
        floors_list = []
        for f_name, f_data in b_data["floors"].items():
            floors_list.append({
                "name": f_name,
                "building": b_name,
                "rooms": f_data["rooms"]
            })
        result.append({
            "name": b_name,
            "color": b_data.get("color", "blue"),
            "floors": floors_list
        })
    return result

@router.post("", response_model=Dict[str, Any])
async def create_group(payload: Dict[str, Any]):
    b = str(payload.get("building") or "").strip()
    f = str(payload.get("floor") or "").strip()
    r = str(payload.get("room") or "").strip()
    raw_name = str(payload.get("name", "")).strip()

    if b and f and r:
        name = raw_name or f"{b} / {f} / {r}"
    elif b and r:
        name = raw_name or f"{b} / {r}"
    else:
        name = raw_name

    if not name:
        raise HTTPException(status_code=400, detail="Group name is required")
    
    # Auto-parse if name has slashes and building wasn't set
    if not b and "/" in name:
        parts = [p.strip() for p in name.split("/")]
        if len(parts) >= 3:
            b, f, r = parts[0], parts[1], parts[2]
        elif len(parts) == 2:
            b, r = parts[0], parts[1]

    # Check if group already exists
    existing = next((g for g in groups_store if g["name"].lower() == name.lower()), None)
    if existing:
        # Update existing
        existing.update({
            "desc": payload.get("desc", existing.get("desc", "")),
            "color": payload.get("color", existing.get("color", "blue")),
            "schedule": payload.get("schedule", existing.get("schedule", "Без расписания")),
            "building": b or existing.get("building", ""),
            "floor": f or existing.get("floor", ""),
            "room": r or existing.get("room", "")
        })
        save_groups(groups_store)
        return existing

    new_group = {
        "name": name,
        "building": b,
        "floor": f,
        "room": r,
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
    if "building" in payload:
        existing["building"] = payload["building"]
    if "floor" in payload:
        existing["floor"] = payload["floor"]
    if "room" in payload:
        existing["room"] = payload["room"]

    # Re-sync if building/floor/room changed
    if existing.get("building") and existing.get("floor") and existing.get("room") and ("name" not in payload or not payload["name"]):
        existing["name"] = f"{existing['building']} / {existing['floor']} / {existing['room']}"

    save_groups(groups_store)
    return existing

@router.delete("/{name:path}")
async def delete_group(name: str):
    idx = next((i for i, g in enumerate(groups_store) if g["name"].lower() == name.lower()), None)
    if idx is not None:
        deleted = groups_store.pop(idx)
        save_groups(groups_store)
        unassign_devices_by_scope(group_name=name)
        return {"status": "deleted", "group": deleted}
    unassign_devices_by_scope(group_name=name)
    return {"status": "not_found"}
