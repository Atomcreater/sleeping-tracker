from datetime import datetime
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import (
    start_sleep,
    finish_sleep,
    get_sleep_history,
    get_sleep_statistics,
)

router = Router()

MONTHS = [
    "января", "февраля", "марта",
    "апреля", "мая", "июня",
    "июля", "августа", "сентября",
    "октября", "ноября", "декабря"
]


def format_duration(duration_minutes):
    minutes_total = int(duration_minutes or 0)
    hours, minutes = divmod(minutes_total, 60)
    return f"{hours} ч {minutes} мин"

def format_sleep_time(value):
    if not value:
        return "Не указано"

    # Старый формат: 23:00
    if len(value) == 5 and ":" in value:
        return value

    # Новый формат: 2026-10-18T23:00:00
    try:
        return datetime.fromisoformat(value).strftime("%H:%M")
    except ValueError:
        return str(value)

@router.message(Command("start"))
async def start_command(message: Message):
    await message.answer(
        "🌙 Привет! Я Sleep Tracker.\n"
        "Я помогу тебе отслеживать режим сна.\n\n"
        "Напиши /help, чтобы узнать мои команды."
    )


@router.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "📋 Доступные команды:\n\n"
        "/start — запустить бота\n"
        "/help — список команд\n"
        "/sleep — начать отслеживание сна\n"
        "/wake — завершить отслеживание сна\n"
        "/history — история сна\n"
        "/stats — статистика сна"
    )


@router.message(Command("sleep"))
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


@router.message(Command("wake"))
async def wake_command(message: Message):
    user_id = message.from_user.id
    duration = finish_sleep(user_id)

    if duration is None:
        await message.answer(
            "У тебя нет активной записи сна.\n"
            "Сначала отправь /sleep."
        )
        return

    await message.answer(
        "☀️ Доброе утро!\n"
        f"Ты спал {format_duration(duration)}.\n"
        "Результат сохранён в базе данных!"
    )


@router.message(Command("history"))
async def history_command(message: Message):
    print("DEBUG 1: Команда /history получена")

    user_id = message.from_user.id
    records = get_sleep_history(user_id)

    print(f"DEBUG 2: Найдено записей: {len(records)}")
    print(f"DEBUG 3: Данные: {records}")

    if not records:
        await message.answer("У тебя нет завершённых записей о сне.")
        return

    response = "🌙 История сна:\n\n"

    for sleep_date, sleep_start, wake_up, duration in records:
        date_obj = datetime.fromisoformat(sleep_date)

        formatted_date = (
            f"{date_obj.day} "
            f"{MONTHS[date_obj.month - 1]} "
            f"{date_obj.year} года"
        )

        formatted_start = format_sleep_time(sleep_start)
        formatted_wake_up = format_sleep_time(wake_up)
       

        response += (
            f"📅 Дата: <b>{formatted_date}</b>\n"
            f"🌙 Заснул в: <b>{formatted_start}</b>\n"
            f"☀️ Проснулся в: <b>{formatted_wake_up}</b>\n"
            f"⏱ Продолжительность сна: "
            f"<b>{format_duration(duration)}</b>\n\n"
        )
    print("DEBUG 4: Сообщение сформировано")
    print(response)

    await message.answer(response, parse_mode="HTML")


@router.message(Command("stats"))
async def stats_command(message: Message):
    user_id = message.from_user.id

    avg, maximum, minimum = get_sleep_statistics(user_id)

    response = (
        "📊 Статистика сна\n\n"
        "За последние 7 завершённых записей:\n\n"
        f"💤 Средняя продолжительность: "
        f"{format_duration(round(avg))}\n"
        f"🌙 Самый долгий сон: "
        f"{format_duration(maximum)}\n"
        f"⏰ Самый короткий сон: "
        f"{format_duration(minimum)}"
    )

    await message.answer(response)
