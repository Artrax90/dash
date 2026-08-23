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
        Process incoming alert and send via configured channels (Web UI & Telegram).
        """
        if not cls.should_notify(alert.get("type", ""), policy):
            return
        
        channels = policy.get("notify_channels", {}) if policy else {"webUi": True, "telegram": True}
        
        # 1. Web UI broadcast (via WebSocket hub)
        # 2. Telegram Bot broadcast
        if channels.get("telegram", True) and settings.TELEGRAM_BOT_TOKEN:
            text = (
                f"🚨 *WORKSTATION ALERT* [{alert.get('severity', 'WARNING')}]\n\n"
                f"🖥 *Устройство:* `{alert.get('device', 'Unknown')}`\n"
                f"🏷 *Тип:* `{alert.get('type')}`\n"
                f"📝 *Описание:* {alert.get('description')}\n"
                f"⏱ *Время:* {datetime.utcnow().strftime('%H:%M:%S UTC')}"
            )
            # In a real setup, dispatch via telegram bot API to all subscribed chat IDs
            print(f"[Telegram Notification] {text}")

alert_engine = AlertEngine()
