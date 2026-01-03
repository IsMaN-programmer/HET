import asyncio
import os
import json
import aiohttp
import datetime
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import BOT_TOKEN
with open("texts.json", "r", encoding="utf-8") as f:
    TEXTS = json.load(f)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔑 Ввести API HET")],
        [KeyboardButton(text="➕ Добавить аккаунт"), KeyboardButton(text="❌ Удалить аккаунт")],
        [KeyboardButton(text="⚡ Сегодняшнее потребление")],
        [KeyboardButton(text="📊 Дневной график"), KeyboardButton(text="📈 Месячный график")]
    ],
    resize_keyboard=True
)
user_states = {}
user_api_keys = {}
accounts_file = "accounts.json"
def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []
def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
@router.message(F.text == "/start")
async def cmd_start(message: types.Message):
    await message.answer(TEXTS["start"], reply_markup=main_kb)
@router.message(F.text == "🔑 Ввести API HET")
async def ask_api_key(message: types.Message):
    await message.answer("🔑 Введите ваш API‑ключ HET:")
    user_api_keys[message.from_user.id] = None  # ожидаем ввод
@router.message()
async def handle_api_or_commands(message: types.Message):
    user_id = message.from_user.id
    if user_api_keys.get(user_id) is None:
        api_key = message.text.strip()
        user_api_keys[user_id] = api_key
        await message.answer("✅ API‑ключ сохранён! Теперь можно смотреть баланс и графики.")
        return
    if user_states.get(user_id) == "awaiting_account_number":
        account_number = message.text.strip()
        accounts = load_json(accounts_file)
        for acc in accounts:
            if acc["user_id"] == user_id and acc["account_number"] == account_number:
                await message.answer(TEXTS["account_exists"].format(account=account_number))
                return
        accounts.append({"user_id": user_id, "account_number": account_number})
        save_json(accounts_file, accounts)
        await message.answer(TEXTS["account_added"].format(account=account_number))
        user_states[user_id] = None
@router.message(F.text == "➕ Добавить аккаунт")
async def add_account_prompt(message: types.Message):
    await message.answer(TEXTS["add_prompt"])
    user_states[message.from_user.id] = "awaiting_account_number"
@router.message(F.text == "❌ Удалить аккаунт")
async def show_accounts_for_deletion(message: types.Message):
    user_id = message.from_user.id
    accounts = load_json(accounts_file)
    user_accounts = [acc["account_number"] for acc in accounts if acc["user_id"] == user_id]
    if not user_accounts:
        await message.answer(TEXTS["no_accounts"])
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=acc_num, callback_data=f"delete:{acc_num}")]
        for acc_num in user_accounts
    ])
    await message.answer(TEXTS["delete_prompt"], reply_markup=kb)
@router.callback_query(F.data.startswith("delete:"))
async def delete_selected_account(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    account_number = callback.data.split(":")[1]
    accounts = load_json(accounts_file)
    new_accounts = [acc for acc in accounts if not (acc["user_id"] == user_id and acc["account_number"] == account_number)]
    if len(new_accounts) < len(accounts):
        save_json(accounts_file, new_accounts)
        await callback.message.edit_text(TEXTS["account_deleted"].format(account=account_number))
    else:
        await callback.message.edit_text(TEXTS["account_not_found"].format(account=account_number))
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
async def show_accounts_for_consumption(message: types.Message):
    user_id = message.from_user.id
    accounts = load_json(accounts_file)
    user_accounts = [acc["account_number"] for acc in accounts if acc["user_id"] == user_id]
    if not user_accounts:
        await message.answer(TEXTS["no_accounts"])
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=acc_num, callback_data=f"consumption:{acc_num}")]
        for acc_num in user_accounts
    ])
    await message.answer(TEXTS["choose_account"], reply_markup=kb)
@router.callback_query(F.data.startswith("consumption:"))
async def show_consumption(callback: types.CallbackQuery):
    account_number = callback.data.split(":")[1]
    api_key = user_api_keys.get(callback.from_user.id)
    if not api_key:
        await callback.message.edit_text("❌ Сначала введите API‑ключ.")
        return
    data = await het_request(api_key, f"consumption/{account_number}/today")
    if not data:
        await callback.message.edit_text("⚠️ Не удалось получить данные от HET API.")
        return
    consumption = data.get("consumption_kwh", 0)
    balance = data.get("balance_sum", 0)
    warning = TEXTS["low_balance"] if balance < 10000 else ""
    await callback.message.edit_text(
        TEXTS["consumption"].format(account=account_number, consumption=consumption, balance=f"{balance:.2f}", warning=warning)
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
        await message.answer_photo(graph_url, caption=TEXTS["daily_graph_caption"])
    else:
        await message.answer(TEXTS["daily_graph_missing"])
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
        await message.answer_photo(graph_url, caption=TEXTS["monthly_graph_caption"])
    else:
        await message.answer(TEXTS["monthly_graph_missing"])
async def send_daily_usage():
    accounts = load_json(accounts_file)
    user_ids = set(acc["user_id"] for acc in accounts)
    for user_id in user_ids:
        await bot.send_message(user_id, TEXTS["daily_report"])
async def main():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_usage, "cron", hour=10, minute=0)
    scheduler.start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)
if __name__ == "__main__":
    asyncio.run(main())
