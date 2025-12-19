import asyncio
import os
import datetime
import aiohttp
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import BOT_TOKEN
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔑 Ввести API HET")],
        [KeyboardButton(text="⚡ Сегодняшнее потребление")],
        [KeyboardButton(text="📊 Дневной график"), KeyboardButton(text="📈 Месячный график")]
    ],
    resize_keyboard=True
)
user_api_keys = {}
@router.message(F.text == "/start")
async def cmd_start(message: types.Message):
    await message.answer("👋 Добро пожаловать в HETMobile!\nВведите свой API‑ключ для работы.", reply_markup=main_kb)
@router.message(F.text == "🔑 Ввести API HET")
async def ask_api_key(message: types.Message):
    await message.answer("🔑 Введите ваш API‑ключ HET:")
    user_api_keys[message.from_user.id] = None  # ожидаем ввод
@router.message()
async def handle_api_or_commands(message: types.Message):
    user_id = message.from_user.id
    # если ожидаем API ключ
    if user_api_keys.get(user_id) is None:
        api_key = message.text.strip()
        user_api_keys[user_id] = api_key
        await message.answer("✅ API‑ключ сохранён! Теперь можно смотреть баланс и графики.")
        return
async def het_request(api_key: str, endpoint: str):
    url = f"https://api.het.uz/{endpoint}"
    headers = {"Authorization": f"Bearer {api_key}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                return None
@router.message(F.text == "⚡ Сегодняшнее потребление")
async def show_consumption(message: types.Message):
    api_key = user_api_keys.get(message.from_user.id)
    if not api_key:
        await message.answer("❌ Сначала введите API‑ключ через кнопку 🔑.")
        return
    data = await het_request(api_key, "consumption/today")
    if not data:
        await message.answer("⚠️ Не удалось получить данные от HET API.")
        return
    consumption = data.get("consumption_kwh", 0)
    balance = data.get("balance_sum", 0)
    warning = ""
    if balance < 10000:
        warning = "\n⚠️ Ваш баланс ниже 10,000 сум. Пополните счёт!"
    await message.answer(
        f"⚡ Сегодняшнее потребление: {consumption} кВт⋅ч\n💰 Баланс: {balance:.2f} сум{warning}"
    )
@router.message(F.text == "📊 Дневной график")
async def send_daily_graph(message: types.Message):
    api_key = user_api_keys.get(message.from_user.id)
    if not api_key:
        await message.answer("❌ Сначала введите API‑ключ.")
        return
    data = await het_request(api_key, "graphs/daily")
    if not data:
        await message.answer("⚠️ Не удалось получить график.")
        return
    graph_url = data.get("graph_url")
    if graph_url:
        await message.answer_photo(graph_url, caption="📊 Дневной график потребления")
    else:
        await message.answer("❌ График не найден.")
@router.message(F.text == "📈 Месячный график")
async def send_monthly_graph(message: types.Message):
    api_key = user_api_keys.get(message.from_user.id)
    if not api_key:
        await message.answer("❌ Сначала введите API‑ключ.")
        return
    data = await het_request(api_key, "graphs/monthly")
    if not data:
        await message.answer("⚠️ Не удалось получить график.")
        return
    graph_url = data.get("graph_url")
    if graph_url:
        await message.answer_photo(graph_url, caption="📈 Месячный график потребления")
    else:
        await message.answer("❌ График не найден.")
async def send_daily_usage():
    for user_id, api_key in user_api_keys.items():
        if api_key:
            await bot.send_message(user_id, "📤 Ежедневный отчёт: проверьте потребление энергии!")
async def main():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_usage, "cron", hour=10, minute=0)
    scheduler.start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)
if __name__ == "__main__":
    asyncio.run(main())
