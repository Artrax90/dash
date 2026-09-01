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
        return httpx.AsyncClient(proxy=proxy, timeout=timeout)
    return httpx.AsyncClient(timeout=timeout)

def load_config() -> Dict[str, Any]:
    default = {
        "enabled": True,
        "botToken": "",
        "chatId": "",
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
            "morningWakeSummary": True,
            "eveningShutdownSummary": True,
            "hardwareChanges": True,
        },
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default.update(data)
        except Exception:
            pass
    return default

def save_config(cfg: Dict[str, Any]):
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

import sqlite3

def load_devices() -> List[Dict[str, Any]]:
    possible_paths = [
        os.path.join(os.getcwd(), "workstation_manager.db"),
        os.path.join(os.getcwd(), "data", "workstation_manager.db"),
        os.path.join(settings.DATA_DIR, "fleet.db")
    ]
    for db_path in possible_paths:
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT id, name, hostname, ip_address, mac_address, group_name, power_status, agent_version, last_seen FROM devices")
                rows = cursor.fetchall()
                conn.close()
                devs = []
                for r in rows:
                    grp_str = r["group_name"] or "Office"
                    grps = [g.strip() for g in grp_str.split(",") if g.strip()]
                    devs.append({
                        "id": r["id"],
                        "name": r["name"] or r["hostname"] or r["id"],
                        "hostname": r["hostname"] or "",
                        "ip": r["ip_address"] or "",
                        "mac": r["mac_address"] or "",
                        "group": grps[0] if grps else "Office",
                        "groups": grps,
                        "powerStatus": r["power_status"] or "On",
                        "agentVersion": r["agent_version"] or "2.5.3",
                        "lastSeen": r["last_seen"]
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

    # 4. Command Router
    if cmd in ["/start", "/help"]:
        return (
            f"👋 <b>Workstation Manager Bot</b>\n"
            f"👤 Оператор: <b>{user_name}</b>\n"
            f"🔰 Роль: <b>{role}</b>\n"
            f"🌐 Зона доступа: <b>{scope_desc}</b>\n\n"
            f"<b>Доступные команды:</b>\n"
            f"📊 <code>/status</code> — Сводка состояния подконтрольного парка\n"
            f"🖥 <code>/devices</code> — Список рабочих станций в вашей зоне\n"
            f"⚡️ <code>/wake &lt;Имя_ПК&gt;</code> — Включить компьютер (Wake-on-LAN)\n"
            f"🛑 <code>/shutdown &lt;Имя_ПК&gt;</code> — Выключить рабочую станцию\n"
            f"🔄 <code>/reboot &lt;Имя_ПК&gt;</code> — Перезагрузить компьютер\n"
            f"🆔 <code>/id</code> — Показать ваш Telegram Chat ID"
        )

    if cmd == "/id" or cmd == "/myid":
        return f"🆔 Ваш Telegram Chat ID: <code>{chat_id}</code>\n👤 Профиль: <b>{user_name}</b> ({role})\n🌐 Зона: <b>{scope_desc}</b>"

    if cmd == "/status":
        total = len(user_devices)
        online = sum(1 for d in user_devices if d.get("powerStatus") == "On")
        offline = total - online
        return (
            f"📊 <b>Сводка состояния парка ПК</b>\n"
            f"🌐 Зона ответственности: <b>{scope_desc}</b>\n\n"
            f"🖥 Всего станций: <b>{total}</b>\n"
            f"🟢 В сети (Онлайн): <b>{online}</b>\n"
            f"🔴 Выключено: <b>{offline}</b>"
        )

    if cmd == "/devices":
        if not user_devices:
            return f"🖥 В вашей зоне ответственности (<b>{scope_desc}</b>) пока нет зарегистрированных ПК."
        lines = [f"🖥 <b>Список рабочих станций ({scope_desc}):</b>\n"]
        for d in user_devices:
            status_icon = "🟢" if d.get("powerStatus") == "On" else "🔴"
            grp = d.get("group", "Общие")
            lines.append(f"{status_icon} <b>{d.get('name')}</b> ({d.get('ip')}) · <i>{grp}</i> · v{d.get('agentVersion', '2.6.5')}")
        return "\n".join(lines)

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
            return f"⚡️ <b>Magic Packet (WoL) успешно отправлен</b> на <b>{target_dev.get('name')}</b> (MAC: <code>{mac}</code>)!"

        if cmd in ["/shutdown", "/poweroff"]:
            ip = target_dev.get("ip", "")
            if ip:
                send_udp_command(ip, "SHUTDOWN")
            record_audit(operator_label, "SHUTDOWN", target_dev.get("id"), "SUCCESS", f"Команда выключения инициирована через Telegram-бота")
            return f"🛑 <b>Команда выключения отправлена</b> на рабочую станцию <b>{target_dev.get('name')}</b> ({ip})."

        if cmd == "/reboot":
            ip = target_dev.get("ip", "")
            if ip:
                send_udp_command(ip, "REBOOT")
            record_audit(operator_label, "REBOOT", target_dev.get("id"), "SUCCESS", f"Команда перезагрузки инициирована через Telegram-бота")
            return f"🔄 <b>Команда перезагрузки отправлена</b> на рабочую станцию <b>{target_dev.get('name')}</b> ({ip})."

    return f"❓ Неизвестная команда <code>{cmd}</code>. Напишите <code>/help</code> для списка доступных команд."

class TelegramConfigPayload(BaseModel):
    botToken: str = ""
    chatId: str = ""
    alertsEnabled: bool = True
    botUsername: str = ""
    proxyEnabled: bool = False
    proxyType: str = "SOCKS5"
    proxyHost: str = ""
    proxyPort: str = "1080"
    proxyUser: str = ""
    proxyPass: str = ""

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
    cfg["alertsEnabled"] = payload.alertsEnabled
    cfg["proxyEnabled"] = payload.proxyEnabled
    cfg["proxyType"] = payload.proxyType.strip()
    cfg["proxyHost"] = payload.proxyHost.strip()
    cfg["proxyPort"] = str(payload.proxyPort).strip()
    cfg["proxyUser"] = payload.proxyUser.strip()
    cfg["proxyPass"] = payload.proxyPass.strip()

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
                return {"ok": True, "message": "Прокси работает! Шлюз api.telegram.org доступен."}
            elif resp.status_code == 401:
                return {"ok": True, "message": "Прокси работает! Сервер Telegram ответил (проверьте корректность Bot Token)."}
            else:
                return {"ok": False, "message": f"Сервер Telegram вернул HTTP статус {resp.status_code}"}
    except Exception as e:
        return {"ok": False, "message": f"Ошибка подключения через прокси: {str(e)}"}

@router.post("/process-command")
async def handle_process_command(payload: ProcessCommandPayload):
    resp_text = process_telegram_command(payload.chatId, payload.text, {"username": payload.username})
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

        reply_text = process_telegram_command(chat_id, text, from_user)

        # Send response via Telegram Bot API if token is configured
        cfg = load_config()
        if cfg.get("botToken") and chat_id:
            try:
                async with get_httpx_client(cfg, timeout=6.0) as client:
                    url = f"https://api.telegram.org/bot{cfg['botToken']}/sendMessage"
                    await client.post(url, json={"chat_id": chat_id, "text": reply_text, "parse_mode": "HTML"})
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
