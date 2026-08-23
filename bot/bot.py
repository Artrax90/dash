import asyncio
import os
import sys
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "mock_bot_token_for_dev")
API_BASE_URL = os.getenv("API_BASE_URL", f"http://backend:{os.getenv('PORT', '2301')}/api/v1")

logging.basicConfig(level=logging.INFO)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 *Workstation Manager Bot*\n\n"
        "Централизованный бот управления парком физических станций.\n\n"
        "📋 *Доступные команды:*\n"
        "• `/status` — Оперативная сводка парка\n"
        "• `/wake <PC>` — Отправить Wake-on-LAN пакет\n"
        "• `/shutdown <PC>` — Инициировать выключение\n"
        "• `/reboot <PC>` — Перезагрузить компьютер\n"
        "• `/alerts` — Список критических алертов\n",
        parse_mode="Markdown"
    )

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    # Summary of fleet
    text = (
        "📊 *СВОДКА СОСТОЯНИЯ ПАРКА*\n\n"
        "• Всего ПК: *20*\n"
        "• 🟢 В сети (Онлайн): *16*\n"
        "• ⚪ Оффлайн: *3*\n"
        "• 🔴 Проблемы / Аварии: *2*\n"
        "• 👥 Активные RDP: *3*\n"
        "• 🛡 Аппаратный эталон: *19/20 в норме (1 расхождение)*\n"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_status")],
        [InlineKeyboardButton(text="🚨 Просмотр алертов", callback_data="view_alerts")]
    ])
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)

@dp.message(Command("alerts"))
async def cmd_alerts(message: types.Message):
    text = (
        "🚨 *АКТИВНЫЕ КРИТИЧЕСКИЕ АЛЕРТЫ:*\n\n"
        "1. `[PC-009]` *HARDWARE_MISMATCH*\n"
        "Изъятие RAM: 32 GB → 16 GB (Слот DIMM_B1)\n\n"
        "2. `[PC-009]` *POWER_OFF_FAILED*\n"
        "Сбой запланированного вечернего выключения."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ WoL PC-009", callback_data="wol_PC-009"),
         InlineKeyboardButton(text="✅ Подтвердить", callback_data="ack_ALT-101")]
    ])
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)

@dp.message(Command("wake"))
async def cmd_wake(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: `/wake <Имя ПК или ID>` (например: `/wake PC-001`)", parse_mode="Markdown")
        return
    
    target = args[1]
    await message.answer(f"⚡ Magic Packet (WoL) успешно отправлен на `{target}`", parse_mode="Markdown")

@dp.callback_query(F.data == "refresh_status")
async def cb_refresh(call: types.CallbackQuery):
    await call.answer("Данные обновлены!")

async def main():
    if TOKEN == "mock_bot_token_for_dev":
        print("[Telegram Bot] Bot is configured in standalone/mock mode.")
        return
    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
