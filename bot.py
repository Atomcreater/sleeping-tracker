import asyncio
import os

MONTHS = [
    "января", "февраля", "марта",
    "апреля", "мая", "июня",
    "июля", "августа", "сентября",
    "октября", "ноября", "декабря"
]

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv
from datetime import datetime
from save_sleep import start_sleep, finish_sleep
from history import get_sleep_history
from statistics import get_sleep_statistics, format_duration

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

dp = Dispatcher()


@dp.message(Command("start"))
async def start_command(message: Message):
    await message.answer(
        "🌙 Привет! Я Sleep Tracker.\n"
        "Я помогу тебе отслеживать режим сна.\n\n"
        "Напиши /help, чтобы узнать мои команды."
    )


@dp.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "📋 Доступные команды:\n\n"
        "/start — запустить бота\n"
        "/help — список команд\n\n"
        "Скоро здесь появится учёт сна!"
    )


async def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN не найден в файле .env")

    bot = Bot(token=TOKEN)
    try:
        print("Бот запущен!")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


@dp.message(Command("sleep"))
async def sleep_command(message: Message):
    user_id = message.from_user.id

    if start_sleep(user_id):
        await message.answer(
            "🌙 Начинаем отслеживание сна!\n"
            "Время засыпания сохранено.\n"
            "Когда проснёшься, отправь /wake."
        )
    else:
        await message.answer(
            "😴 У тебя уже есть активная запись сна."
        )


@dp.message(Command("wake"))
async def wake_command(message: Message):
    user_id = message.from_user.id
    duration = finish_sleep(user_id)

    if duration is None:
        await message.answer(
            "У тебя нет активной записи сна.\n"
            "Сначала отправь /sleep."
        )
        return

    hours, minutes = divmod(duration, 60)

    await message.answer(
        f"☀️ Доброе утро!\n"
        f"Ты спал {hours} ч {minutes} мин.\n"
        f"Результат сохранён в базе данных!"
    )

@dp.message(Command("history"))
async def history_command(message: Message):
    user_id = message.from_user.id
    records = get_sleep_history(user_id)

    if not records:
        await message.answer("У тебя нет записей о сне.")
        return

    response = "🌙 История сна:\n\n"
    for record in records:
        sleep_date, sleep_start, wake_up, duration_minutes = record

        date_obj = datetime.fromisoformat(sleep_date)
        day = date_obj.day
        month = MONTHS[date_obj.month - 1]
        year = date_obj.year
        formatted_date = f"{day} {month} {year} года"
        formatted_start = datetime.fromisoformat(sleep_start).strftime("%H:%M")
        formatted_wake_up = datetime.fromisoformat(wake_up).strftime("%H:%M")
        formatted_duration = format_duration(duration_minutes)

        response += f"📅 Дата: <b>{formatted_date}</b>\n"
        response += f"🌙 Заснул в: <b>{formatted_start}</b>\n"
        response += f"☀️ Проснулся в: <b>{formatted_wake_up}</b>\n"
        response += f"⏱ Продолжительность сна: <b>{formatted_duration}</b>\n\n"

    await message.answer(response, parse_mode="HTML")

@dp.message(Command("stats"))
async def stats_command(message: Message):
    user_id = message.from_user.id

    avg_duration, max_duration, min_duration = get_sleep_statistics(user_id)

    avg_sleep = format_duration(round(avg_duration))
    max_sleep = format_duration(max_duration)
    min_sleep = format_duration(min_duration)

    response = (
        "📊 Статистика сна\n\n"
        "За последние 7 записей:\n\n"
        f"💤 Средняя продолжительность: {avg_sleep}\n"
        f"🌙 Самый долгий сон: {max_sleep}\n"
        f"⏰ Самый короткий сон: {min_sleep}"
    )

    await message.answer(response)

if __name__ == "__main__":
    asyncio.run(main())


