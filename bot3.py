import asyncio
import json
import os
import datetime
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
        [KeyboardButton(text="➕ Добавить аккаунт"), KeyboardButton(text="❌ Удалить аккаунт")],
        [KeyboardButton(text="⚡ Сегодняшнее потребление")],
        [KeyboardButton(text="📊 Дневной график"), KeyboardButton(text="📈 Месячный график")]
    ],
    resize_keyboard=True
)

user_states = {}
accounts_file = "accounts.json"
usage_file = "daily_usage.json"

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
    await message.answer("👋 Добро пожаловать в HETMobile!", reply_markup=main_kb)

@router.message(F.text == "/accounts")
async def show_user_accounts(message: types.Message):
    user_id = message.from_user.id
    accounts = load_json(accounts_file)
    user_accounts = [acc["account_number"] for acc in accounts if acc["user_id"] == user_id]
    if user_accounts:
        await message.answer("📋 Ваши лицевые счета:\n" + "\n".join(user_accounts))
    else:
        await message.answer("❌ У вас нет добавленных лицевых счетов.")

@router.message(F.text == "➕ Добавить аккаунт")
async def add_account_prompt(message: types.Message):
    await message.answer("🔢 Введите лицевой счёт для добавления:")
    user_states[message.from_user.id] = "awaiting_account_number"

@router.message(F.text == "❌ Удалить аккаунт")
async def show_accounts_for_deletion(message: types.Message):
    user_id = message.from_user.id
    accounts = load_json(accounts_file)
    user_accounts = [acc["account_number"] for acc in accounts if acc["user_id"] == user_id]

    if not user_accounts:
        await message.answer("❌ У вас нет добавленных лицевых счетов.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=acc_num, callback_data=f"delete:{acc_num}")]
        for acc_num in user_accounts
    ])
    await message.answer("🗑 Выберите лицевой счёт для удаления:", reply_markup=kb)

@router.callback_query(F.data.startswith("delete:"))
async def delete_selected_account(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    account_number = callback.data.split(":")[1]
    accounts = load_json(accounts_file)

    new_accounts = [acc for acc in accounts if not (acc["user_id"] == user_id and acc["account_number"] == account_number)]
    if len(new_accounts) < len(accounts):
        save_json(accounts_file, new_accounts)
        await callback.message.edit_text(f"✅ Лицевой счёт '{account_number}' успешно удалён.")
    else:
        await callback.message.edit_text(f"❌ Лицевой счёт '{account_number}' не найден.")

@router.message(F.text == "⚡ Сегодняшнее потребление")
async def show_accounts_for_consumption(message: types.Message):
    user_id = message.from_user.id
    accounts = load_json(accounts_file)
    user_accounts = [acc["account_number"] for acc in accounts if acc["user_id"] == user_id]

    if not user_accounts:
        await message.answer("❌ У вас нет добавленных лицевых счетов.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=acc_num, callback_data=f"consumption:{acc_num}")]
        for acc_num in user_accounts
    ])
    await message.answer("📊 Выберите счёт для просмотра сегодняшнего потребления:", reply_markup=kb)

@router.callback_query(F.data.startswith("consumption:"))
async def show_consumption(callback: types.CallbackQuery):
    account_number = callback.data.split(":")[1]
    fake_consumption = 12.4
    fake_balance = 9542.42

    usage_entry = {
        "user_id": callback.from_user.id,
        "account": account_number,
        "date": datetime.date.today().isoformat(),
        "consumption": fake_consumption,
        "balance": fake_balance
    }
    data = load_json(usage_file)
    data.append(usage_entry)
    save_json(usage_file, data)

    warning = ""
    if fake_balance < 10000:
        warning = "\n⚠️ Ваш баланс ниже 10,000 сум. Пополните счёт!"

    await callback.message.edit_text(
        f"⚡ Сегодняшнее потребление по счёту '{account_number}': {fake_consumption} кВт⋅ч\n💰 Баланс: {fake_balance:.2f} сум{warning}"
    )

@router.message(F.text == "📊 Дневной график")
async def send_daily_graph(message: types.Message):
    graph_path = "D:/Net/daily_graph.png"
    if os.path.exists(graph_path):
        photo = FSInputFile(graph_path)
        await message.answer_photo(photo, caption="📊 Дневной график потребления")
    else:
        await message.answer("❌ Изображение дневного графика не найдено. Поместите файл в папку D:/Net.")

@router.message(F.text == "📈 Месячный график")
async def send_monthly_graph(message: types.Message):
    graph_path = "D:/Net/monthly_graph.png"
    if os.path.exists(graph_path):
        photo = FSInputFile(graph_path)
        await message.answer_photo(photo, caption="📈 Месячный график потребления")
    else:
        await message.answer("❌ Изображение месячного графика не найдено. Поместите файл в папку D:/Net.")

@router.message()
async def handle_account_input(message: types.Message):
    user_id = message.from_user.id
    if user_states.get(user_id) == "awaiting_account_number":
        account_number = message.text.strip()
        accounts = load_json(accounts_file)

        for acc in accounts:
            if acc["user_id"] == user_id and acc["account_number"] == account_number:
                await message.answer(f"⚠️ Лицевой счёт '{account_number}' уже добавлен. Введите другой:")
                return

        accounts.append({"user_id": user_id, "account_number": account_number})
        save_json(accounts_file, accounts)
        await message.answer(f"✅ Лицевой счёт '{account_number}' добавлен.")
        user_states[user_id] = None

# ⏰ Ежедневная задача
async def send_daily_usage():
    accounts = load_json(accounts_file)
    user_ids = set(acc["user_id"] for acc in accounts)
    for user_id in user_ids:
        await bot.send_message(user_id, "📤 Ежедневный отчёт: не забудьте проверить потребление энергии!")

async def main():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_usage, "cron", hour=10, minute=0)
    scheduler.start()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
