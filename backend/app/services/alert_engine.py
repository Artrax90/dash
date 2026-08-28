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
        if mode == "Muted":
            return False
        if mode == "Hardware Only" and not alert_type.startswith("HARDWARE"):
            return False
        
        events = policy.get("events_config", {})
        if alert_type == "HARDWARE_MISMATCH" and not events.get("hardwareChanges", True):
            return False
        if alert_type == "POWER_FAILED" and not events.get("powerStateFailed", True):
            return False
        if alert_type == "MORNING_WAKE_FAILED" and not events.get("morningWakeFailed", True):
            return False
        if alert_type == "EVENING_SHUTDOWN_FAILED" and not events.get("eveningShutdownFailed", True):
            return False
        if alert_type == "RDP_TIMEOUT" and not events.get("rdpSessionTimeout", True):
            return False
            
        return True

    @classmethod
    async def dispatch_alert(cls, alert: Dict[str, Any], policy: Optional[Dict[str, Any]] = None):
        """
        Process incoming alert and send via configured channels (Telegram Bot & WebSocket).
        """
        if not cls.should_notify(alert.get("type", ""), policy):
            return
        
        channels = policy.get("notify_channels", {}) if policy else {"webUi": True, "telegram": True}
        
        # 1. Telegram Bot broadcast
        if channels.get("telegram", True):
            try:
                from backend.app.api.v1.telegram import load_config, get_httpx_client
                cfg = load_config()
                token = cfg.get("botToken") or settings.TELEGRAM_BOT_TOKEN
                chat_id = cfg.get("chatId")
                
                if cfg.get("enabled", True) and cfg.get("alertsEnabled", True) and token and chat_id:
                    # Verify event config from telegram settings
                    events = cfg.get("eventsConfig", {})
                    a_type = alert.get("type", "")
                    if a_type == "HARDWARE_MISMATCH" and not events.get("hardwareChanges", True):
                        return
                    if a_type in ["POWER_FAILED", "OFFLINE"] and not events.get("criticalAlerts", True):
                        return

                    sev = alert.get("severity", "Warning").upper()
                    icon = "🚨" if sev in ["CRITICAL", "HIGH"] else ("⚠️" if sev in ["WARNING", "MEDIUM"] else "ℹ️")
                    dev_name = alert.get("device") or alert.get("deviceName") or alert.get("deviceId") or "Рабочая станция"
                    desc = alert.get("description") or "Зафиксировано изменение конфигурации"
                    now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

                    text = (
                        f"{icon} <b>ОПОВЕЩЕНИЕ ОБОРУДОВАНИЯ</b> [{sev}]\n\n"
                        f"🖥 <b>Устройство:</b> <code>{dev_name}</code>\n"
                        f"🏷 <b>Категория:</b> {alert.get('category', 'Hardware')}\n"
                        f"📝 <b>Событие:</b> {desc}\n"
                        f"⏱ <b>Время:</b> <i>{now_str}</i>"
                    )

                    async with get_httpx_client(cfg, timeout=6.0) as client:
                        url = f"https://api.telegram.org/bot{token}/sendMessage"
                        resp = await client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
                        if resp.status_code == 200:
                            print(f"[Telegram Alert] Sent notification to chat {chat_id}: {desc}")
                        else:
                            print(f"[Telegram Alert] Telegram API returned status {resp.status_code}: {resp.text}")
            except Exception as e:
                print(f"[Telegram Alert Dispatch Error] {e}")

alert_engine = AlertEngine()
