from fastapi import APIRouter, HTTPException, Request
from typing import List, Dict, Any, Optional
import json
import os
import sqlite3
from backend.app.core.config import settings

router = APIRouter(prefix="/groups", tags=["groups"])

GROUPS_FILE = os.path.join(settings.DATA_DIR, "groups.json")

def unassign_devices_by_scope(building: Optional[str] = None, floor: Optional[str] = None, room: Optional[str] = None, group_name: Optional[str] = None):
    possible_paths = [
        os.path.join(settings.DATA_DIR, "workstation_manager.db"),
        os.path.join(os.getcwd(), "data", "workstation_manager.db"),
        os.path.join(os.getcwd(), "workstation_manager.db")
    ]
    for db_path in possible_paths:
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT id, group_name, building, floor, room FROM devices")
                rows = cursor.fetchall()

                for r in rows:
                    dev_id = r["id"]
                    curr_grp = r["group_name"] or ""
                    curr_b = r["building"] or ""
                    curr_f = r["floor"] or ""
                    curr_r = r["room"] or ""

                    grps = [g.strip() for g in curr_grp.split(",") if g.strip()]
                    should_update = False
                    new_b = curr_b
                    new_f = curr_f
                    new_r = curr_r

                    # Match by room
                    if building and floor and room:
                        if (curr_b.lower() == building.lower() and curr_f.lower() == floor.lower() and curr_r.lower() == room.lower()) or (group_name and any(g.lower() == group_name.lower() for g in grps)):
                            new_r = ""
                            path = f"{building} / {floor} / {room}".lower()
                            grps = [g for g in grps if g.lower() != path and (not group_name or g.lower() != group_name.lower())]
                            should_update = True

                    # Match by floor
                    elif building and floor:
                        if curr_b.lower() == building.lower() and curr_f.lower() == floor.lower():
                            new_f = ""
                            new_r = ""
                            prefix = f"{building} / {floor} /".lower()
                            grps = [g for g in grps if not g.lower().startswith(prefix)]
                            should_update = True

                    # Match by building
                    elif building:
                        if curr_b.lower() == building.lower():
                            new_b = ""
                            new_f = ""
                            new_r = ""
                            prefix = f"{building} /".lower()
                            grps = [g for g in grps if not g.lower().startswith(prefix)]
                            should_update = True

                    # Match solely by group_name
                    elif group_name:
                        matched = any(g.lower() == group_name.lower() for g in grps)
                        if matched:
                            grps = [g for g in grps if g.lower() != group_name.lower()]
                            should_update = True

                    if should_update:
                        new_grp_str = ", ".join(grps) if grps else "Default"
                        cursor.execute(
                            "UPDATE devices SET group_name = ?, building = ?, floor = ?, room = ? WHERE id = ?",
                            (new_grp_str, new_b, new_f, new_r, dev_id)
                        )

                conn.commit()
                conn.close()
                break
            except Exception as e:
                print(f"Error unassigning devices in {db_path}: {e}")

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

from backend.app.api.v1.users import get_current_user_from_request, is_superadmin_role, is_fleetadmin_role, can_manage_fleet_groups
from backend.app.core.scope import (
    is_path_in_scope,
    is_device_in_scope,
    is_group_in_scope,
    is_building_in_scope,
    is_floor_in_scope,
    is_room_in_scope
)

@router.get("", response_model=List[Dict[str, Any]])
async def list_groups(request: Request):
    u = get_current_user_from_request(request)
    if u and not is_superadmin_role(u.get("role")) and u.get("scope") != "Все устройства" and u.get("allowedGroups"):
        allowed = u.get("allowedGroups", [])
        return [g for g in groups_store if is_group_in_scope(g, allowed)]
    return groups_store

@router.get("/buildings", response_model=List[Dict[str, Any]])
async def list_buildings(request: Request):
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

    u = get_current_user_from_request(request)
    if u and not is_superadmin_role(u.get("role")) and u.get("scope") != "Все устройства" and u.get("allowedGroups"):
        allowed = u.get("allowedGroups", [])
        return [b for b in buildings_store if is_building_in_scope(b["name"], allowed)]
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
async def get_groups_hierarchy(request: Request):
    u = get_current_user_from_request(request)
    allowed = None
    if u and not is_superadmin_role(u.get("role")) and u.get("scope") != "Все устройства" and u.get("allowedGroups"):
        allowed = u.get("allowedGroups", [])

    buildings_map: Dict[str, Dict[str, Any]] = {}
    
    # 1. Pre-populate from configured buildings so all floors exist (filtered by scope)
    for b in buildings_store:
        b_name = b["name"]
        if allowed and not is_building_in_scope(b_name, allowed):
            continue

        floors_dict = {}
        for f_name in b.get("floors", []):
            if allowed and not is_floor_in_scope(b_name, f_name, allowed):
                continue
            floors_dict[f_name] = {"name": f_name, "building": b_name, "rooms": []}

        buildings_map[b_name] = {
            "name": b_name,
            "color": b.get("color", "blue"),
            "floors": floors_dict
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

        # Scope check
        if allowed:
            if not is_room_in_scope(b, f, r, allowed) and not is_group_in_scope(g, allowed):
                continue

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

    # Convert to clean nested arrays (omit empty buildings if restricted)
    result = []
    for b_name, b_data in buildings_map.items():
        floors_list = []
        for f_name, f_data in b_data["floors"].items():
            if allowed and not f_data["rooms"] and not is_floor_in_scope(b_name, f_name, allowed):
                continue
            floors_list.append({
                "name": f_name,
                "building": b_name,
                "rooms": f_data["rooms"]
            })
        if allowed and not floors_list and not is_building_in_scope(b_name, allowed):
            continue
        result.append({
            "name": b_name,
            "color": b_data.get("color", "blue"),
            "floors": floors_list
        })
    return result

@router.post("", response_model=Dict[str, Any])
async def create_group(payload: Dict[str, Any], request: Request):
    u = get_current_user_from_request(request)
    if u:
        if u.get("role") in ["Наблюдатель", "Observer"]:
            raise HTTPException(status_code=403, detail="Роль «Наблюдатель» имеет доступ только для чтения")
        if not can_manage_fleet_groups(u.get("role")):
            raise HTTPException(status_code=403, detail="Недостаточно прав для создания групп")
        if u.get("scope") != "Все устройства" and u.get("allowedGroups"):
            allowed = u.get("allowedGroups", [])
            b = str(payload.get("building") or "").strip()
            f = str(payload.get("floor") or "").strip()
            r = str(payload.get("room") or "").strip()
            raw_name = str(payload.get("name", "")).strip()
            check_p = f"{b} / {f} / {r}" if (b and f and r) else (raw_name or b)
            if not is_path_in_scope(check_p, allowed):
                raise HTTPException(
                    status_code=403,
                    detail=f"Отказ в доступе: вы можете создавать группы только в разрешенных вам разделах ({', '.join(allowed)})."
                )
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
        bld = deleted.get("building")
        flr = deleted.get("floor")
        rm = deleted.get("room")
        if bld and flr and rm:
            unassign_devices_by_scope(building=bld, floor=flr, room=rm, group_name=name)
        else:
            unassign_devices_by_scope(group_name=name)
        return {"status": "deleted", "group": deleted}
    unassign_devices_by_scope(group_name=name)
    return {"status": "not_found"}
