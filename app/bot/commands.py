from datetime import datetime, timedelta, timezone
from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from app.bot.keyboards import main_menu, sleep_review_keyboard
from aiogram import F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from app.services.sleep_detector import find_sleep_intervals_from_db, merge_sleeping_intervals

from app.db.sleep import (
    start_sleep,
    finish_sleep,
    get_sleep_history,
    get_sleep_statistics,
    save_detected_sleep,
    get_pending_sleep,
    confirm_detected_sleep,
    get_detected_sleep_by_id,
    find_sleep_overlaps
)

router = Router()

class SleepCorrection(StatesGroup):
    choosing_field = State()
    choosing_part = State()
    waiting_for_value = State()

def sleep_review_keyboard(detected_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"confirm_sleep:{detected_id}"
                ),
                InlineKeyboardButton(
                    text="✏️ Исправить",
                    callback_data=f"correct_sleep:{detected_id}"
                )
            ]
        ]
    )

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
        "ℹ️ <i>Анализ основан на событиях активности, "
        "с iPhone. Взаимодействия с Telegram-ботом "
        "не учитываются. "
        "Отсутствие событий не подтверждает сон. "
        "Время указано приблизительно.</i>"
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

    save_detected_sleep(user_id, merged_intervals)

    response = format_merged_sleep_result(merged_intervals)
    await message.answer(response, parse_mode="HTML")

@router.message(Command("detect_test"))
async def detect_test_command(message: Message):
    TEST_USER_ID = 999999999

    intervals = find_sleep_intervals_from_db(TEST_USER_ID, source="test")
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

    save_detected_sleep(user_id, merged_intervals)

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

@router.message(Command("review"))
async def review_command(message: Message):
    user_id = message.from_user.id

    records = get_pending_sleep(user_id)

    if not records:
        await message.answer(
            "🌙 Нет оценок сна, ожидающих подтверждения.\n\n"
            "Для нового анализа отправь /detect."
        )
        return

    await message.answer(
        f"🌙 Найдено {len(records)} оценок сна для проверки."
    )

    for record_id, start, end, minutes, awake in records:
        start_dt = datetime.fromisoformat(start).astimezone(LOCAL_TZ)
        end_dt = datetime.fromisoformat(end).astimezone(LOCAL_TZ)

        text = (
            f"🌙 <b>Предполагаемый сон №{record_id}</b>\n\n"
            f"📅 Дата: {start_dt:%d.%m.%Y}\n"
            f"💤 Заснул: {start_dt:%H:%M}\n"
            f"☀️ Проснулся: {end_dt:%H:%M}\n"
            f"⏱ Продолжительность: {format_duration(minutes)}\n"
            f"🌗 Активность: {awake} мин\n\n"
            "Всё правильно?"
        )

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=sleep_review_keyboard(record_id)
        )


@router.message(Command("confirm"))
async def confirm_command(message: Message):
    parts = message.text.split()

    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer(
            "Укажи ID оценки, например: /confirm 2\n"
            "Посмотреть оценки: /review"
        )
        return

    result = confirm_detected_sleep(
        message.from_user.id,
        int(parts[1]),
    )
    await message.answer(result)


@router.message(Command("correct"))
async def correct_command(message: Message):
    parts = message.text.split()

    if len(parts) != 7:
        await message.answer(
            "Формат:\n"
            "/correct ID дата_начала время_начала "
            "дата_конца время_конца минуты_бодрствования\n\n"
            "Пример:\n"
            "/correct 2 2026-10-25 23:30 2026-10-26 07:00 10\n\n"
            "Время — московское (+03:00). "
            "Команда сразу сохраняет исправленный сон в историю."
        )
        return

    try:
        detected_id = int(parts[1])

        start = datetime.strptime(
            f"{parts[2]} {parts[3]}",
            "%Y-%m-%d %H:%M",
        ).replace(tzinfo=LOCAL_TZ)

        end = datetime.strptime(
            f"{parts[4]} {parts[5]}",
            "%Y-%m-%d %H:%M",
        ).replace(tzinfo=LOCAL_TZ)

        awake_minutes = int(parts[6])
    except ValueError:
        await message.answer(
            "Проверь ввод: ID и минуты — целые числа, "
            "даты — ГГГГ-ММ-ДД, время — ЧЧ:ММ."
        )
        return

    result = confirm_detected_sleep(
        message.from_user.id,
        detected_id,
        corrected=(
            start.isoformat(),
            end.isoformat(),
            awake_minutes,
        ),
    )
    await message.answer(result)

@router.callback_query(F.data.startswith("correct_sleep:"))
async def correct_sleep_button(
    callback: CallbackQuery,
    state: FSMContext
):
    try:
        detected_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(
            "Некорректный ID записи.",
            show_alert=True
        )
        return

     # Получаем исходный интервал из PostgreSQL
    record = get_detected_sleep_by_id(
        callback.from_user.id,
        detected_id
    )

    if record is None:
        await callback.answer(
            "Запись сна не найдена.",
            show_alert=True
        )
        return

    sleep_start, sleep_end, awake_minutes = record

    # Приводим даты к московскому времени
    start_dt = datetime.fromisoformat(
        str(sleep_start)
    ).astimezone(LOCAL_TZ)

    end_dt = datetime.fromisoformat(
        str(sleep_end)
    ).astimezone(LOCAL_TZ)

    await state.update_data(
        detected_id=detected_id,
        sleep_start=start_dt.isoformat(),
        sleep_end=end_dt.isoformat(),
        awake_minutes=awake_minutes
    )

    # Переходим в состояние выбора поля
    await state.set_state(SleepCorrection.choosing_field)

    await callback.answer()

    await callback.message.answer(
        "✏️ <b>Редактирование сна</b>\n\n"
        "Что будем исправлять?",
        parse_mode="HTML",
        reply_markup=correction_menu_keyboard()
    )

@router.callback_query(
    SleepCorrection.choosing_field,
    F.data.in_({"edit_sleep:start", "edit_sleep:end"})
)
async def choose_sleep_field(
    callback: CallbackQuery,
    state: FSMContext
):
    # Определяем, что пользователь хочет исправить
    field = callback.data.split(":")[1]

    # Запоминаем выбор
    await state.update_data(edit_field=field)

    # Переходим к выбору даты или времени
    await state.set_state(SleepCorrection.choosing_part)

    await callback.answer()

    if field == "start":
        text = "🌙 Редактирование времени засыпания"
    else:
        text = "☀️ Редактирование времени пробуждения"

    await callback.message.answer(
        f"<b>{text}</b>\n\n"
        "Что будем изменять?",
        parse_mode="HTML",
        reply_markup=correction_part_keyboard()
    )

@router.callback_query(
    SleepCorrection.choosing_part,
    F.data.in_({"edit_part:date", "edit_part:time"})
)
async def choose_sleep_part(
    callback: CallbackQuery,
    state: FSMContext
):
    # Получаем выбранную часть
    part = callback.data.split(":")[1]

    # Запоминаем, что пользователь хочет изменить
    await state.update_data(edit_part=part)

    # Переходим в режим ожидания сообщения
    await state.set_state(SleepCorrection.waiting_for_value)

    await callback.answer()

    if part == "date":
        text = (
            "📅 <b>Изменение даты</b>\n\n"
            "Введи новую дату в формате:\n"
            "<code>2026-10-19</code>"
        )
    else:
        text = (
            "🕐 <b>Изменение времени</b>\n\n"
            "Введи новое время в формате:\n"
            "<code>08:30</code>"
        )

    await callback.message.answer(
        text,
        parse_mode="HTML"
    )

@router.message(SleepCorrection.waiting_for_value, F.text)
async def process_sleep_value(
    message: Message,
    state: FSMContext
):
    data = await state.get_data()

    field = data["edit_field"]
    part = data["edit_part"]

    # Определяем, какой интервал редактируем
    key = "sleep_start" if field == "start" else "sleep_end"

    # Получаем исходную дату и время
    current_dt = datetime.fromisoformat(data[key])

    value = message.text.strip()

    try:
        if part == "date":
            # Проверяем формат даты
            new_date = datetime.strptime(value, "%Y-%m-%d").date()

            # Меняем только дату
            new_dt = current_dt.replace(
                year=new_date.year,
                month=new_date.month,
                day=new_date.day
            )

        else:
            # Проверяем формат времени
            new_time = datetime.strptime(value, "%H:%M").time()

            # Меняем только часы и минуты
            new_dt = current_dt.replace(
                hour=new_time.hour,
                minute=new_time.minute,
                second=0,
                microsecond=0
            )

    except ValueError:
        await message.answer(
            "❌ Неверный формат.\n\n"
            "Для даты используй: 2026-10-19\n"
            "Для времени: 08:30"
        )
        return

    # Формируем предполагаемый интервал
    start_dt = (
        new_dt
        if field == "start"
        else datetime.fromisoformat(data["sleep_start"])
    )

    end_dt = (
        new_dt
        if field == "end"
        else datetime.fromisoformat(data["sleep_end"])
    )

    # Проверяем порядок дат до сохранения
    if end_dt <= start_dt:
        await message.answer(
            "⚠️ Время пробуждения должно быть позже "
            "времени засыпания.\n\n"
            "Попробуй ввести другое значение."
        )
        return

    # Сохраняем только корректное изменение
    await state.update_data(**{
        key: new_dt.isoformat()
    })

    if end_dt <= start_dt:
        await message.answer(
            "⚠️ Время пробуждения должно быть позже "
            "времени засыпания.\n\n"
            "Измени дату или время ещё раз."
        )
        return

    duration_minutes = int(
        (end_dt - start_dt).total_seconds() // 60
    )

    # Возвращаемся в главное меню редактирования
    await state.set_state(SleepCorrection.choosing_field)

    await message.answer(
        "✅ <b>Изменение принято!</b>\n\n"
        f"🌙 Заснул: {start_dt:%d.%m.%Y %H:%M}\n"
        f"☀️ Проснулся: {end_dt:%d.%m.%Y %H:%M}\n"
        f"⏱ Продолжительность: "
        f"{format_duration(duration_minutes)}\n\n"
        "Что будем делать дальше?",
        parse_mode="HTML",
        reply_markup=correction_menu_keyboard()
    )

@router.callback_query(
    SleepCorrection.choosing_part,
    F.data == "edit_part:back"
)
async def back_to_correction_menu(
    callback: CallbackQuery,
    state: FSMContext
):
    await state.set_state(SleepCorrection.choosing_field)

    await callback.answer()

    await callback.message.answer(
        "✏️ <b>Редактирование сна</b>\n\n"
        "Что будем исправлять?",
        parse_mode="HTML",
        reply_markup=correction_menu_keyboard()
    )

@router.callback_query(
    SleepCorrection.choosing_field,
    F.data == "edit_sleep:cancel"
)
async def cancel_sleep_correction(
    callback: CallbackQuery,
    state: FSMContext
):
    await state.clear()

    await callback.answer("Редактирование отменено")

    await callback.message.answer(
        "❌ Редактирование сна отменено.\n\n"
        "Изменения не сохранены."
    )

@router.callback_query(
    SleepCorrection.choosing_field,
    F.data == "edit_sleep:save"
)
async def save_sleep_correction(
    callback: CallbackQuery,
    state: FSMContext
):
    data = await state.get_data()

    detected_id = data.get("detected_id")
    sleep_start = data.get("sleep_start")
    sleep_end = data.get("sleep_end")
    awake_minutes = data.get("awake_minutes", 0)

    if detected_id is None or not sleep_start or not sleep_end:
        await callback.answer(
            "Данные редактирования не найдены.",
            show_alert=True
        )
        return

    # Проверяем интервал перед сохранением
    start_dt = datetime.fromisoformat(sleep_start)
    end_dt = datetime.fromisoformat(sleep_end)

    if end_dt <= start_dt:
        await callback.answer(
            "Некорректный интервал сна.",
            show_alert=True
        )
        return

    # Ищем пересечения с существующими записями
    overlaps = find_sleep_overlaps(
        user_id=callback.from_user.id,
        new_start=sleep_start,
        new_end=sleep_end
    )

    if overlaps:
        text = (
            "⚠️ <b>Обнаружено пересечение интервалов сна!</b>\n\n"
            "🌙 <b>Ты пытаешься сохранить:</b>\n"
            f"{start_dt:%d.%m.%Y %H:%M} → "
            f"{end_dt:%d.%m.%Y %H:%M}\n\n"
            "📋 <b>Конфликтующие записи:</b>\n"
        )

        for record in overlaps[:5]:
            old_start = record["start"]
            old_end = record["end"]

            end_text = (
                old_end.strftime("%d.%m.%Y %H:%M")
                if old_end is not None
                else "Сон не завершён"
            )

            text += (
                f"\n<b>Запись №{record['id']}</b>\n"
                f"🌙 {old_start:%d.%m.%Y %H:%M}\n"
                f"☀️ {end_text}\n"
            )

        if len(overlaps) > 5:
            text += f"\nИ ещё пересечений: {len(overlaps) - 5}\n"

        text += (
            "\nИзмени время сна или отмени редактирование."
        )

        await callback.answer()

        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=correction_menu_keyboard()
        )
        return

    await callback.answer("Сохраняем изменения...")

    # Передаём исправленный интервал существующей функции
    result = confirm_detected_sleep(
        user_id=callback.from_user.id,
        detected_id=detected_id,
        corrected=(
            sleep_start,
            sleep_end,
            awake_minutes
        )
    )

    await callback.message.answer(result)

    # Завершаем редактирование только при успешном сохранении
    if result.startswith("Сон сохранён:"):
        await state.clear()

@router.callback_query(F.data.startswith("confirm_sleep:"))
async def confirm_sleep_button(callback: CallbackQuery):
    print(f"🔘 Нажата кнопка: {callback.data}", flush=True)

    try:
        detected_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(
            "Некорректный ID записи.",
            show_alert=True
        )
        return

    result = confirm_detected_sleep(
        callback.from_user.id,
        detected_id
    )

    await callback.answer()

    if result.startswith("Сон сохранён:"):
        await callback.message.edit_reply_markup(
            reply_markup=None
        )

    await callback.message.answer(
        f"🌙 {result}"
    )

@router.callback_query()
async def debug_callback(callback: CallbackQuery):
    print(
        f"DEBUG CALLBACK: {callback.data}",
        flush=True
    )

    await callback.answer(
        f"Получено: {callback.data}",
        show_alert=True
    )

def correction_menu_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌙 Засыпание",
                    callback_data="edit_sleep:start"
                ),
                InlineKeyboardButton(
                    text="☀️ Пробуждение",
                    callback_data="edit_sleep:end"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💾 Сохранить",
                    callback_data="edit_sleep:save"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="edit_sleep:cancel"
                )
            ]
        ]
    )

def correction_part_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📅 Дата",
                    callback_data="edit_part:date"
                ),
                InlineKeyboardButton(
                    text="🕐 Время",
                    callback_data="edit_part:time"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="edit_part:back"
                )
            ]
        ]
    )