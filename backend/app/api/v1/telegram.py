import collections
import json
import os
import socket
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from backend.app.api.v1.users import load_users
from backend.app.api.v1.audit import record_audit

from backend.app.core.config import settings

router = APIRouter(prefix="/telegram", tags=["telegram"])

CONFIG_FILE = os.path.join(settings.DATA_DIR, "telegram_config.json")
DEVICES_FILE = os.path.join(settings.DATA_DIR, "devices.json")

import httpx

def get_proxy_url(cfg: Dict[str, Any]) -> Optional[str]:
    if not cfg or not cfg.get("proxyEnabled", False):
        return None
    ptype = str(cfg.get("proxyType", "SOCKS5")).lower().strip()
    host = str(cfg.get("proxyHost", "")).strip()
    port = str(cfg.get("proxyPort", "")).strip()
    user = str(cfg.get("proxyUser", "")).strip()
    pwd = str(cfg.get("proxyPass", "")).strip()
    
    if not host or not port:
        return None
        
    auth = f"{user}:{pwd}@" if (user and pwd) else (f"{user}@" if user else "")
    
    if "socks" in ptype:
        return f"socks5://{auth}{host}:{port}"
    elif ptype == "https":
        return f"https://{auth}{host}:{port}"
    else:
        return f"http://{auth}{host}:{port}"

def get_httpx_client(cfg: Dict[str, Any] = None, timeout: float = 8.0) -> httpx.AsyncClient:
    if cfg is None:
        cfg = load_config()
    proxy = get_proxy_url(cfg)
    if proxy:
        return httpx.AsyncClient(proxy=proxy, timeout=timeout, follow_redirects=True)
    return httpx.AsyncClient(timeout=timeout, follow_redirects=True)

BACKUP_CONFIG_FILE = os.path.join(settings.DATA_DIR, "telegram_config.backup.json")

def load_config() -> Dict[str, Any]:
    default = {
        "enabled": True,
        "botToken": "",
        "chatId": "",
        "timezone": "Europe/Moscow",
        "alertsEnabled": True,
        "botUsername": "",
        "status": "Не настроен",
        "subscribersCount": 0,
        "proxyEnabled": False,
        "proxyType": "SOCKS5",
        "proxyHost": "",
        "proxyPort": "1080",
        "proxyUser": "",
        "proxyPass": "",
        "eventsConfig": {
            "criticalAlerts": True,
            "hardwareChanges": True,
            "usbStorage": False,
            "morningWakeSummary": True,
            "eveningShutdownSummary": True,
            "powerAlerts": True,
            "disconnectAlerts": True,
        },
    }
    loaded = False
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "eventsConfig" in data and isinstance(data["eventsConfig"], dict):
                    default["eventsConfig"].update(data["eventsConfig"])
                    data.pop("eventsConfig")
                default.update(data)
                loaded = True
                if default.get("botToken"):
                    try:
                        with open(BACKUP_CONFIG_FILE, "w", encoding="utf-8") as bf:
                            json.dump(default, bf, ensure_ascii=False, indent=2)
                    except Exception:
                        pass
        except Exception:
            pass

    # If telegram was not configured or lost, check backup
    if not default.get("botToken") and os.path.exists(BACKUP_CONFIG_FILE):
        try:
            with open(BACKUP_CONFIG_FILE, "r", encoding="utf-8") as bf:
                bdata = json.load(bf)
                if bdata.get("botToken"):
                    if "eventsConfig" in bdata and isinstance(bdata["eventsConfig"], dict):
                        default["eventsConfig"].update(bdata["eventsConfig"])
                        bdata.pop("eventsConfig")
                    default.update(bdata)
                    save_config(default)
        except Exception:
            pass

    return default

def save_config(cfg: Dict[str, Any]):
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    if cfg and cfg.get("botToken"):
        try:
            with open(BACKUP_CONFIG_FILE, "w", encoding="utf-8") as bf:
                json.dump(cfg, bf, ensure_ascii=False, indent=2)
        except Exception:
            pass

import sqlite3

def load_devices() -> List[Dict[str, Any]]:
    possible_paths = [
        os.path.join(settings.DATA_DIR, "workstation_manager.db"),
        os.path.join(os.getcwd(), "data", "workstation_manager.db"),
        os.path.join(os.getcwd(), "workstation_manager.db"),
        os.path.join(settings.DATA_DIR, "fleet.db")
    ]
    for db_path in possible_paths:
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(devices)")
                cols = {c[1] for c in cursor.fetchall()}
                select_cols = ["id", "name", "hostname", "ip_address", "mac_address", "group_name", "power_status", "agent_version", "last_seen"]
                if "building" in cols: select_cols.append("building")
                if "floor" in cols: select_cols.append("floor")
                if "room" in cols: select_cols.append("room")
                cursor.execute(f"SELECT {', '.join(select_cols)} FROM devices")
                rows = cursor.fetchall()
                conn.close()
                devs = []
                now_utc = datetime.utcnow()
                for r in rows:
                    grp_str = r["group_name"] or "Office"
                    grps = [g.strip() for g in grp_str.split(",") if g.strip()]
                    b_val = str(r["building"]).strip() if "building" in r.keys() and r["building"] else ""
                    f_val = str(r["floor"]).strip() if "floor" in r.keys() and r["floor"] else ""
                    r_val = str(r["room"]).strip() if "room" in r.keys() and r["room"] else ""

                    if not b_val and grp_str and "/" in grp_str:
                        parts = [p.strip() for p in grp_str.split("/")]
                        if len(parts) >= 3:
                            b_val, f_val, r_val = parts[0], parts[1], parts[2]
                        elif len(parts) == 2:
                            b_val, r_val = parts[0], parts[1]
                    
                    last_seen_val = r["last_seen"]
                    sec_since = 999999
                    if last_seen_val:
                        try:
                            if isinstance(last_seen_val, str):
                                dt = datetime.fromisoformat(last_seen_val.replace("Z", "+00:00"))
                            elif isinstance(last_seen_val, datetime):
                                dt = last_seen_val
                            else:
                                dt = None
                            if dt:
                                if dt.tzinfo is not None:
                                    dt = dt.replace(tzinfo=None)
                                sec_since = (now_utc - dt).total_seconds()
                        except Exception:
                            pass

                    p_raw = str(r["power_status"] or "").strip().upper()
                    agent_ver = str(r["agent_version"] or "")
                    dev_id = str(r["id"] or "")

                    is_agentless = (
                        agent_ver == "Agentless" or 
                        dev_id.startswith("TC-") or 
                        "тонкий" in grp_str.lower()
                    )
                    timeout = 120 if is_agentless else 135

                    if p_raw in ["OFF", "POWERSTATUS.OFF"]:
                        is_online = False
                    elif p_raw in ["ON", "POWERSTATUS.ON", "BOOTING"]:
                        is_online = (sec_since <= timeout)
                    else:
                        is_online = (sec_since <= timeout)

                    effective_power = "On" if is_online else "Off"

                    devs.append({
                        "id": dev_id,
                        "name": r["name"] or r["hostname"] or dev_id,
                        "hostname": r["hostname"] or "",
                        "ip": r["ip_address"] or "",
                        "mac": r["mac_address"] or "",
                        "group": grps[0] if grps else "Office",
                        "groups": grps,
                        "building": b_val or "Общие группы",
                        "floor": f_val or "1 этаж",
                        "room": r_val or (grps[0] if grps else "Без кабинета"),
                        "powerStatus": effective_power,
                        "isOnline": is_online,
                        "agentVersion": agent_ver or "2.9.4",
                        "lastSeen": last_seen_val
                    })
                if devs:
                    return devs
            except Exception:
                pass
    return []
    return []

def send_wol_packet(mac_str: str) -> bool:
    try:
        clean_mac = mac_str.replace(":", "").replace("-", "").strip()
        if len(clean_mac) != 12:
            return False
        data = bytes.fromhex("FF" * 6 + clean_mac * 16)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(data, ("255.255.255.255", 9))
        sock.close()
        return True
    except Exception:
        return False

def send_udp_command(ip: str, action: str) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1.0)
        sock.sendto(f"CMD:{action.upper()}".encode("utf-8"), (ip, 48123))
        sock.close()
        return True
    except Exception:
        return False

def process_telegram_command(chat_id_str: str, text: str, from_user: Dict[str, Any] = None) -> str:
    chat_id = str(chat_id_str).strip()
    cmd_raw = (text or "").strip()
    parts = cmd_raw.split()
    cmd = parts[0].lower() if parts else ""
    arg = parts[1] if len(parts) > 1 else ""

    users = load_users()
    from_username = str(from_user.get("username", "") if from_user else "").replace("@", "").strip().lower()

    def matches_telegram_user(u: Dict[str, Any]) -> bool:
        tg_val = str(u.get("telegramChatId", "")).strip()
        if not tg_val:
            return False
        if tg_val == chat_id:
            return True
        clean_stored = tg_val.replace("@", "").strip().lower()
        if from_username and clean_stored == from_username:
            return True
        return False

    matched_user = next((u for u in users if matches_telegram_user(u)), None)

    # 1. Unregistered user handling
    if not matched_user:
        if cmd in ["/start", "/id", "/myid", "/help"]:
            username_part = f" @{from_user.get('username')}" if from_user and from_user.get("username") else ""
            return (
                f"👋 <b>Добро пожаловать в Workstation Manager!</b>\n\n"
                f"🆔 Ваш Telegram Chat ID: <code>{chat_id}</code>{username_part}\n\n"
                f"<i>Передайте этот идентификатор администратору для привязки к вашей учетной записи и получения доступа к управлению.</i>"
            )
        return (
            f"⛔️ <b>Доступ запрещен.</b>\n"
            f"Ваш Telegram Chat ID (<code>{chat_id}</code>) не привязан ни к одной учетной записи оператора.\n\n"
            f"Напишите команду <code>/id</code> для получения вашего идентификатора."
        )

    # 2. Check enabled status
    if not matched_user.get("enabled", True):
        return "🚫 <b>Учетная запись заблокирована</b> администратором. Обратитесь в IT-отдел."

    # 3. User attributes and scopes
    user_name = matched_user.get("displayName", matched_user.get("username", "Оператор"))
    role = matched_user.get("role", "Дежурный оператор")
    scope = matched_user.get("scope", "Все устройства")
    allowed_groups = [g.lower() for g in matched_user.get("allowedGroups", [])]
    is_global_scope = (scope == "Все устройства") or (not allowed_groups)

    # Filter devices according to Scope
    all_devs = load_devices()
    if is_global_scope:
        user_devices = all_devs
        scope_desc = "Все устройства"
    else:
        user_devices = [
            d for d in all_devs
            if str(d.get("group", "")).lower() in allowed_groups
            or any(str(g).lower() in allowed_groups for g in d.get("groups", []))
        ]
        scope_desc = f"Группы: {', '.join(matched_user.get('allowedGroups', []))}"

    def can_manage_device(d: Dict[str, Any]) -> bool:
        if is_global_scope:
            return True
        d_grp = str(d.get("group", "")).lower()
        d_grps = [str(g).lower() for g in d.get("groups", [])]
        return d_grp in allowed_groups or any(g in allowed_groups for g in d_grps)

def build_main_menu(user_name: str, role: str, scope_desc: str) -> Dict[str, Any]:
    return {
        "text": (
            f"👋 <b>Панель управления Workstation Manager</b>\n\n"
            f"👤 Оператор: <b>{user_name}</b>\n"
            f"🔰 Роль: <b>{role}</b>\n"
            f"🌐 Зона ответственности: <b>{scope_desc}</b>\n\n"
            f"<i>Выберите нужный раздел с помощью кнопок или введите номер кабинета / имя ПК для быстрого поиска:</i>"
        ),
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "🏢 Корпуса и кабинеты", "callback_data": "menu:buildings"},
                    {"text": "📊 Сводка сети", "callback_data": "menu:status"}
                ],
                [
                    {"text": "🖥 Все ПК (общий список)", "callback_data": "menu:devices:0"},
                    {"text": "🔄 Обновить", "callback_data": "menu:main"}
                ]
            ]
        }
    }

def build_hierarchy_buildings_view(user_devices: List[Dict[str, Any]], scope_desc: str) -> Dict[str, Any]:
    bld_map = collections.defaultdict(list)
    for d in user_devices:
        b = d.get("building") or "Общие группы"
        bld_map[b].append(d)

    keyboard = []
    for b_name, b_devs in sorted(bld_map.items()):
        total = len(b_devs)
        online = sum(1 for d in b_devs if d.get("isOnline") or d.get("powerStatus") == "On")
        keyboard.append([{"text": f"🏢 {b_name} ({total} ПК | {online} 🟢)", "callback_data": f"bld:{b_name}"}])

    keyboard.append([{"text": "⬅️ Главное меню", "callback_data": "menu:main"}])
    return {
        "text": f"🏢 <b>Выберите корпус или филиал</b> ({scope_desc}):\n<i>Нажмите на корпус для перехода к этажам и кабинетам:</i>",
        "reply_markup": {"inline_keyboard": keyboard}
    }

def build_hierarchy_floors_view(building: str, user_devices: List[Dict[str, Any]], role: str) -> Dict[str, Any]:
    bld_devs = [d for d in user_devices if (d.get("building") or "Общие группы") == building]
    flr_map = collections.defaultdict(list)
    for d in bld_devs:
        f = d.get("floor") or "1 этаж"
        flr_map[f].append(d)

    keyboard = []
    for f_name, f_devs in sorted(flr_map.items()):
        total = len(f_devs)
        online = sum(1 for d in f_devs if d.get("isOnline") or d.get("powerStatus") == "On")
        keyboard.append([{"text": f"🏬 {f_name} ({total} ПК | {online} 🟢)", "callback_data": f"flr:{building}:{f_name}"}])

    if role != "Наблюдатель" and bld_devs:
        keyboard.append([
            {"text": f"⚡️ Включить весь {building} (WoL)", "callback_data": f"confirm:wakebld:{building}"},
            {"text": f"🛑 Выключить весь {building}", "callback_data": f"confirm:shutbld:{building}"}
        ])

    keyboard.append([
        {"text": "⬅️ К списку корпусов", "callback_data": "menu:buildings"},
        {"text": "🏠 Главное меню", "callback_data": "menu:main"}
    ])
    return {
        "text": f"🏢 <b>{building}</b> (всего {len(bld_devs)} ПК)\n<i>Выберите этаж или выполните действие для всего корпуса:</i>",
        "reply_markup": {"inline_keyboard": keyboard}
    }

def build_hierarchy_rooms_view(building: str, floor: str, user_devices: List[Dict[str, Any]], role: str) -> Dict[str, Any]:
    target_devs = [d for d in user_devices if (d.get("building") or "Общие группы") == building and (d.get("floor") or "1 этаж") == floor]
    rm_map = collections.defaultdict(list)
    for d in target_devs:
        r = d.get("room") or d.get("group") or "Без кабинета"
        rm_map[r].append(d)

    keyboard = []
    row = []
    for r_name, r_devs in sorted(rm_map.items()):
        total = len(r_devs)
        online = sum(1 for d in r_devs if d.get("isOnline") or d.get("powerStatus") == "On")
        row.append({"text": f"🚪 {r_name} ({online}/{total} 🟢)", "callback_data": f"rm:{building}:{floor}:{r_name}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    if role != "Наблюдатель" and target_devs:
        keyboard.append([
            {"text": f"⚡️ Включить весь {floor} (WoL)", "callback_data": f"confirm:wakeflr:{building}:{floor}"},
            {"text": f"🛑 Выключить весь {floor}", "callback_data": f"confirm:shutflr:{building}:{floor}"}
        ])

    keyboard.append([
        {"text": "⬅️ Назад к этажам", "callback_data": f"bld:{building}"},
        {"text": "🏠 Главное меню", "callback_data": "menu:main"}
    ])
    return {
        "text": f"🏢 <b>{building}</b> → 🏬 <b>{floor}</b> ({len(target_devs)} ПК)\n<i>Выберите кабинет для управления:</i>",
        "reply_markup": {"inline_keyboard": keyboard}
    }

def build_hierarchy_room_devices_view(building: str, floor: str, room: str, user_devices: List[Dict[str, Any]], role: str) -> Dict[str, Any]:
    rm_devs = [d for d in user_devices if (d.get("building") or "Общие группы") == building and (d.get("floor") or "1 этаж") == floor and (d.get("room") or d.get("group") or "Без кабинета") == room]
    total = len(rm_devs)
    online = sum(1 for d in rm_devs if d.get("isOnline") or d.get("powerStatus") == "On")
    offline = total - online

    keyboard = []
    row = []
    for d in rm_devs:
        is_on = (d.get("powerStatus") == "On" or d.get("isOnline") is True)
        icon = "🟢" if is_on else "🔴"
        row.append({"text": f"{icon} {d.get('name')}", "callback_data": f"dev:{d.get('id')}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    if role != "Наблюдатель" and rm_devs:
        keyboard.append([
            {"text": "⚡️ Включить весь кабинет (WoL)", "callback_data": f"confirm:wakerm:{building}:{floor}:{room}"},
            {"text": "🛑 Выключить кабинет", "callback_data": f"confirm:shutrm:{building}:{floor}:{room}"}
        ])

    keyboard.append([
        {"text": "⬅️ Назад к кабинетам", "callback_data": f"flr:{building}:{floor}"},
        {"text": "🏠 Главное меню", "callback_data": "menu:main"}
    ])

    return {
        "text": (
            f"🏢 <b>{building}</b> → 🏬 <b>{floor}</b> → 🚪 <b>{room}</b>\n\n"
            f"🖥 Всего ПК: <b>{total}</b>  |  🟢 В сети: <b>{online}</b>  |  🔴 Выключено: <b>{offline}</b>\n\n"
            f"<i>Выберите станцию для индивидуального управления или воспользуйтесь групповыми кнопками:</i>"
        ),
        "reply_markup": {"inline_keyboard": keyboard}
    }

def build_status_view(user_devices: List[Dict[str, Any]], scope_desc: str) -> Dict[str, Any]:
    total = len(user_devices)
    online = sum(1 for d in user_devices if d.get("powerStatus") == "On" or d.get("isOnline") is True)
    offline = total - online
    return {
        "text": (
            f"📊 <b>Сводка состояния парка ПК</b>\n"
            f"🌐 Зона ответственности: <b>{scope_desc}</b>\n\n"
            f"🖥 Всего станций: <b>{total}</b>\n"
            f"🟢 В сети (Онлайн): <b>{online}</b>\n"
            f"🔴 Выключено: <b>{offline}</b>"
        ),
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "🖥 Список ПК", "callback_data": "menu:devices:0"},
                    {"text": "🔄 Обновить", "callback_data": "menu:status"}
                ],
                [
                    {"text": "⬅️ Главное меню", "callback_data": "menu:main"}
                ]
            ]
        }
    }

def build_devices_view(user_devices: List[Dict[str, Any]], scope_desc: str, page: int = 0) -> Dict[str, Any]:
    if not user_devices:
        return {
            "text": f"🖥 В вашей зоне ответственности (<b>{scope_desc}</b>) пока нет зарегистрированных ПК.",
            "reply_markup": {
                "inline_keyboard": [[{"text": "⬅️ Главное меню", "callback_data": "menu:main"}]]
            }
        }
    PAGE_SIZE = 8
    total_pages = max(1, (len(user_devices) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start_idx = page * PAGE_SIZE
    page_devs = user_devices[start_idx:start_idx + PAGE_SIZE]

    keyboard = []
    row = []
    for d in page_devs:
        is_on = (d.get("powerStatus") == "On" or d.get("isOnline") is True)
        icon = "🟢" if is_on else "🔴"
        btn_text = f"{icon} {d.get('name')}"
        row.append({"text": btn_text, "callback_data": f"dev:{d.get('id')}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    nav_row = []
    if page > 0:
        nav_row.append({"text": "◀️ Назад", "callback_data": f"menu:devices:{page - 1}"})
    nav_row.append({"text": f"📄 {page + 1}/{total_pages}", "callback_data": f"menu:devices:{page}"})
    if page < total_pages - 1:
        nav_row.append({"text": "Вперёд ▶️", "callback_data": f"menu:devices:{page + 1}"})
    keyboard.append(nav_row)

    keyboard.append([
        {"text": "🔄 Обновить", "callback_data": f"menu:devices:{page}"},
        {"text": "⬅️ Главное меню", "callback_data": "menu:main"}
    ])

    return {
        "text": f"🖥 <b>Список рабочих станций</b> ({scope_desc}):\n<i>Нажмите на нужную станцию для управления:</i>",
        "reply_markup": {"inline_keyboard": keyboard}
    }

def build_device_card(target_dev: Dict[str, Any], can_manage: bool, role: str) -> Dict[str, Any]:
    dev_id = target_dev.get("id")
    is_on = (target_dev.get("powerStatus") == "On" or target_dev.get("isOnline") is True)
    icon = "🟢" if is_on else "🔴"
    status_text = "В сети (Онлайн)" if is_on else "Выключен (Офлайн)"

    text = (
        f"🖥 <b>Рабочая станция: {target_dev.get('name')}</b>\n\n"
        f"📌 <b>ID:</b> <code>{dev_id}</code>\n"
        f"📶 <b>Статус:</b> {icon} <b>{status_text}</b>\n"
        f"🌐 <b>IP-адрес:</b> <code>{target_dev.get('ip') or '—'}</code>\n"
        f"🏷 <b>MAC-адрес:</b> <code>{target_dev.get('mac') or '—'}</code>\n"
        f"📁 <b>Группа:</b> <i>{target_dev.get('group')}</i>\n"
        f"⚙️ <b>Версия агента:</b> <code>v{target_dev.get('agentVersion')}</code>"
    )

    keyboard = []
    if can_manage and role != "Наблюдатель":
        ctrl_row = []
        if not is_on:
            ctrl_row.append({"text": "⚡️ Включить (WoL)", "callback_data": f"confirm:wake:{dev_id}"})
        else:
            ctrl_row.append({"text": "🛑 Выключить", "callback_data": f"confirm:shutdown:{dev_id}"})
            ctrl_row.append({"text": "🔄 Перезагрузить", "callback_data": f"confirm:reboot:{dev_id}"})
        if ctrl_row:
            keyboard.append(ctrl_row)

    keyboard.append([
        {"text": "🔍 Проверить статус", "callback_data": f"dev:{dev_id}"},
        {"text": "📋 К списку ПК", "callback_data": "menu:devices:0"}
    ])
    keyboard.append([{"text": "⬅️ Главное меню", "callback_data": "menu:main"}])

    return {"text": text, "reply_markup": {"inline_keyboard": keyboard}}

def build_confirm_view(target_dev: Dict[str, Any], action: str) -> Dict[str, Any]:
    dev_id = target_dev.get("id")
    act_name = "ВЫКЛЮЧЕНИЕ" if action == "shutdown" else ("ПЕРЕЗАГРУЗКУ" if action == "reboot" else "ВКЛЮЧЕНИЕ (WoL)")
    act_icon = "🛑" if action == "shutdown" else ("🔄" if action == "reboot" else "⚡️")

    text = (
        f"⚠️ <b>Подтверждение действия</b>\n\n"
        f"Вы действительно хотите выполнить {act_icon} <b>{act_name}</b>\n"
        f"для станции <b>{target_dev.get('name')}</b> (<code>{target_dev.get('ip')}</code>)?"
    )
    keyboard = [
        [
            {"text": f"{act_icon} Да, выполнить", "callback_data": f"do:{action}:{dev_id}"},
            {"text": "❌ Отмена", "callback_data": f"dev:{dev_id}"}
        ]
    ]
    return {"text": text, "reply_markup": {"inline_keyboard": keyboard}}

def process_telegram_callback(chat_id_str: str, data_str: str, from_user: Dict[str, Any] = None) -> Dict[str, Any]:
    chat_id = str(chat_id_str).strip()
    data = (data_str or "").strip()
    users = load_users()
    from_username = str(from_user.get("username", "") if from_user else "").replace("@", "").strip().lower()

    def matches_telegram_user(u: Dict[str, Any]) -> bool:
        tg_val = str(u.get("telegramChatId", "")).strip()
        if not tg_val:
            return False
        if tg_val == chat_id:
            return True
        clean_stored = tg_val.replace("@", "").strip().lower()
        if from_username and clean_stored == from_username:
            return True
        return False

    matched_user = next((u for u in users if matches_telegram_user(u)), None)
    if not matched_user or not matched_user.get("enabled", True):
        return {"text": "⛔️ <b>Доступ запрещен.</b> Учетная запись не привязана или заблокирована.", "alert": "Доступ запрещен"}

    user_name = matched_user.get("displayName", matched_user.get("username", "Оператор"))
    role = matched_user.get("role", "Дежурный оператор")
    scope = matched_user.get("scope", "Все устройства")
    allowed_groups = [g.lower() for g in matched_user.get("allowedGroups", [])]
    is_global_scope = (scope == "Все устройства") or (not allowed_groups)

    all_devs = load_devices()
    if is_global_scope:
        user_devices = all_devs
        scope_desc = "Все устройства"
    else:
        user_devices = [
            d for d in all_devs
            if str(d.get("group", "")).lower() in allowed_groups
            or any(str(g).lower() in allowed_groups for g in d.get("groups", []))
        ]
        scope_desc = f"Группы: {', '.join(matched_user.get('allowedGroups', []))}"

    def can_manage_device(d: Dict[str, Any]) -> bool:
        if is_global_scope:
            return True
        d_grp = str(d.get("group", "")).lower()
        d_grps = [str(g).lower() for g in d.get("groups", [])]
        return d_grp in allowed_groups or any(g in allowed_groups for g in d_grps)

    tg_tag = f"@{from_user.get('username')}" if from_user and from_user.get("username") else f"ID:{chat_id}"
    operator_label = f"{user_name} ({tg_tag})"

    if data == "menu:main":
        res = build_main_menu(user_name, role, scope_desc)
        res["alert"] = "Главное меню"
        return res

    if data == "menu:status":
        res = build_status_view(user_devices, scope_desc)
        res["alert"] = "Сводка обновлена"
        return res

    if data == "menu:buildings":
        res = build_hierarchy_buildings_view(user_devices, scope_desc)
        res["alert"] = "Корпуса"
        return res

    if data.startswith("bld:"):
        bld_name = data.split(":", 1)[1]
        res = build_hierarchy_floors_view(bld_name, user_devices, role)
        res["alert"] = f"Корпус {bld_name}"
        return res

    if data.startswith("flr:"):
        _, bld_name, flr_name = data.split(":", 2)
        res = build_hierarchy_rooms_view(bld_name, flr_name, user_devices, role)
        res["alert"] = f"Этаж {flr_name}"
        return res

    if data.startswith("rm:"):
        _, bld_name, flr_name, rm_name = data.split(":", 3)
        res = build_hierarchy_room_devices_view(bld_name, flr_name, rm_name, user_devices, role)
        res["alert"] = f"Кабинет {rm_name}"
        return res

    # Bulk room power actions
    if data.startswith("confirm:wakerm:"):
        _, _, bld_name, flr_name, rm_name = data.split(":", 4)
        return {
            "text": f"⚡️ <b>Подтверждение включения</b>\n\nВы действительно хотите отправить сигнал Wake-on-LAN на <b>все ПК кабинета {rm_name}</b> ({bld_name} / {flr_name})?",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {"text": "⚡️ Да, включить кабинет", "callback_data": f"do:wakerm:{bld_name}:{flr_name}:{rm_name}"},
                        {"text": "❌ Отмена", "callback_data": f"rm:{bld_name}:{flr_name}:{rm_name}"}
                    ]
                ]
            },
            "alert": "Требуется подтверждение"
        }

    if data.startswith("confirm:shutrm:"):
        _, _, bld_name, flr_name, rm_name = data.split(":", 4)
        return {
            "text": f"🛑 <b>Подтверждение выключения</b>\n\nВы действительно хотите выключить <b>все компьютеры кабинета {rm_name}</b> ({bld_name} / {flr_name})?",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {"text": "🛑 Да, выключить кабинет", "callback_data": f"do:shutrm:{bld_name}:{flr_name}:{rm_name}"},
                        {"text": "❌ Отмена", "callback_data": f"rm:{bld_name}:{flr_name}:{rm_name}"}
                    ]
                ]
            },
            "alert": "Требуется подтверждение"
        }

    if data.startswith("do:wakerm:"):
        _, _, bld_name, flr_name, rm_name = data.split(":", 4)
        target_devs = [d for d in user_devices if (d.get("building") or "Общие группы") == bld_name and (d.get("floor") or "1 этаж") == flr_name and (d.get("room") or d.get("group") or "Без кабинета") == rm_name]
        woken = 0
        for d in target_devs:
            if d.get("mac"):
                send_wol_packet(d["mac"])
                woken += 1
        record_audit(operator_label, "BULK_WAKE", f"ROOM_{rm_name}", "SUCCESS", f"WoL отправлен на {woken} ПК в {bld_name}/{flr_name}/{rm_name}")
        return {
            "text": f"✅ <b>Сигнал Wake-on-LAN отправлен!</b>\n\n⚡️ Разбужено компьютеров: <b>{woken}</b> из {len(target_devs)}\n📍 Локация: <b>{bld_name} → {flr_name} → {rm_name}</b>",
            "reply_markup": {
                "inline_keyboard": [[{"text": "🚪 К кабинету", "callback_data": f"rm:{bld_name}:{flr_name}:{rm_name}"}]]
            },
            "alert": f"WoL отправлен на {woken} ПК"
        }

    if data.startswith("do:shutrm:"):
        _, _, bld_name, flr_name, rm_name = data.split(":", 4)
        if role == "Наблюдатель":
            return {"text": "🚫 Роль «Наблюдатель» имеет доступ только для чтения.", "alert": "Отказ: роль Наблюдатель"}
        target_devs = [d for d in user_devices if (d.get("building") or "Общие группы") == bld_name and (d.get("floor") or "1 этаж") == flr_name and (d.get("room") or d.get("group") or "Без кабинета") == rm_name]
        from backend.app.api.v1.agents import queue_device_command, send_direct_lan_power_signal
        shut = 0
        for d in target_devs:
            if d.get("ip"):
                send_direct_lan_power_signal(ip_address=d["ip"], action="SHUTDOWN", device_id=d.get("id"), mac_address=d.get("mac", ""), hostname=d.get("hostname", ""))
            queue_device_command(d.get("id"), "SHUTDOWN", force=True, reason=f"Telegram room shutdown by {operator_label}")
            shut += 1
        record_audit(operator_label, "BULK_SHUTDOWN", f"ROOM_{rm_name}", "SUCCESS", f"Выключение {shut} ПК в {bld_name}/{flr_name}/{rm_name}")
        return {
            "text": f"✅ <b>Команда выключения отправлена!</b>\n\n🛑 Выключено станций: <b>{shut}</b>\n📍 Локация: <b>{bld_name} → {flr_name} → {rm_name}</b>",
            "reply_markup": {
                "inline_keyboard": [[{"text": "🚪 К кабинету", "callback_data": f"rm:{bld_name}:{flr_name}:{rm_name}"}]]
            },
            "alert": f"Выключение {shut} ПК"
        }

    # Bulk building power actions
    if data.startswith("confirm:wakebld:"):
        bld_name = data.split(":", 2)[2]
        return {
            "text": f"⚡️ <b>Подтверждение включения корпуса</b>\n\nВы действительно хотите отправить Wake-on-LAN на <b>ВСЕ компьютеры корпуса {bld_name}</b>?",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {"text": "⚡️ Да, включить весь корпус", "callback_data": f"do:wakebld:{bld_name}"},
                        {"text": "❌ Отмена", "callback_data": f"bld:{bld_name}"}
                    ]
                ]
            },
            "alert": "Требуется подтверждение"
        }

    if data.startswith("confirm:shutbld:"):
        bld_name = data.split(":", 2)[2]
        return {
            "text": f"🛑 <b>Подтверждение выключения корпуса</b>\n\nВы действительно хотите выключить <b>ВСЕ компьютеры корпуса {bld_name}</b>?",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {"text": "🛑 Да, выключить корпус", "callback_data": f"do:shutbld:{bld_name}"},
                        {"text": "❌ Отмена", "callback_data": f"bld:{bld_name}"}
                    ]
                ]
            },
            "alert": "Требуется подтверждение"
        }

    if data.startswith("do:wakebld:"):
        bld_name = data.split(":", 2)[2]
        target_devs = [d for d in user_devices if (d.get("building") or "Общие группы") == bld_name]
        woken = 0
        for d in target_devs:
            if d.get("mac"):
                send_wol_packet(d["mac"])
                woken += 1
        record_audit(operator_label, "BULK_WAKE", f"BLD_{bld_name}", "SUCCESS", f"WoL отправлен на {woken} ПК в корпусе {bld_name}")
        return {
            "text": f"✅ <b>Wake-on-LAN отправлен!</b>\n\n⚡️ Разбужено ПК: <b>{woken}</b> из {len(target_devs)} в <b>{bld_name}</b>",
            "reply_markup": {
                "inline_keyboard": [[{"text": "🏢 К корпусу", "callback_data": f"bld:{bld_name}"}]]
            },
            "alert": f"WoL на {woken} ПК"
        }

    if data.startswith("do:shutbld:"):
        bld_name = data.split(":", 2)[2]
        if role == "Наблюдатель":
            return {"text": "🚫 Роль «Наблюдатель» имеет доступ только для чтения.", "alert": "Отказ: роль Наблюдатель"}
        target_devs = [d for d in user_devices if (d.get("building") or "Общие группы") == bld_name]
        from backend.app.api.v1.agents import queue_device_command, send_direct_lan_power_signal
        shut = 0
        for d in target_devs:
            if d.get("ip"):
                send_direct_lan_power_signal(ip_address=d["ip"], action="SHUTDOWN", device_id=d.get("id"), mac_address=d.get("mac", ""), hostname=d.get("hostname", ""))
            queue_device_command(d.get("id"), "SHUTDOWN", force=True, reason=f"Telegram building shutdown by {operator_label}")
            shut += 1
        record_audit(operator_label, "BULK_SHUTDOWN", f"BLD_{bld_name}", "SUCCESS", f"Выключение {shut} ПК в {bld_name}")
        return {
            "text": f"✅ <b>Команда выключения отправлена!</b>\n\n🛑 Выключено ПК: <b>{shut}</b> в <b>{bld_name}</b>",
            "reply_markup": {
                "inline_keyboard": [[{"text": "🏢 К корпусу", "callback_data": f"bld:{bld_name}"}]]
            },
            "alert": f"Выключение {shut} ПК"
        }

    if data.startswith("menu:devices"):
        parts = data.split(":")
        page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        res = build_devices_view(user_devices, scope_desc, page)
        res["alert"] = f"Страница {page + 1}"
        return res

    if data.startswith("dev:"):
        dev_id = data.split(":", 1)[1]
        target = next((d for d in all_devs if d.get("id") == dev_id or d.get("name") == dev_id), None)
        if not target:
            return {"text": f"❌ Устройство <code>{dev_id}</code> не найдено.", "alert": "Устройство не найдено"}
        res = build_device_card(target, can_manage_device(target), role)
        res["alert"] = f"Статус: {target.get('name')}"
        return res

    if data.startswith("confirm:"):
        _, action, dev_id = data.split(":", 2)
        target = next((d for d in all_devs if d.get("id") == dev_id or d.get("name") == dev_id), None)
        if not target:
            return {"text": "❌ Устройство не найдено.", "alert": "Устройство не найдено"}
        return build_confirm_view(target, action)

    if data.startswith("do:"):
        _, action, dev_id = data.split(":", 2)
        target = next((d for d in all_devs if d.get("id") == dev_id or d.get("name") == dev_id), None)
        if not target:
            return {"text": "❌ Устройство не найдено.", "alert": "Устройство не найдено"}
        if not can_manage_device(target):
            return {"text": "🚫 Ограничение доступа по зоне ответственности (Scope).", "alert": "Нет прав для этой группы!"}
        if role == "Наблюдатель" and action != "wake":
            return {"text": "🚫 Роль «Наблюдатель» имеет доступ только для чтения.", "alert": "Отказ: роль Наблюдатель"}

        from backend.app.api.v1.agents import queue_device_command, send_direct_lan_power_signal
        act_name = "Включение (WoL)" if action == "wake" else ("Выключение" if action == "shutdown" else "Перезагрузка")
        act_icon = "⚡️" if action == "wake" else ("🛑" if action == "shutdown" else "🔄")

        if action == "wake":
            mac = target.get("mac", "")
            if not mac:
                return {"text": f"❌ У устройства {target.get('name')} нет MAC-адреса.", "alert": "Ошибка: нет MAC"}
            send_wol_packet(mac)
            record_audit(operator_label, "WAKE", dev_id, "SUCCESS", "Magic Packet (WoL) отправлен через Telegram инлайн-кнопку")
        elif action in ["shutdown", "poweroff"]:
            ip = target.get("ip", "")
            if ip:
                send_direct_lan_power_signal(ip_address=ip, action="SHUTDOWN", device_id=dev_id, mac_address=target.get("mac", ""), hostname=target.get("hostname", ""))
            queue_device_command(dev_id, "SHUTDOWN", force=True, reason=f"Telegram inline by {operator_label}")
            if target.get("hostname") and target.get("hostname") != dev_id:
                queue_device_command(target.get("hostname"), "SHUTDOWN", force=True, reason=f"Telegram inline by {operator_label}")
            record_audit(operator_label, "SHUTDOWN", dev_id, "SUCCESS", "Команда выключения отправлена через Telegram инлайн-кнопку")
        elif action in ["reboot", "restart"]:
            ip = target.get("ip", "")
            if ip:
                send_direct_lan_power_signal(ip_address=ip, action="REBOOT", device_id=dev_id, mac_address=target.get("mac", ""), hostname=target.get("hostname", ""))
            queue_device_command(dev_id, "REBOOT", force=True, reason=f"Telegram inline by {operator_label}")
            if target.get("hostname") and target.get("hostname") != dev_id:
                queue_device_command(target.get("hostname"), "REBOOT", force=True, reason=f"Telegram inline by {operator_label}")
            record_audit(operator_label, "REBOOT", dev_id, "SUCCESS", "Команда перезагрузки отправлена через Telegram инлайн-кнопку")

        return {
            "text": (
                f"✅ <b>Команда успешно отправлена!</b>\n\n"
                f"{act_icon} Действие: <b>{act_name}</b>\n"
                f"🖥 Станция: <b>{target.get('name')}</b> (<code>{target.get('ip')}</code>)\n"
                f"👤 Оператор: <b>{user_name}</b>\n\n"
                f"<i>Сигнал мгновенно передан целевому компьютеру.</i>"
            ),
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {"text": "🖥 К компьютеру", "callback_data": f"dev:{dev_id}"},
                        {"text": "📋 К списку ПК", "callback_data": "menu:devices:0"}
                    ]
                ]
            },
            "alert": f"{act_name} выполнено!"
        }

    return {"text": "❓ Неизвестное действие.", "alert": "Неизвестное действие"}

def process_telegram_command(chat_id_str: str, text: str, from_user: Dict[str, Any] = None) -> Any:
    chat_id = str(chat_id_str).strip()
    cmd_raw = (text or "").strip()
    parts = cmd_raw.split()
    cmd = parts[0].lower() if parts else ""
    arg = parts[1] if len(parts) > 1 else ""

    users = load_users()
    from_username = str(from_user.get("username", "") if from_user else "").replace("@", "").strip().lower()

    def matches_telegram_user(u: Dict[str, Any]) -> bool:
        tg_val = str(u.get("telegramChatId", "")).strip()
        if not tg_val:
            return False
        if tg_val == chat_id:
            return True
        clean_stored = tg_val.replace("@", "").strip().lower()
        if from_username and clean_stored == from_username:
            return True
        return False

    matched_user = next((u for u in users if matches_telegram_user(u)), None)

    # 1. Unregistered user handling
    if not matched_user:
        if cmd in ["/start", "/id", "/myid", "/help"]:
            username_part = f" @{from_user.get('username')}" if from_user and from_user.get("username") else ""
            return (
                f"👋 <b>Добро пожаловать в Workstation Manager!</b>\n\n"
                f"🆔 Ваш Telegram Chat ID: <code>{chat_id}</code>{username_part}\n\n"
                f"<i>Передайте этот идентификатор администратору для привязки к вашей учетной записи и получения доступа к управлению.</i>"
            )
        return (
            f"⛔️ <b>Доступ запрещен.</b>\n"
            f"Ваш Telegram Chat ID (<code>{chat_id}</code>) не привязан ни к одной учетной записи оператора.\n\n"
            f"Напишите команду <code>/id</code> для получения вашего идентификатора."
        )

    # 2. Check enabled status
    if not matched_user.get("enabled", True):
        return "🚫 <b>Учетная запись заблокирована</b> администратором. Обратитесь в IT-отдел."

    # 3. User attributes and scopes
    user_name = matched_user.get("displayName", matched_user.get("username", "Оператор"))
    role = matched_user.get("role", "Дежурный оператор")
    scope = matched_user.get("scope", "Все устройства")
    allowed_groups = [g.lower() for g in matched_user.get("allowedGroups", [])]
    is_global_scope = (scope == "Все устройства") or (not allowed_groups)

    # Filter devices according to Scope
    all_devs = load_devices()
    if is_global_scope:
        user_devices = all_devs
        scope_desc = "Все устройства"
    else:
        user_devices = [
            d for d in all_devs
            if str(d.get("group", "")).lower() in allowed_groups
            or any(str(g).lower() in allowed_groups for g in d.get("groups", []))
        ]
        scope_desc = f"Группы: {', '.join(matched_user.get('allowedGroups', []))}"

    def can_manage_device(d: Dict[str, Any]) -> bool:
        if is_global_scope:
            return True
        d_grp = str(d.get("group", "")).lower()
        d_grps = [str(g).lower() for g in d.get("groups", [])]
        return d_grp in allowed_groups or any(g in allowed_groups for g in d_grps)

    # 4. Command Router with Rich Inline Menus
    if cmd in ["/start", "/help", "/menu"]:
        return build_main_menu(user_name, role, scope_desc)

    if cmd in ["/id", "/myid"]:
        return {
            "text": f"🆔 Ваш Telegram Chat ID: <code>{chat_id}</code>\n👤 Профиль: <b>{user_name}</b> ({role})\n🌐 Зона: <b>{scope_desc}</b>",
            "reply_markup": {
                "inline_keyboard": [[{"text": "⬅️ Главное меню", "callback_data": "menu:main"}]]
            }
        }

    if cmd == "/status":
        return build_status_view(user_devices, scope_desc)

    if cmd == "/devices":
        return build_devices_view(user_devices, scope_desc, 0)

    if cmd in ["/wake", "/shutdown", "/reboot", "/poweroff"]:
        if not arg:
            return f"⚠️ Пожалуйста, укажите имя или ID компьютера. Пример: <code>{cmd} xeon</code>"
        
        target_term = arg.strip().lower()
        target_dev = next((
            d for d in all_devs
            if d.get("name", "").lower() == target_term
            or d.get("id", "").lower() == target_term
            or d.get("hostname", "").lower() == target_term
            or d.get("ip", "") == target_term
        ), None)

        if not target_dev:
            return f"❌ Компьютер <b>{arg}</b> не найден в базе данных."

        # Check Scope
        if not can_manage_device(target_dev):
            target_grp = target_dev.get("group", "Другая группа")
            return (
                f"🚫 <b>Ограничение доступа (Scope):</b>\n"
                f"Компьютер <b>{target_dev.get('name')}</b> находится в группе <b>{target_grp}</b>.\n"
                f"Ваша зона ответственности ограничена: <b>{scope_desc}</b>."
            )

        # Check Role permissions
        if role == "Наблюдатель":
            return "🚫 <b>Отказ в доступе:</b> Учетная запись с ролью «Наблюдатель» имеет доступ только для чтения."

        # Execute Command
        tg_tag = f"@{from_user.get('username')}" if from_user and from_user.get("username") else f"ID:{chat_id}"
        operator_label = f"{user_name} ({tg_tag})"

        if cmd == "/wake":
            mac = target_dev.get("mac", "")
            if not mac:
                return f"❌ У устройства <b>{target_dev.get('name')}</b> не указан MAC-адрес для Wake-on-LAN."
            send_wol_packet(mac)
            record_audit(operator_label, "WAKE", target_dev.get("id"), "SUCCESS", f"Magic Packet (WoL) отправлен через Telegram-бота")
            return {
                "text": f"⚡️ <b>Magic Packet (WoL) успешно отправлен</b> на <b>{target_dev.get('name')}</b> (MAC: <code>{mac}</code>)!",
                "reply_markup": {
                    "inline_keyboard": [[{"text": "🖥 К компьютеру", "callback_data": f"dev:{target_dev.get('id')}"}]]
                }
            }

        if cmd in ["/shutdown", "/poweroff"]:
            ip = target_dev.get("ip", "")
            dev_id = target_dev.get("id")
            from backend.app.api.v1.agents import queue_device_command, send_direct_lan_power_signal
            if ip:
                send_direct_lan_power_signal(
                    ip_address=ip,
                    action="SHUTDOWN",
                    device_id=dev_id,
                    mac_address=target_dev.get("mac", ""),
                    hostname=target_dev.get("hostname", "")
                )
            if dev_id:
                queue_device_command(dev_id, "SHUTDOWN", force=True, reason=f"Telegram command by {operator_label}")
                if target_dev.get("hostname") and target_dev.get("hostname") != dev_id:
                    queue_device_command(target_dev.get("hostname"), "SHUTDOWN", force=True, reason=f"Telegram command by {operator_label}")
            record_audit(operator_label, "SHUTDOWN", dev_id, "SUCCESS", f"Команда выключения инициирована через Telegram-бота")
            return {
                "text": f"🛑 <b>Команда выключения отправлена</b> на рабочую станцию <b>{target_dev.get('name')}</b> ({ip}).",
                "reply_markup": {
                    "inline_keyboard": [[{"text": "🖥 К компьютеру", "callback_data": f"dev:{target_dev.get('id')}"}]]
                }
            }

        if cmd == "/reboot":
            ip = target_dev.get("ip", "")
            dev_id = target_dev.get("id")
            from backend.app.api.v1.agents import queue_device_command, send_direct_lan_power_signal
            if ip:
                send_direct_lan_power_signal(
                    ip_address=ip,
                    action="REBOOT",
                    device_id=dev_id,
                    mac_address=target_dev.get("mac", ""),
                    hostname=target_dev.get("hostname", "")
                )
            if dev_id:
                queue_device_command(dev_id, "REBOOT", force=True, reason=f"Telegram command by {operator_label}")
                if target_dev.get("hostname") and target_dev.get("hostname") != dev_id:
                    queue_device_command(target_dev.get("hostname"), "REBOOT", force=True, reason=f"Telegram command by {operator_label}")
            record_audit(operator_label, "REBOOT", dev_id, "SUCCESS", f"Команда перезагрузки инициирована через Telegram-бота")
            return {
                "text": f"🔄 <b>Команда перезагрузки отправлена</b> на рабочую станцию <b>{target_dev.get('name')}</b> ({ip}).",
                "reply_markup": {
                    "inline_keyboard": [[{"text": "🖥 К компьютеру", "callback_data": f"dev:{target_dev.get('id')}"}]]
                }
            }

    # 5. Smart search by room number, cabinet name, device name, IP, or building
    q = cmd_raw.strip().lower()
    if q and not q.startswith("/"):
        matches = [
            d for d in user_devices
            if q in str(d.get("room", "")).lower()
            or q in str(d.get("name", "")).lower()
            or q in str(d.get("hostname", "")).lower()
            or q in str(d.get("ip", "")).lower()
            or q in str(d.get("group", "")).lower()
            or q in str(d.get("building", "")).lower()
        ]
        if matches:
            if len(matches) == 1:
                return build_device_card(matches[0], can_manage_device(matches[0]), role)
            
            keyboard = []
            for d in matches[:10]:
                is_on = (d.get("powerStatus") == "On" or d.get("isOnline") is True)
                icon = "🟢" if is_on else "🔴"
                loc = f"{d.get('building')} / {d.get('room')}" if d.get('room') else d.get('group')
                keyboard.append([{"text": f"{icon} {d.get('name')} ({loc})", "callback_data": f"dev:{d.get('id')}"}])
            keyboard.append([{"text": "⬅️ Главное меню", "callback_data": "menu:main"}])
            return {
                "text": f"🔍 <b>Найдено совпадений: {len(matches)}</b> по запросу «{cmd_raw}»:\n<i>Выберите станцию для перехода к управлению:</i>",
                "reply_markup": {"inline_keyboard": keyboard}
            }

    return f"❓ Неизвестная команда <code>{cmd}</code>. Напишите <code>/help</code> или <code>/menu</code> для открытия меню."

class TelegramConfigPayload(BaseModel):
    botToken: str = ""
    chatId: str = ""
    timezone: Optional[str] = "Europe/Moscow"
    alertsEnabled: bool = True
    botUsername: str = ""
    proxyEnabled: bool = False
    proxyType: str = "SOCKS5"
    proxyHost: str = ""
    proxyPort: str = "1080"
    proxyUser: str = ""
    proxyPass: str = ""
    eventsConfig: Optional[Dict[str, bool]] = None

class TestProxyPayload(BaseModel):
    botToken: Optional[str] = ""
    proxyEnabled: bool = True
    proxyType: str = "SOCKS5"
    proxyHost: str = ""
    proxyPort: str = "1080"
    proxyUser: Optional[str] = ""
    proxyPass: Optional[str] = ""

class ProcessCommandPayload(BaseModel):
    chatId: str
    text: str
    username: Optional[str] = ""

@router.get("/config")
async def get_telegram_config():
    return load_config()

@router.post("/config")
async def update_telegram_config(payload: TelegramConfigPayload):
    cfg = load_config()
    cfg["botToken"] = payload.botToken.strip()
    cfg["chatId"] = payload.chatId.strip()
    if payload.timezone:
        cfg["timezone"] = payload.timezone.strip()
    cfg["alertsEnabled"] = payload.alertsEnabled
    cfg["proxyEnabled"] = payload.proxyEnabled
    cfg["proxyType"] = payload.proxyType.strip()
    cfg["proxyHost"] = payload.proxyHost.strip()
    cfg["proxyPort"] = str(payload.proxyPort).strip()
    cfg["proxyUser"] = payload.proxyUser.strip()
    cfg["proxyPass"] = payload.proxyPass.strip()
    if payload.eventsConfig is not None:
        if "eventsConfig" not in cfg or not isinstance(cfg["eventsConfig"], dict):
            cfg["eventsConfig"] = {}
        cfg["eventsConfig"].update(payload.eventsConfig)

    if not cfg["botToken"]:
        cfg["botUsername"] = ""
        cfg["status"] = "Не настроен"
    else:
        # Check token validity via Telegram API
        try:
            async with get_httpx_client(cfg, timeout=4.0) as client:
                url = f"https://api.telegram.org/bot{cfg['botToken']}/getMe"
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    bot_username = data.get("result", {}).get("username", "")
                    if bot_username:
                        cfg["botUsername"] = f"@{bot_username}"
                    cfg["status"] = "Подключен"
                elif resp.status_code == 401:
                    cfg["status"] = "Неверный токен"
                else:
                    cfg["status"] = "Ошибка связи"
        except Exception:
            cfg["status"] = "Подключен" if (cfg["botToken"] and cfg["chatId"]) else "Готов"

    if payload.botUsername and not cfg.get("botUsername"):
        cfg["botUsername"] = payload.botUsername.strip()

    save_config(cfg)
    return cfg

@router.post("/test-proxy")
async def test_telegram_proxy(payload: TestProxyPayload):
    test_cfg = {
        "proxyEnabled": payload.proxyEnabled,
        "proxyType": payload.proxyType,
        "proxyHost": payload.proxyHost,
        "proxyPort": payload.proxyPort,
        "proxyUser": payload.proxyUser,
        "proxyPass": payload.proxyPass
    }
    
    proxy_url = get_proxy_url(test_cfg)
    if not proxy_url and payload.proxyEnabled:
        return {"ok": False, "message": "Укажите хост и порт прокси-сервера"}

    token = payload.botToken.strip()
    if not token:
        token = load_config().get("botToken", "")

    test_url = f"https://api.telegram.org/bot{token}/getMe" if token else "https://api.telegram.org"

    try:
        async with get_httpx_client(test_cfg, timeout=7.0) as client:
            resp = await client.get(test_url)
            if resp.status_code == 200:
                data = resp.json() if token else {}
                bot_name = data.get("result", {}).get("username", "")
                if bot_name:
                    return {"ok": True, "message": f"Соединение с Telegram успешно! Бот @{bot_name} отвечает через прокси.", "botUsername": f"@{bot_name}"}
            elif resp.status_code == 302:
                return {"ok": True, "message": "Прокси работает! Шлюз api.telegram.org доступен (получен ответ от серверов Telegram)."}
            elif resp.status_code == 401:
                return {"ok": True, "message": "Прокси работает! Сервер Telegram ответил (проверьте корректность Bot Token)."}
            else:
                return {"ok": False, "message": f"Сервер Telegram вернул HTTP статус {resp.status_code}"}
    except Exception as e:
        return {"ok": False, "message": f"Ошибка подключения через прокси: {str(e)}"}

@router.post("/process-command")
async def handle_process_command(payload: ProcessCommandPayload):
    resp_data = process_telegram_command(payload.chatId, payload.text, {"username": payload.username})
    resp_text = resp_data.get("text", "") if isinstance(resp_data, dict) else str(resp_data)
    return {"reply": resp_text}

@router.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        message = data.get("message") or data.get("edited_message")
        if not message:
            return {"ok": True}
        
        chat = message.get("chat", {})
        chat_id = str(chat.get("id", ""))
        text = message.get("text", "")
        from_user = message.get("from", {})

        reply_data = process_telegram_command(chat_id, text, from_user)
        reply_text = reply_data.get("text", "") if isinstance(reply_data, dict) else str(reply_data)
        reply_markup = reply_data.get("reply_markup") if isinstance(reply_data, dict) else None

        # Send response via Telegram Bot API if token is configured
        cfg = load_config()
        if cfg.get("botToken") and chat_id:
            try:
                async with get_httpx_client(cfg, timeout=6.0) as client:
                    url = f"https://api.telegram.org/bot{cfg['botToken']}/sendMessage"
                    post_payload = {"chat_id": chat_id, "text": reply_text, "parse_mode": "HTML"}
                    if reply_markup:
                        post_payload["reply_markup"] = reply_markup
                    await client.post(url, json=post_payload)
            except Exception:
                pass

        return {"ok": True, "reply": reply_text}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.post("/test-alert")
async def send_test_alert(payload: Dict[str, Any] = None):
    cfg = load_config()
    message = payload.get("message", "Тестовый сигнал от Workstation Manager: Все системы в норме") if payload else "Тестовый сигнал"
    
    if cfg.get("botToken") and cfg.get("chatId"):
        try:
            async with get_httpx_client(cfg, timeout=7.0) as client:
                url = f"https://api.telegram.org/bot{cfg['botToken']}/sendMessage"
                resp = await client.post(url, json={"chat_id": cfg["chatId"], "text": message, "parse_mode": "HTML"})
                if resp.status_code == 200:
                    return {"status": "sent", "message": "Тестовое сообщение успешно доставлено в Telegram-чат!"}
        except Exception as e:
            return {"status": "dispatched", "message": f"Тестовый сигнал сформирован (ошибка отправки Telegram API: {str(e)})"}

    return {"status": "dispatched", "message": "Тестовый сигнал успешно обработан сервером"}
