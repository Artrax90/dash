import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.app.core.config import settings

SCOPE_POLICIES_FILE = os.path.join(settings.DATA_DIR, 'scope_alert_policies.json')
BACKUP_SCOPE_POLICIES_FILE = os.path.join(settings.DATA_DIR, 'scope_alert_policies.backup.json')

def get_default_policy() -> Dict[str, Any]:
    return {
        'mode': 'Full',
        'events': {
            'hardwareChanges': True,
            'hwDisks': True,
            'usbStorage': False,
            'remoteDisplayAdapter': False,
            'hwNetwork': True,
            'powerStateFailed': True,
            'morningWakeFailed': True,
            'eveningShutdownFailed': True,
            'agentDisconnect': True,
            'agentOnline': True,
            'rdpSessionTimeout': True,
            'rdpLogon': False,
            'highCpuUsage': True,
            'highRamUsage': True,
            'highDiskUsage': True,
        },
        'thresholds': {
            'cpuPercent': 90,
            'ramPercent': 85,
            'diskPercent': 90,
            'rdpIdleMinutes': 30,
        },
        'notifyChannels': {
            'webUi': True,
            'telegram': True,
        },
        'source': 'global',
        'sourceName': 'По умолчанию',
        'isInherited': True
    }

def canonicalize_scope_key(scope: str) -> str:
    if not scope:
        return ''
    scope = scope.strip()
    if ':' in scope:
        prefix, rest = scope.split(':', 1)
        return f'{prefix.strip().lower()}:{rest.strip()}'
    return scope

def load_all_scope_policies() -> Dict[str, Dict[str, Any]]:
    if os.path.exists(SCOPE_POLICIES_FILE):
        try:
            with open(SCOPE_POLICIES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            print(f'[scope_policy_service] Error loading policies: {e}')

    if os.path.exists(BACKUP_SCOPE_POLICIES_FILE):
        try:
            with open(BACKUP_SCOPE_POLICIES_FILE, 'r', encoding='utf-8') as bf:
                data = json.load(bf)
                if isinstance(data, dict):
                    save_all_scope_policies(data)
                    return data
        except Exception:
            pass

    return {}

def save_all_scope_policies(policies: Dict[str, Dict[str, Any]]):
    try:
        os.makedirs(settings.DATA_DIR, exist_ok=True)
        tmp_file = SCOPE_POLICIES_FILE + '.tmp'
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(policies, f, ensure_ascii=False, indent=2)
        if os.path.exists(SCOPE_POLICIES_FILE):
            os.replace(tmp_file, SCOPE_POLICIES_FILE)
        else:
            os.rename(tmp_file, SCOPE_POLICIES_FILE)
        if policies:
            try:
                with open(BACKUP_SCOPE_POLICIES_FILE, 'w', encoding='utf-8') as bf:
                    json.dump(policies, bf, ensure_ascii=False, indent=2)
            except Exception:
                pass
    except Exception as e:
        print(f'[scope_policy_service] Error saving policies: {e}')

def normalize_scope_lookup_keys(scope: str) -> List[str]:
    if not scope:
        return []
    s = scope.strip()
    keys = []
    prefix = ""
    clean = s
    if ":" in s:
        p, rest = s.split(":", 1)
        if p.lower() in ["building", "floor", "room", "group"]:
            prefix = p.lower()
            clean = rest.strip()

    slash_parts = [p.strip() for p in clean.split("/") if p.strip()]
    spaced_slash = " / ".join(slash_parts)
    tight_slash = "/".join(slash_parts)

    variants = [clean]
    if spaced_slash and spaced_slash != clean:
        variants.append(spaced_slash)
    if tight_slash and tight_slash != clean and tight_slash != spaced_slash:
        variants.append(tight_slash)

    for v in variants:
        if not v:
            continue
        keys.append(v)
        if prefix:
            keys.append(f"{prefix}:{v}")
        else:
            keys.append(f"group:{v}")
            keys.append(f"building:{v}")
            keys.append(f"floor:{v}")
            keys.append(f"room:{v}")

    seen = set()
    result = []
    for k in keys:
        lk = k.lower()
        if lk not in seen:
            seen.add(lk)
            result.append(k)
    return result

def get_scope_policy(scope: str) -> Optional[Dict[str, Any]]:
    policies = load_all_scope_policies()
    candidates = normalize_scope_lookup_keys(scope)
    # 1. Exact match
    for c in candidates:
        if c in policies:
            return policies[c]
    # 2. Case-insensitive match
    lower_map = {k.lower(): v for k, v in policies.items()}
    for c in candidates:
        if c.lower() in lower_map:
            return lower_map[c.lower()]
    return None

def save_scope_policy(scope: str, policy: Dict[str, Any]) -> Dict[str, Any]:
    key = canonicalize_scope_key(scope)
    policies = load_all_scope_policies()

    if isinstance(policy.get('policy'), dict):
        inner = policy['policy']
        policy = {**inner, 'scope': scope}

    raw_channels = policy.get('notifyChannels') or policy.get('notify_channels') or {}
    w = raw_channels.get('webUi') if raw_channels.get('webUi') is not None else raw_channels.get('web_ui', True)
    tg = raw_channels.get('telegram') if raw_channels.get('telegram') is not None else raw_channels.get('tg', True)

    canonical_record = {
        'scope': key,
        'mode': policy.get('mode', 'Custom'),
        'events': policy.get('events') or policy.get('events_config') or {},
        'thresholds': policy.get('thresholds') or {},
        'notifyChannels': {
            'webUi': bool(w),
            'web_ui': bool(w),
            'telegram': bool(tg),
            'tg': bool(tg),
        },
        'updatedAt': datetime.utcnow().isoformat() + 'Z'
    }

    policies[key] = canonical_record
    save_all_scope_policies(policies)
    return canonical_record

def delete_scope_policy(scope: str) -> bool:
    key = canonicalize_scope_key(scope)
    policies = load_all_scope_policies()
    deleted = False

    if key in policies:
        del policies[key]
        deleted = True
    else:
        l_key = key.lower()
        to_del = [k for k in policies if k.lower() == l_key]
        for k in to_del:
            del policies[k]
            deleted = True

    if deleted:
        save_all_scope_policies(policies)
    return deleted

def propagate_group_policy(
    scope: str,
    policy: Dict[str, Any],
    cascade: str = 'group',
    target_scopes: Optional[List[str]] = None
) -> List[str]:
    saved_scopes = []
    save_scope_policy(scope, policy)
    saved_scopes.append(canonicalize_scope_key(scope))

    if cascade in ['floors', 'rooms', 'custom'] and target_scopes:
        for t_scope in target_scopes:
            save_scope_policy(t_scope, policy)
            saved_scopes.append(canonicalize_scope_key(t_scope))

    return saved_scopes

def resolve_scope_effective_policy(
    scope: str,
    building: Optional[str] = None,
    floor: Optional[str] = None,
    room: Optional[str] = None
) -> Dict[str, Any]:
    clean_scope = scope.strip() if scope else ''
    if clean_scope.startswith(('building:', 'floor:', 'room:', 'group:')):
        clean_scope = clean_scope.split(':', 1)[1].strip()

    if not building and not floor and not room and '/' in clean_scope:
        parts = [p.strip() for p in clean_scope.split('/') if p.strip()]
        if len(parts) >= 3:
            building, floor, room = parts[0], parts[1], parts[2]
        elif len(parts) == 2:
            building, floor = parts[0], parts[1]

    # 1. Direct custom policy for this scope
    direct_pol = get_scope_policy(scope)
    if direct_pol and direct_pol.get('mode') != 'Inherit':
        return {
            'scope': scope,
            'mode': direct_pol.get('mode', 'Custom'),
            'events': direct_pol.get('events', {}),
            'thresholds': direct_pol.get('thresholds', {}),
            'notifyChannels': direct_pol.get('notifyChannels', {'webUi': True, 'telegram': True}),
            'hasCustomOverride': True,
            'isInherited': False,
            'source': 'direct',
            'sourceName': scope
        }

    # 2. Check room -> floor inheritance
    if room:
        f_candidates = []
        if building and floor:
            f_candidates.extend([
                f'floor:{building} / {floor}',
                f'floor:{building}/{floor}',
                f'{building} / {floor}',
                f'{building}/{floor}'
            ])
        if floor:
            f_candidates.extend([f'floor:{floor}', floor])
        for fc in f_candidates:
            f_pol = get_scope_policy(fc)
            if f_pol and f_pol.get('mode') != 'Inherit':
                src_name = f'{building} / {floor}' if building else floor
                return {
                    'scope': scope,
                    'mode': f_pol.get('mode', 'Custom'),
                    'events': f_pol.get('events', {}),
                    'thresholds': f_pol.get('thresholds', {}),
                    'notifyChannels': f_pol.get('notifyChannels', {'webUi': True, 'telegram': True}),
                    'hasCustomOverride': False,
                    'isInherited': True,
                    'source': 'floor',
                    'sourceName': src_name
                }

    # 3. Check floor / room -> building/group inheritance
    target_bld = building or clean_scope
    if target_bld:
        b_candidates = [
            f'building:{target_bld}',
            f'group:{target_bld}',
            target_bld
        ]
        for bc in b_candidates:
            b_pol = get_scope_policy(bc)
            if b_pol and b_pol.get('mode') != 'Inherit':
                return {
                    'scope': scope,
                    'mode': b_pol.get('mode', 'Custom'),
                    'events': b_pol.get('events', {}),
                    'thresholds': b_pol.get('thresholds', {}),
                    'notifyChannels': b_pol.get('notifyChannels', {'webUi': True, 'telegram': True}),
                    'hasCustomOverride': False,
                    'isInherited': True,
                    'source': 'building',
                    'sourceName': target_bld
                }

    # 4. Global default
    def_pol = get_default_policy()
    return {
        'scope': scope,
        'mode': def_pol['mode'],
        'events': def_pol['events'],
        'thresholds': def_pol['thresholds'],
        'notifyChannels': def_pol['notifyChannels'],
        'hasCustomOverride': False,
        'isInherited': True,
        'source': 'global',
        'sourceName': 'По умолчанию'
    }

def resolve_effective_policy(device_obj: Any, device_policy: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if isinstance(device_obj, dict):
        d_id = str(device_obj.get('id') or device_obj.get('deviceId') or '')
        d_host = str(device_obj.get('hostname') or '')
        d_grp = str(device_obj.get('group') or device_obj.get('group_name') or '')
        d_bld = str(device_obj.get('building') or '')
        d_flr = str(device_obj.get('floor') or '')
        d_rm = str(device_obj.get('room') or '')
    else:
        d_id = str(getattr(device_obj, 'id', '') or '')
        d_host = str(getattr(device_obj, 'hostname', '') or '')
        d_grp = str(getattr(device_obj, 'group_name', '') or getattr(device_obj, 'group', '') or '')
        d_bld = str(getattr(device_obj, 'building', '') or '')
        d_flr = str(getattr(device_obj, 'floor', '') or '')
        d_rm = str(getattr(device_obj, 'room', '') or '')

    # Auto-extract hierarchical components if group string has slashes
    if d_grp and '/' in d_grp:
        parts = [p.strip() for p in d_grp.split('/') if p.strip()]
        if len(parts) >= 3:
            if not d_bld: d_bld = parts[0]
            if not d_flr: d_flr = parts[1]
            if not d_rm: d_rm = parts[2]
        elif len(parts) == 2:
            if not d_bld: d_bld = parts[0]
            if not d_flr: d_flr = parts[1]

    if device_policy:
        d_mode = device_policy.get('mode')
        if d_mode and d_mode != 'Inherit':
            ch = device_policy.get('notifyChannels') or device_policy.get('notify_channels') or {}
            w = ch.get('webUi') if ch.get('webUi') is not None else ch.get('web_ui', True)
            tg = ch.get('telegram') if ch.get('telegram') is not None else ch.get('tg', True)
            return {
                'mode': d_mode,
                'events': device_policy.get('events') or device_policy.get('events_config') or {},
                'thresholds': device_policy.get('thresholds') or {},
                'notifyChannels': {'webUi': bool(w), 'web_ui': bool(w), 'telegram': bool(tg), 'tg': bool(tg)},
                'source': 'device',
                'sourceName': d_host or d_id,
                'isInherited': False
            }

    room_candidates = []
    if d_bld and d_flr and d_rm:
        room_candidates.extend([
            f'room:{d_bld} / {d_flr} / {d_rm}',
            f'room:{d_bld}/{d_flr}/{d_rm}',
            f'{d_bld} / {d_flr} / {d_rm}',
            f'{d_bld}/{d_flr}/{d_rm}'
        ])
    if d_grp and d_flr and d_rm:
        room_candidates.extend([
            f'room:{d_grp} / {d_flr} / {d_rm}',
            f'{d_grp} / {d_flr} / {d_rm}'
        ])
    if d_rm:
        room_candidates.extend([f'room:{d_rm}', d_rm])

    for rc in room_candidates:
        pol = get_scope_policy(rc)
        if pol and pol.get('mode') != 'Inherit':
            prefix_part = (d_bld + ' / ') if d_bld else ''
            flr_part = (d_flr + ' / ') if d_flr else ''
            return {
                'mode': pol.get('mode', 'Custom'),
                'events': pol.get('events', {}),
                'thresholds': pol.get('thresholds', {}),
                'notifyChannels': pol.get('notifyChannels', {'webUi': True, 'telegram': True}),
                'source': 'room',
                'sourceName': f'{prefix_part}{flr_part}{d_rm}',
                'isInherited': True
            }

    floor_candidates = []
    if d_bld and d_flr:
        floor_candidates.extend([
            f'floor:{d_bld} / {d_flr}',
            f'floor:{d_bld}/{d_flr}',
            f'{d_bld} / {d_flr}',
            f'{d_bld}/{d_flr}'
        ])
    if d_grp and d_flr:
        floor_candidates.extend([
            f'floor:{d_grp} / {d_flr}',
            f'{d_grp} / {d_flr}'
        ])
    if d_flr:
        floor_candidates.extend([f'floor:{d_flr}', d_flr])

    for fc in floor_candidates:
        pol = get_scope_policy(fc)
        if pol and pol.get('mode') != 'Inherit':
            prefix_part = (d_bld + ' / ') if d_bld else ''
            return {
                'mode': pol.get('mode', 'Custom'),
                'events': pol.get('events', {}),
                'thresholds': pol.get('thresholds', {}),
                'notifyChannels': pol.get('notifyChannels', {'webUi': True, 'telegram': True}),
                'source': 'floor',
                'sourceName': f'{prefix_part}{d_flr}',
                'isInherited': True
            }

    group_candidates = []
    if d_bld:
        group_candidates.extend([f'building:{d_bld}', f'group:{d_bld}', d_bld])
    if d_grp:
        for g in d_grp.split(','):
            g_clean = g.strip()
            if g_clean:
                group_candidates.extend([f'group:{g_clean}', g_clean])
                if '/' in g_clean:
                    top_bld = g_clean.split('/')[0].strip()
                    if top_bld:
                        group_candidates.extend([f'building:{top_bld}', f'group:{top_bld}', top_bld])

    for gc in group_candidates:
        pol = get_scope_policy(gc)
        if pol and pol.get('mode') != 'Inherit':
            g_name = gc.split(':', 1)[1] if ':' in gc else gc
            return {
                'mode': pol.get('mode', 'Custom'),
                'events': pol.get('events', {}),
                'thresholds': pol.get('thresholds', {}),
                'notifyChannels': pol.get('notifyChannels', {'webUi': True, 'telegram': True}),
                'source': 'group',
                'sourceName': g_name,
                'isInherited': True
            }

    return get_default_policy()
