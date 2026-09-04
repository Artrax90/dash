# backend/app/core/scope.py
"""
Hierarchical RBAC Scope Resolution and Isolation Engine.
Supports matching by Building, Floor, Room, and Group paths across
the 3-level organization hierarchy (e.g. 'МНОК' -> 'МНОК / 1 этаж' -> 'МНОК / 1 этаж / 111').
"""
from typing import List, Dict, Any, Optional, Set

def is_path_in_scope(target_path: str, allowed_groups: Optional[List[str]]) -> bool:
    if not allowed_groups:
        return True
    clean_target = str(target_path or "").strip().lower()
    if not clean_target:
        return False
    for allowed in allowed_groups:
        a = str(allowed or "").strip().lower()
        if not a:
            continue
        if clean_target == a:
            return True
        if clean_target.startswith(a + " /") or clean_target.startswith(a + "/"):
            return True
        if a.startswith(clean_target + " /") or a.startswith(clean_target + "/"):
            return True
    return False

def is_device_in_scope(device: Dict[str, Any], allowed_groups: Optional[List[str]]) -> bool:
    if not allowed_groups:
        return True
    bld = str(device.get("building") or "").strip().lower()
    flr = str(device.get("floor") or "").strip().lower()
    rm = str(device.get("room") or "").strip().lower()
    grp = str(device.get("group") or device.get("group_name") or "").strip().lower()
    grps = [str(g).strip().lower() for g in device.get("groups", []) if g]

    all_paths: Set[str] = set()
    if grp:
        all_paths.add(grp)
        if not bld and "/" in grp:
            parts = [p.strip() for p in grp.split("/")]
            if len(parts) >= 3:
                bld, flr, rm = parts[0], parts[1], parts[2]
            elif len(parts) == 2:
                bld, rm = parts[0], parts[1]

    for g in grps:
        all_paths.add(g)

    if bld:
        all_paths.add(bld)
        if flr:
            all_paths.add(f"{bld} / {flr}")
            if rm:
                all_paths.add(f"{bld} / {flr} / {rm}")
        elif rm:
            all_paths.add(f"{bld} / {rm}")

    for allowed in allowed_groups:
        a = str(allowed or "").strip().lower()
        if not a:
            continue
        for p in all_paths:
            if p == a or p.startswith(a + " /") or p.startswith(a + "/"):
                return True
    return False

def is_group_in_scope(group: Dict[str, Any], allowed_groups: Optional[List[str]]) -> bool:
    if not allowed_groups:
        return True
    name = str(group.get("name") or "").strip().lower()
    bld = str(group.get("building") or "").strip().lower()
    flr = str(group.get("floor") or "").strip().lower()
    rm = str(group.get("room") or "").strip().lower()

    all_paths: Set[str] = set()
    if name:
        all_paths.add(name)
        if not bld and "/" in name:
            parts = [p.strip() for p in name.split("/")]
            if len(parts) >= 3:
                bld, flr, rm = parts[0], parts[1], parts[2]
            elif len(parts) == 2:
                bld, rm = parts[0], parts[1]

    if bld:
        all_paths.add(bld)
        if flr:
            all_paths.add(f"{bld} / {flr}")
            if rm:
                all_paths.add(f"{bld} / {flr} / {rm}")
        elif rm:
            all_paths.add(f"{bld} / {rm}")

    for allowed in allowed_groups:
        a = str(allowed or "").strip().lower()
        if not a:
            continue
        for p in all_paths:
            if p == a or p.startswith(a + " /") or p.startswith(a + "/") or a.startswith(p + " /") or a.startswith(p + "/"):
                return True
    return False

def is_building_in_scope(building_name: str, allowed_groups: Optional[List[str]]) -> bool:
    if not allowed_groups:
        return True
    b = str(building_name or "").strip().lower()
    if not b:
        return False
    for allowed in allowed_groups:
        a = str(allowed or "").strip().lower()
        if not a:
            continue
        if a == b or a.startswith(b + " /") or a.startswith(b + "/") or b.startswith(a + " /") or b.startswith(a + "/"):
            return True
    return False

def is_floor_in_scope(building_name: str, floor_name: str, allowed_groups: Optional[List[str]]) -> bool:
    if not allowed_groups:
        return True
    b = str(building_name or "").strip().lower()
    f = str(floor_name or "").strip().lower()
    f_path = f"{b} / {f}"
    for allowed in allowed_groups:
        a = str(allowed or "").strip().lower()
        if not a:
            continue
        if a == b or a == f_path or a.startswith(f_path + " /") or a.startswith(f_path + "/") or f_path.startswith(a + " /"):
            return True
    return False

def is_room_in_scope(building_name: str, floor_name: str, room_name: str, allowed_groups: Optional[List[str]]) -> bool:
    if not allowed_groups:
        return True
    b = str(building_name or "").strip().lower()
    f = str(floor_name or "").strip().lower()
    r = str(room_name or "").strip().lower()
    f_path = f"{b} / {f}"
    r_path = f"{f_path} / {r}" if (b and f and r) else f"{b} / {r}"
    for allowed in allowed_groups:
        a = str(allowed or "").strip().lower()
        if not a:
            continue
        if a == b or a == f_path or a == r_path or a == r:
            return True
    return False
