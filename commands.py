from datetime import datetime, timedelta, timezone
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from keyboards import main_menu
from aiogram import F
from aiogram.types import CallbackQuery
from sleep_detector import find_sleep_intervals_from_db, merge_sleeping_intervals

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

LOCAL_TZ = timezone(timedelta(hours=3))

def format_duration(duration_minutes):
    minutes_total = int(duration_minutes or 0)
    hours, minutes = divmod(minutes_total, 60)
    return f"{hours} ч {minutes} мин"


def format_sleep_time(value):
    if not value:
        return "Не указано"

    if len(value) == 5 and ":" in value:
        return value

    try:
        dt = datetime.fromisoformat(value)

        if dt.tzinfo is not None:
            dt = dt.astimezone(LOCAL_TZ)

        return dt.strftime("%H:%M")

    except ValueError:
        return str(value)


def format_merged_sleep_result(periods):
    if not periods:
        return "🔎 Недостаточно данных для анализа сна."

    response = (
        "🌙 <b>Анализ сна завершён</b>\n\n"
        f"Найдено периодов сна: <b>{len(periods)}</b>\n\n"
    )

    for number, period in enumerate(periods, start=1):
        start = period["start"]
        end = period["end"]

        sleep_minutes = round(period["sleep_minutes"])
        activity_minutes = round(period["activity_minutes"])

        response += (
            f"💤 <b>Период №{number}</b>\n"
            f"🌙 Начало: {start:%d.%m.%Y %H:%M}\n"
            f"☀️ Окончание: {end:%d.%m.%Y %H:%M}\n"
            f"⏱ Оценка сна по активности: "
            f"{sleep_minutes // 60} ч {sleep_minutes % 60} мин\n"
        )

        if activity_minutes > 0:
            response += (
                f"🌗 Ночная активность: "
                f"{activity_minutes} мин\n"
            )

            for activity_start, activity_end, minutes in period["activity_periods"]:
                response += (
                    f"   • {activity_start:%H:%M}–"
                    f"{activity_end:%H:%M} "
                    f"({round(minutes)} мин)\n"
                )

        response += "\n"

    response += (
        "ℹ️ <i>Анализ основан только на взаимодействиях "
        "с ботом. Отсутствие событий не подтверждает сон. "
        "Указанное время является приблизительной оценкой.</i>"
    )

    return response


@router.message(Command("start"))
async def start_command(message: Message):
    await message.answer(
        "🌙 <b>Sleep Tracker</b>\n\n"
        "Добро пожаловать в твой трекер сна!\n\n"
        "Здесь ты можешь:\n"
        "💤 Отслеживать продолжительность сна\n"
        "📅 Просматривать историю\n"
        "📊 Анализировать статистику\n\n"
        "Выбери действие:",
        parse_mode="HTML",
        reply_markup=main_menu()
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

def format_sleep_history(records):
    if not records:
        return "У тебя нет завершённых записей о сне."

    response = "🌙 <b>История сна</b>\n\n"

    for sleep_date, sleep_start, wake_up, duration in records:
        date_obj = datetime.fromisoformat(sleep_date)

        formatted_date = (
            f"{date_obj.day} "
            f"{MONTHS[date_obj.month - 1]} "
            f"{date_obj.year} года"
        )

        response += (
            f"📅 Дата: <b>{formatted_date}</b>\n"
            f"🌙 Заснул в: <b>{format_sleep_time(sleep_start)}</b>\n"
            f"☀️ Проснулся в: <b>{format_sleep_time(wake_up)}</b>\n"
            f"⏱ Продолжительность: "
            f"<b>{format_duration(duration)}</b>\n\n"
        )

    return response


@router.message(Command("history"))
async def history_command(message: Message):
    records = get_sleep_history(message.from_user.id)

    await message.answer(
        format_sleep_history(records),
        parse_mode="HTML"
    )

def format_sleep_statistics(avg, maximum, minimum):
    return (
        "📊 <b>Статистика сна</b>\n\n"
        "За последние 7 завершённых записей:\n\n"
        f"💤 Средняя продолжительность: "
        f"<b>{format_duration(round(avg))}</b>\n"
        f"🌙 Самый долгий сон: "
        f"<b>{format_duration(maximum)}</b>\n"
        f"⏰ Самый короткий сон: "
        f"<b>{format_duration(minimum)}</b>"
    )

@router.message(Command("stats"))
async def stats_command(message: Message):
    statistics = get_sleep_statistics(message.from_user.id)

    await message.answer(
        format_sleep_statistics(*statistics),
        parse_mode="HTML"
    )

@router.message(Command("detect"))
async def detect_command(message: Message):
    user_id = message.from_user.id

    intervals = find_sleep_intervals_from_db(user_id)
    merged_intervals = merge_sleeping_intervals(intervals)

    response = format_merged_sleep_result(merged_intervals)
    await message.answer(response, parse_mode="HTML")

@router.message(Command("detect_test"))
async def detect_test_command(message: Message):
    TEST_USER_ID = 999999999

    intervals = find_sleep_intervals_from_db(TEST_USER_ID)
    merged_intervals = merge_sleeping_intervals(intervals)

    response = format_merged_sleep_result(merged_intervals)

    await message.answer(
        "🧪 <b>Тестовый режим</b>\n\n" + response,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "sleep")
async def sleep_button(callback: CallbackQuery):
    user_id = callback.from_user.id

    if start_sleep(user_id):
        text = (
            "🌙 <b>Сон начат!</b>\n\n"
            "Время начала сохранено.\n"
            "Когда проснёшься, нажми «Проснулся»."
        )
    else:
        text = "😴 У тебя уже есть активная запись сна."

    await callback.answer()
    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=main_menu()
    )


@router.callback_query(F.data == "wake")
async def wake_button(callback: CallbackQuery):
    user_id = callback.from_user.id
    duration = finish_sleep(user_id)

    if duration is None:
        text = "У тебя нет активной записи сна."
    else:
        text = (
            "☀️ <b>Доброе утро!</b>\n\n"
            f"Ты спал {format_duration(duration)}.\n"
            "Результат сохранён!"
        )

    await callback.answer()
    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=main_menu()
    )


@router.callback_query(F.data == "history")
async def history_button(callback: CallbackQuery):
    records = get_sleep_history(callback.from_user.id)

    await callback.answer()
    await callback.message.answer(
        format_sleep_history(records),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "stats")
async def stats_button(callback: CallbackQuery):
    statistics = get_sleep_statistics(callback.from_user.id)

    await callback.answer()
    await callback.message.answer(
        format_sleep_statistics(*statistics),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "detect")
async def detect_button(callback: CallbackQuery):
    user_id = callback.from_user.id

    intervals = find_sleep_intervals_from_db(user_id)
    merged_intervals = merge_sleeping_intervals(intervals)

    response = format_merged_sleep_result(merged_intervals)

    await callback.answer()
    await callback.message.answer(
        response,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "settings")
async def settings_button(callback: CallbackQuery):
    await callback.answer(
        "⚙️ Настройки появятся в следующих обновлениях!",
        show_alert=True
    )

