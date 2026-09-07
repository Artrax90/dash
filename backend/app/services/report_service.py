from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import collections
from backend.app.core.scope import is_device_in_scope

def filter_user_devices(user: Dict[str, Any], devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    role = user.get("role", "Дежурный оператор")
    scope = user.get("scope", "Все устройства")
    allowed_groups = user.get("allowedGroups", []) or []
    
    if scope == "Все устройства" or not allowed_groups:
        return devices
    return [d for d in devices if is_device_in_scope(d, allowed_groups)]

def generate_morning_report(
    user: Dict[str, Any],
    devices: List[Dict[str, Any]],
    power_logs: Dict[str, List[Dict[str, Any]]],
    now_dt: Optional[datetime] = None
) -> Dict[str, Any]:
    if now_dt is None:
        now_dt = datetime.now(timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)

    user_devices = filter_user_devices(user, devices)
    total_devices = len(user_devices)
    
    online_count = 0
    offline_count = 0
    unreturned = []

    # Window for night events: last 12 hours
    cutoff_time = now_dt - timedelta(hours=12)

    for dev in user_devices:
        dev_id = str(dev.get("id", "")).upper()
        is_on = (dev.get("powerStatus") == "On" or dev.get("isOnline") is True)
        
        if is_on:
            online_count += 1
        else:
            offline_count += 1
            dev_events = power_logs.get(dev_id, [])
            recent_event = None
            for evt in dev_events:
                evt_time_str = evt.get("timestamp") or evt.get("time")
                if evt_time_str:
                    try:
                        evt_dt = datetime.fromisoformat(evt_time_str.replace("Z", "+00:00"))
                        if evt_dt >= cutoff_time:
                            recent_event = evt
                            break
                    except Exception:
                        pass
            if recent_event:
                action = (recent_event.get("action") or "SHUTDOWN").upper()
                details = recent_event.get("details") or recent_event.get("title") or ""
                unreturned.append({
                    "id": dev.get("id"),
                    "name": dev.get("name") or dev.get("id"),
                    "building": dev.get("building") or "Общие группы",
                    "floor": dev.get("floor") or "1 этаж",
                    "room": dev.get("room") or dev.get("group") or "—",
                    "action": action,
                    "reason": f"{action}: {details}" if details else action,
                    "event_time": recent_event.get("timestamp") or recent_event.get("time")
                })

    return {
        "user_id": user.get("id"),
        "user_name": user.get("displayName") or user.get("username") or "Оператор",
        "total_devices": total_devices,
        "online_devices": online_count,
        "offline_devices": offline_count,
        "unreturned_devices": unreturned,
        "user_devices": user_devices
    }

def generate_evening_report(
    user: Dict[str, Any],
    devices: List[Dict[str, Any]]
) -> Dict[str, Any]:
    user_devices = filter_user_devices(user, devices)
    total_devices = len(user_devices)
    
    active_devices = []
    offline_count = 0

    for dev in user_devices:
        is_on = (dev.get("powerStatus") == "On" or dev.get("isOnline") is True)
        if is_on:
            active_devices.append({
                "id": dev.get("id"),
                "name": dev.get("name") or dev.get("id"),
                "building": dev.get("building") or "Общие группы",
                "floor": dev.get("floor") or "1 этаж",
                "room": dev.get("room") or dev.get("group") or "—",
                "ip": dev.get("ip") or "—"
            })
        else:
            offline_count += 1

    return {
        "user_id": user.get("id"),
        "user_name": user.get("displayName") or user.get("username") or "Оператор",
        "total_devices": total_devices,
        "online_count": len(active_devices),
        "offline_count": offline_count,
        "active_devices": active_devices,
        "user_devices": user_devices
    }

def format_morning_report_message(report: Dict[str, Any]) -> str:
    user_name = report.get("user_name", "Оператор")
    total = report.get("total_devices", 0)
    online = report.get("online_devices", 0)
    offline = report.get("offline_devices", 0)
    unreturned = report.get("unreturned_devices", [])

    lines = [
        f"🌅 <b>Доброе утро, {user_name}!</b>",
        f"📅 <i>Утренний отчет по готовности рабочих станций</i>\n"
    ]

    if unreturned:
        lines.append(f"⚠️ <b>Не вернулись онлайн после ночных событий ({len(unreturned)} шт.):</b>")
        for u in unreturned:
            loc = f"{u.get('building')} / {u.get('floor')} / {u.get('room')}"
            lines.append(f"🔴 <b>{u.get('name')}</b> (<code>{u.get('id')}</code>)")
            lines.append(f"   📍 <i>{loc}</i> — {u.get('reason')}")
        lines.append("")
    else:
        lines.append("✅ <b>Ночных сбоев не зафиксировано</b>, все перезагрузки прошли успешно.\n")

    lines.append(f"📊 <b>Текущий статус парка (всего {total} ПК):</b>")
    lines.append(f"🟢 В сети: <b>{online}</b> ПК")
    lines.append(f"⚪️ Выключено: <b>{offline}</b> ПК")

    room_map = collections.defaultdict(lambda: {"total": 0, "online": 0})
    for d in report.get("user_devices", []):
        r_name = d.get("room") or d.get("group") or "Без кабинета"
        room_map[r_name]["total"] += 1
        if d.get("powerStatus") == "On" or d.get("isOnline") is True:
            room_map[r_name]["online"] += 1

    if room_map:
        lines.append("")
        lines.append("<blockquote expandable><b>Детализация по кабинетам:</b>")
        for r_name, stats in sorted(room_map.items()):
            lines.append(f"▫️ <b>{r_name}</b>: {stats['online']}/{stats['total']} 🟢")
        lines.append("</blockquote>")

    return "\n".join(lines)

def format_evening_report_message(report: Dict[str, Any]) -> str:
    user_name = report.get("user_name", "Оператор")
    total = report.get("total_devices", 0)
    online = report.get("online_count", 0)
    offline = report.get("offline_count", 0)
    active_devs = report.get("active_devices", [])

    lines = [
        f"🌇 <b>Добрый вечер, {user_name}!</b>",
        f"📅 <i>Вечерний отчет контроля питания рабочих станций</i>\n"
    ]

    if active_devs:
        lines.append(f"🔋 <b>Остались включенными на конец дня ({len(active_devs)} шт.):</b>")
        lines.append("<blockquote expandable>")
        for d in active_devs:
            loc = f"{d.get('building')} / {d.get('room')}"
            lines.append(f"• <b>{d.get('name')}</b> (<code>{d.get('id')}</code>) — <i>{loc}</i> [🟢 В сети]")
        lines.append("</blockquote>\n")
    else:
        lines.append("✅ <b>Все рабочие станции выключены.</b> Парк обесточен штатно.\n")

    lines.append(f"📊 <b>Итоговое состояние:</b> 🟢 В сети: <b>{online}</b> • ⚪️ Выключено: <b>{offline}</b> (всего {total} ПК)")
    return "\n".join(lines)

def should_send_user_report(user: Dict[str, Any], report_type: str, current_dt: Optional[datetime] = None) -> bool:
    if not user or not user.get("telegramChatId"):
        return False

    rep_cfg = user.get("telegramReports")
    if not rep_cfg or not rep_cfg.get("enabled", False):
        return False

    if current_dt is None:
        current_dt = datetime.now()

    days = rep_cfg.get("days", [0, 1, 2, 3, 4])
    if current_dt.weekday() not in days:
        return False

    curr_time_str = current_dt.strftime("%H:%M")

    if report_type == "morning":
        m_cfg = rep_cfg.get("morningReport", {})
        if not m_cfg.get("enabled", True):
            return False
        return m_cfg.get("time", "08:00") == curr_time_str
    elif report_type == "evening":
        e_cfg = rep_cfg.get("eveningReport", {})
        if not e_cfg.get("enabled", True):
            return False
        return e_cfg.get("time", "20:00") == curr_time_str

    return False

async def send_scheduled_report_to_user(user: Dict[str, Any], report_type: str) -> bool:
    chat_id = str(user.get("telegramChatId", "")).strip()
    if not chat_id:
        return False
    from backend.app.api.v1.telegram import load_config, get_httpx_client, load_devices
    from backend.app.api.v1.devices import load_device_power_logs

    cfg = load_config()
    token = (cfg.get("botToken") or "").strip()
    if not token or not cfg.get("enabled", True):
        return False

    devices = load_devices()
    power_logs = load_device_power_logs()

    if report_type == "morning":
        rep = generate_morning_report(user, devices, power_logs)
        text = format_morning_report_message(rep)
        keyboard = []
        if rep.get("unreturned_devices") and user.get("role") != "Наблюдатель":
            keyboard.append([{"text": f"⚡️ Включить проблемные ПК ({len(rep['unreturned_devices'])})", "callback_data": "report:wakeproblems"}])
        keyboard.append([{"text": "📋 Меню отчетов", "callback_data": "report:menu"}])
        effect_id = "5046509860389126442"  # 🎉 Confetti for morning readiness
    else:
        rep = generate_evening_report(user, devices)
        text = format_evening_report_message(rep)
        keyboard = []
        if rep.get("active_devices") and user.get("role") != "Наблюдатель":
            keyboard.append([{"text": f"🛑 Выключить оставшиеся ({len(rep['active_devices'])})", "callback_data": "report:shutdownactive"}])
        keyboard.append([{"text": "📋 Меню отчетов", "callback_data": "report:menu"}])
        effect_id = None

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": keyboard}
    }
    if effect_id:
        payload["message_effect_id"] = str(effect_id)

    try:
        async with get_httpx_client(cfg, timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200 and "message_effect_id" in payload:
                payload.pop("message_effect_id")
                resp = await client.post(url, json=payload)
            return resp.status_code == 200
    except Exception as e:
        print(f"[Scheduled Report Error] Failed sending {report_type} report to {chat_id}: {e}")
        return False


