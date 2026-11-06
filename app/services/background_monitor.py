import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from aiogram import Bot

from app.services.sleep_notification import (
    register_sleep_notifications,
    send_pending_sleep_notifications,
)
from app.db.activity import get_activity_events
from app.db.sleep import save_detected_sleep
from app.services.sleep_detector import (
    find_sleep_intervals,
    merge_sleeping_intervals,
)


def check_sleep_activity():
    user_id = os.getenv("SLEEP_TRACKER_USER_ID")

    if not user_id:
        logging.warning("Не задан SLEEP_TRACKER_USER_ID")
        return

    events = get_activity_events(
        user_id=int(user_id),
        source="iphone",
        days=7,
    )

    logging.info(
        "Получено %s событий активности iPhone",
        len(events),
    )

    if not events:
        logging.info("Нет событий для анализа сна")
        return

    last_event_time = max(
        datetime.fromisoformat(event[0])
        if isinstance(event[0], str)
        else event[0]
        for event in events
    )

    if last_event_time.tzinfo is None:
        last_event_time = last_event_time.replace(
            tzinfo=timezone(timedelta(hours=3))
        )

    now = datetime.now(timezone.utc)

    if now - last_event_time > timedelta(hours=24):
        logging.warning(
            "Последняя активность была более 24 часов назад. "
            "Автоматический анализ пропущен."
        )
        return

    intervals = find_sleep_intervals(events)
    merged_intervals = merge_sleeping_intervals(intervals)

    logging.info(
        "Найдено предполагаемых интервалов сна: %s",
        len(intervals),
    )

    for start, end, hours in intervals:
        logging.info(
            "🌙 Предполагаемый сон: %s → %s (%.1f ч)",
            start.strftime("%d.%m.%Y %H:%M"),
            end.strftime("%d.%m.%Y %H:%M"),
            hours,
        )

    logging.info(
        "После объединения осталось интервалов: %s",
        len(merged_intervals),
    )

    for period in merged_intervals:
        logging.info(
            "💤 Итоговый сон: %s → %s | Сон: %.1f ч | Активность: %.0f мин",
            period["start"].strftime("%d.%m.%Y %H:%M"),
            period["end"].strftime("%d.%m.%Y %H:%M"),
            period["sleep_minutes"] / 60,
            period["activity_minutes"],
        )

    if not merged_intervals:
        logging.info("Новых интервалов сна не обнаружено")
        return

    new_ids = save_detected_sleep(
        user_id=int(user_id),
        periods=merged_intervals,
    )

    if new_ids:
        logging.info(
            register_sleep_notifications(
                user_id=int(user_id),
                detected_ids=new_ids,
            ),
            "💾 Сохранено новых интервалов сна: %s. ID: %s",
            len(new_ids),
            new_ids,
        )

    else:
        logging.info(
            "Новых записей нет: интервалы уже существуют"
        )



async def background_sleep_monitor(bot: Bot):
    logging.info("🌙 Фоновый мониторинг сна запущен")

    while True:
        try:
            await asyncio.to_thread(check_sleep_activity)
        except Exception:
            logging.exception("Ошибка фонового анализа сна")

        try:
            user_id = os.getenv("SLEEP_TRACKER_USER_ID")

            if user_id:
                await send_pending_sleep_notifications(
                    bot=bot,
                    user_id=int(user_id),
                )
        except Exception:
            logging.exception("Ошибка обработки уведомлений")

        await asyncio.sleep(15 * 60)