import asyncio
import os
import time
from typing import Dict, Any, Optional
import httpx

from backend.app.api.v1.telegram import (
    load_config,
    save_config,
    get_httpx_client,
    process_telegram_command,
    process_telegram_callback
)

class TelegramBotService:
    """
    Background service for Telegram Bot long-polling (getUpdates).
    Works seamlessly in isolated networks, behind NAT and SOCKS5/HTTP proxies
    without requiring public IP addresses, domain names, or incoming ports.
    Supports rich inline keyboard navigation, real-time command dispatch, and callbacks.
    """
    def __init__(self):
        self.is_running = False
        self.last_update_id = 0
        self._active_token = ""
        self._webhook_cleared = False

    async def start_polling_loop(self):
        if self.is_running:
            return
        self.is_running = True
        print("[Telegram Bot] Long polling background service started.")

        while self.is_running:
            try:
                cfg = load_config()
                bot_token = (cfg.get("botToken") or "").strip()
                enabled = cfg.get("enabled", True)

                # If bot is disabled or token is not configured yet, wait and re-check
                if not enabled or not bot_token:
                    await asyncio.sleep(3)
                    continue

                # Token changed or first run: ensure webhook is cleared so getUpdates works
                if self._active_token != bot_token:
                    self._active_token = bot_token
                    self._webhook_cleared = False
                    self.last_update_id = 0

                if not self._webhook_cleared:
                    try:
                        async with get_httpx_client(cfg, timeout=8.0) as client:
                            del_url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"
                            await client.get(del_url, params={"drop_pending_updates": False})
                            self._webhook_cleared = True
                            print(f"[Telegram Bot] Webhook cleared. Ready to poll updates.")
                    except Exception:
                        self._webhook_cleared = True

                # Long-poll getUpdates including callback queries
                params = {
                    "offset": self.last_update_id + 1 if self.last_update_id else 0,
                    "timeout": 15,
                    "allowed_updates": ["message", "edited_message", "callback_query"]
                }
                poll_url = f"https://api.telegram.org/bot{bot_token}/getUpdates"

                async with get_httpx_client(cfg, timeout=25.0) as client:
                    resp = await client.get(poll_url, params=params)

                    if resp.status_code == 200:
                        data = resp.json()
                        updates = data.get("result", [])

                        for update in updates:
                            u_id = update.get("update_id", 0)
                            if u_id > self.last_update_id:
                                self.last_update_id = u_id

                            # Case A: Inline button click (callback_query)
                            cb = update.get("callback_query")
                            if cb:
                                cb_id = cb.get("id")
                                cb_data = cb.get("data", "")
                                from_user = cb.get("from", {})
                                msg = cb.get("message", {})
                                chat = msg.get("chat", {})
                                chat_id = str(chat.get("id", ""))
                                message_id = msg.get("message_id")

                                print(f"[Telegram Bot] Inline click '{cb_data}' from {chat_id} (@{from_user.get('username', '')})")
                                cb_result = process_telegram_callback(chat_id, cb_data, from_user)

                                # 1. Answer callback query (stops spinner / displays toast notification)
                                if cb_id:
                                    try:
                                        ans_url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
                                        ans_payload = {
                                            "callback_query_id": cb_id,
                                            "text": cb_result.get("alert", "")
                                        }
                                        await client.post(ans_url, json=ans_payload)
                                    except Exception:
                                        pass

                                # 2. Edit existing message with updated card or view
                                if message_id and cb_result.get("text"):
                                    try:
                                        edit_url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
                                        edit_payload = {
                                            "chat_id": chat_id,
                                            "message_id": message_id,
                                            "text": cb_result["text"],
                                            "parse_mode": "HTML"
                                        }
                                        if cb_result.get("reply_markup"):
                                            edit_payload["reply_markup"] = cb_result["reply_markup"]
                                        await client.post(edit_url, json=edit_payload)
                                    except Exception:
                                        pass
                                continue

                            # Case B: Regular text message
                            msg = update.get("message") or update.get("edited_message")
                            if not msg:
                                continue

                            chat = msg.get("chat", {})
                            chat_id = str(chat.get("id", ""))
                            text = (msg.get("text") or "").strip()
                            from_user = msg.get("from", {})

                            if not chat_id or not text:
                                continue

                            u_name = from_user.get("username", "")
                            print(f"[Telegram Bot] Received '{text}' from chat {chat_id} (user: {u_name})")

                            # Dispatch through command router
                            reply_data = process_telegram_command(chat_id, text, from_user)

                            if reply_data:
                                try:
                                    send_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                                    if isinstance(reply_data, dict):
                                        send_payload = {
                                            "chat_id": chat_id,
                                            "text": reply_data.get("text", ""),
                                            "parse_mode": "HTML"
                                        }
                                        if reply_data.get("reply_markup"):
                                            send_payload["reply_markup"] = reply_data["reply_markup"]
                                    else:
                                        send_payload = {
                                            "chat_id": chat_id,
                                            "text": str(reply_data),
                                            "parse_mode": "HTML"
                                        }
                                    await client.post(send_url, json=send_payload)
                                except Exception as send_err:
                                    print(f"[Telegram Bot] Failed to send reply to {chat_id}: {send_err}")

                    elif resp.status_code == 409:
                        # Conflict: webhook is still registered on Telegram servers
                        self._webhook_cleared = False
                        await asyncio.sleep(2)
                    elif resp.status_code == 401:
                        # Invalid token
                        await asyncio.sleep(8)
                    else:
                        await asyncio.sleep(3)

            except (httpx.RequestError, httpx.TimeoutException):
                # Temporary network or proxy timeout: backoff quietly
                await asyncio.sleep(2)
            except Exception as loop_err:
                print(f"[Telegram Bot] Polling loop exception: {loop_err}")
                await asyncio.sleep(3)

telegram_bot_service = TelegramBotService()
