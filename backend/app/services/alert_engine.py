from typing import Dict, Any, Optional
import httpx
from datetime import datetime
from backend.app.core.config import settings

class AlertEngine:
    @staticmethod
    def should_notify(alert_type: str, policy: Optional[Dict[str, Any]]) -> bool:
        if not policy:
            return True
        
        mode = policy.get("mode", "Full")
        if mode in ["Muted", "Silent"]:
            return False
        
        if mode == "Critical Only":
            # In Critical Only mode, ignore non-critical peripheral events like USB drives and resource warnings
            if alert_type in ["USB_STORAGE_CHANGED", "HIGH_CPU", "HIGH_RAM", "HIGH_DISK", "RDP_TIMEOUT"]:
                return False
                
        if mode == "Hardware Only" and not (alert_type.startswith("HARDWARE") or alert_type == "USB_STORAGE_CHANGED"):
            return False
        
        events = policy.get("events_config", {}) or policy.get("events", {}) or {}
        
        if alert_type == "USB_STORAGE_CHANGED":
            # When in Custom mode, check explicit usbStorage toggle
            if mode == "Custom":
                return bool(events.get("usbStorage", False))
            # In Full mode, default to True unless explicitly disabled
            return bool(events.get("usbStorage", True))
            
        if alert_type == "HARDWARE_MISMATCH" and not events.get("hardwareChanges", True):
            return False
        if alert_type in ["POWER_FAILED", "POWER_OFF_FAILED"] and not events.get("powerStateFailed", True):
            return False
        if alert_type == "MORNING_WAKE_FAILED" and not events.get("morningWakeFailed", True):
            return False
        if alert_type == "EVENING_SHUTDOWN_FAILED" and not events.get("eveningShutdownFailed", True):
            return False
        if alert_type == "RDP_TIMEOUT" and not events.get("rdpSessionTimeout", True):
            return False
        if alert_type in ["OFFLINE", "AGENT_DISCONNECTED"] and not events.get("agentDisconnect", True):
            return False
        if alert_type in ["ONLINE", "AGENT_CONNECTED"] and not events.get("agentOnline", True):
            return False
        if alert_type == "HIGH_CPU" and not events.get("highCpuUsage", True):
            return False
        if alert_type == "HIGH_RAM" and not events.get("highRamUsage", True):
            return False
        if alert_type == "HIGH_DISK" and not events.get("highDiskUsage", True):
            return False
            
        return True

    @classmethod
    async def dispatch_alert(cls, alert: Dict[str, Any], policy: Optional[Dict[str, Any]] = None):
        """
        Process incoming alert and send via configured channels (Telegram Bot & WebSocket).
        """
        if not cls.should_notify(alert.get("type", ""), policy):
            return
        
        channels = policy.get("notify_channels", {}) or policy.get("notifyChannels", {}) if policy else {"webUi": True, "telegram": True}
        
        # 1. Telegram Bot broadcast
        if channels.get("telegram", True):
            try:
                from backend.app.api.v1.telegram import load_config, get_httpx_client
                cfg = load_config()
                token = (cfg.get("botToken") or settings.TELEGRAM_BOT_TOKEN or "").strip()
                
                if cfg.get("enabled", True) and cfg.get("alertsEnabled", True) and token:
                    events = cfg.get("eventsConfig", {}) or {}
                    a_type = alert.get("type", "")
                    
                    # Granular Telegram Event Filter:
                    # 1. USB Storage events: disabled by default in Telegram to prevent production notification floods!
                    if a_type == "USB_STORAGE_CHANGED" and not events.get("usbStorage", False):
                        print(f"[Telegram Alert] Skipped USB event ({alert.get('description')}) - Telegram usbStorage alerts disabled in settings.")
                        return
                    # 2. Hardware changes
                    if a_type == "HARDWARE_MISMATCH" and not events.get("hardwareChanges", True):
                        return
                    # 3. Power and Disconnect alerts
                    if a_type in ["POWER_FAILED", "EMERGENCY_SHUTDOWN", "OFFLINE", "AGENT_DISCONNECTED"]:
                        if not (events.get("criticalAlerts", True) or events.get("disconnectAlerts", True) or events.get("powerAlerts", True)):
                            print(f"[Telegram Alert] Skipped {a_type} ({alert.get('description')}) - Telegram disconnect/power alerts disabled.")
                            return
                    if a_type in ["ONLINE", "AGENT_CONNECTED", "BOOT"]:
                        if not (events.get("powerAlerts", True) or events.get("disconnectAlerts", True)):
                            return

                    # Collect ALL valid recipient chat IDs
                    target_chats = set()
                    global_chat = str(cfg.get("chatId", "")).strip()
                    if global_chat:
                        target_chats.add(global_chat)
                    
                    # Also include any active admins with telegramChatId
                    try:
                        from backend.app.api.v1.users import load_users
                        for u in load_users():
                            if u.get("enabled", True):
                                u_chat = str(u.get("telegramChatId", "")).strip()
                                if u_chat and (u_chat.isdigit() or (u_chat.startswith("-") and u_chat[1:].isdigit())):
                                    target_chats.add(u_chat)
                    except Exception as u_err:
                        print(f"[Telegram Alert] Could not load users: {u_err}")

                    if not target_chats:
                        print(f"[Telegram Alert] Notice: Alert not sent - no Telegram Chat ID configured in settings or user profiles.")
                        return

                    sev = str(alert.get("severity", "Warning")).upper()
                    dev_name = alert.get("device") or alert.get("deviceName") or alert.get("deviceId") or "Рабочая станция"
                    desc = alert.get("description") or "Зафиксировано изменение конфигурации"
                    
                    # Exact local timezone formatting (defaults to Europe/Moscow UTC+3)
                    tz_name = cfg.get("timezone") or os.getenv("TZ") or "Europe/Moscow"
                    now_str = ""
                    try:
                        from zoneinfo import ZoneInfo
                        now_str = datetime.now(ZoneInfo(tz_name)).strftime("%d.%m.%Y %H:%M:%S")
                    except Exception:
                        try:
                            from datetime import timezone, timedelta
                            now_str = datetime.now(timezone(timedelta(hours=3))).strftime("%d.%m.%Y %H:%M:%S")
                        except Exception:
                            now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

                    if a_type == "USB_STORAGE_CHANGED":
                        icon = "💾"
                        header = "СЪЕМНЫЙ USB-НАКОПИТЕЛЬ"
                    elif a_type in ["OFFLINE", "AGENT_DISCONNECTED"]:
                        icon = "🔌"
                        header = "ПОТЕРЯ СВЯЗИ / ПК ВЫКЛЮЧЕН"
                    elif a_type in ["ONLINE", "AGENT_CONNECTED", "BOOT"]:
                        icon = "🟢"
                        header = "СВЯЗЬ ВОССТАНОВЛЕНА / ПК ВКЛЮЧЕН"
                    elif a_type in ["POWER_FAILED", "EMERGENCY_SHUTDOWN"]:
                        icon = "⚡️"
                        header = "АВАРИЙНОЕ ВЫКЛЮЧЕНИЕ ПИТАНИЯ"
                    elif sev in ["CRITICAL", "HIGH"]:
                        icon = "🚨"
                        header = "КРИТИЧЕСКИЙ СБОЙ ОБОРУДОВАНИЯ"
                    elif sev in ["WARNING", "MEDIUM"]:
                        icon = "⚠️"
                        header = "ИЗМЕНЕНИЕ КОНФИГУРАЦИИ ПК"
                    else:
                        icon = "ℹ️"
                        header = "СИСТЕМНОЕ ОПОВЕЩЕНИЕ"

                    text = (
                        f"{icon} <b>{header}</b> [{sev}]\n\n"
                        f"🖥 <b>Устройство:</b> <code>{dev_name}</code>\n"
                        f"🏷 <b>Категория:</b> {alert.get('category', 'Hardware')}\n"
                        f"📝 <b>Событие:</b> {desc}\n"
                        f"⏱ <b>Время:</b> <i>{now_str}</i>"
                    )

                    async with get_httpx_client(cfg, timeout=15.0) as client:
                        for cid in target_chats:
                            try:
                                url = f"https://api.telegram.org/bot{token}/sendMessage"
                                resp = await client.post(url, json={"chat_id": cid, "text": text, "parse_mode": "HTML"})
                                if resp.status_code == 200:
                                    print(f"[Telegram Alert] Sent notification to chat {cid}: {desc}")
                                else:
                                    print(f"[Telegram Alert] HTTP {resp.status_code} sending to {cid}: {resp.text}")
                            except Exception as post_err:
                                print(f"[Telegram Alert] Failed sending to {cid}: {post_err}")
            except Exception as e:
                print(f"[Telegram Alert Dispatch Error] {e}")

    @classmethod
    async def trigger_device_offline(cls, session, device, reason: str = ""):
        """
        Record and dispatch device OFFLINE alert to DB, Telegram, and WebSocket.
        """
        try:
            from backend.app.models.alert import AlertModel, AlertPolicyModel
            from backend.app.api.v1.alerts import alerts_db
            from backend.app.core.ws import ws_manager
            from sqlalchemy import select
            
            # Deduplication: do not create multiple open OFFLINE alerts for the same device
            existing = await session.execute(
                select(AlertModel).where(
                    (AlertModel.device_id == device.id) &
                    (AlertModel.alert_type.in_(["OFFLINE", "AGENT_DISCONNECTED"])) &
                    (AlertModel.state == "Open")
                )
            )
            if existing.scalars().first():
                return
                
            now_utc = datetime.utcnow()
            dev_title = device.name or device.hostname or device.id
            alert_id = f"ALT-OFF-{device.id}-{int(now_utc.timestamp())}"
            desc = reason or f"Связь с агентом прервана (компьютер {dev_title} выключен или недоступен в сети)"
            
            alert_obj = AlertModel(
                id=alert_id,
                device_id=device.id,
                alert_type="OFFLINE",
                severity="Warning",
                description=desc,
                state="Open",
                created_at=now_utc
            )
            session.add(alert_obj)
            
            alert_dict = {
                "id": alert_id,
                "device": dev_title,
                "deviceName": dev_title,
                "deviceId": device.id,
                "type": "OFFLINE",
                "category": "Availability",
                "severity": "Warning",
                "state": "Open",
                "description": desc,
                "createdAt": now_utc.isoformat() + "Z",
                "time": now_utc.isoformat() + "Z",
                "timestamp": now_utc.isoformat() + "Z"
            }
            alerts_db.insert(0, alert_dict)
            if len(alerts_db) > 1000:
                alerts_db.pop()
                
            # Query device alert policy
            pol_res = await session.execute(
                select(AlertPolicyModel).where(
                    (AlertPolicyModel.device_id == device.id) | (AlertPolicyModel.device_id == device.hostname)
                )
            )
            pol_model = pol_res.scalar_one_or_none()
            policy_dict = {
                "mode": pol_model.mode,
                "events_config": pol_model.events_config,
                "notify_channels": pol_model.notify_channels
            } if pol_model else {"mode": "Full", "events_config": {"agentDisconnect": True}, "notify_channels": {"webUi": True, "telegram": True}}
            
            await cls.dispatch_alert(alert_dict, policy=policy_dict)
            await ws_manager.broadcast_event("alert.created", alert_dict)
        except Exception as err:
            print(f"[Trigger Device Offline Error] {err}")

    @classmethod
    async def trigger_device_online(cls, session, device, reason: str = ""):
        """
        Auto-resolve open OFFLINE alerts, dispatch ONLINE alert if policy enables it.
        """
        try:
            from backend.app.models.alert import AlertModel, AlertPolicyModel
            from backend.app.api.v1.alerts import alerts_db
            from backend.app.core.ws import ws_manager
            from sqlalchemy import select
            
            now_utc = datetime.utcnow()
            # 1. Resolve open OFFLINE alerts
            open_alerts = await session.execute(
                select(AlertModel).where(
                    (AlertModel.device_id == device.id) &
                    (AlertModel.alert_type.in_(["OFFLINE", "AGENT_DISCONNECTED"])) &
                    (AlertModel.state == "Open")
                )
            )
            for a in open_alerts.scalars().all():
                a.state = "Resolved"
                a.resolved_at = now_utc
                await ws_manager.broadcast_event("alert.updated", {
                    "id": a.id,
                    "deviceId": device.id,
                    "state": "Resolved",
                    "resolvedAt": now_utc.isoformat() + "Z"
                })
                
            for a in alerts_db:
                if a.get("deviceId") == device.id and a.get("type") in ["OFFLINE", "AGENT_DISCONNECTED"] and a.get("state") == "Open":
                    a["state"] = "Resolved"
                    
            # 2. Dispatch ONLINE alert
            pol_res = await session.execute(
                select(AlertPolicyModel).where(
                    (AlertPolicyModel.device_id == device.id) | (AlertPolicyModel.device_id == device.hostname)
                )
            )
            pol_model = pol_res.scalar_one_or_none()
            policy_dict = {
                "mode": pol_model.mode,
                "events_config": pol_model.events_config,
                "notify_channels": pol_model.notify_channels
            } if pol_model else {"mode": "Full", "events_config": {"agentOnline": True}, "notify_channels": {"webUi": True, "telegram": True}}
            
            if cls.should_notify("ONLINE", policy_dict):
                dev_title = device.name or device.hostname or device.id
                alert_id = f"ALT-ON-{device.id}-{int(now_utc.timestamp())}"
                desc = reason or f"Связь с агентом {dev_title} восстановлена (компьютер включен)"
                online_dict = {
                    "id": alert_id,
                    "device": dev_title,
                    "deviceName": dev_title,
                    "deviceId": device.id,
                    "type": "ONLINE",
                    "category": "Availability",
                    "severity": "Info",
                    "state": "Resolved",
                    "description": desc,
                    "createdAt": now_utc.isoformat() + "Z",
                    "time": now_utc.isoformat() + "Z",
                    "timestamp": now_utc.isoformat() + "Z"
                }
                await cls.dispatch_alert(online_dict, policy=policy_dict)
        except Exception as err:
            print(f"[Trigger Device Online Error] {err}")

alert_engine = AlertEngine()
