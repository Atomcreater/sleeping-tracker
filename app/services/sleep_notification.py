import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot

from app.bot.keyboards import sleep_review_keyboard
from app.db.connection import get_connection


LOCAL_TZ = timezone(timedelta(hours=3))


def get_notification_keyboard(detected_id: int):
    return sleep_review_keyboard(detected_id)


def register_sleep_notifications(user_id: int, detected_ids: list[int]):
    """Регистрирует новые уведомления без дублирования."""
    if not detected_ids:
        return

    with get_connection() as connection:
        with connection.cursor() as cursor:
            for detected_id in detected_ids:
                cursor.execute(
                    """
                    INSERT INTO sleep_notifications
                        (user_id, detected_sleep_id, status)
                    VALUES (%s, %s, 'pending')
                    ON CONFLICT (detected_sleep_id) DO NOTHING
                    """,
                    (user_id, detected_id),
                )


def claim_notification(user_id: int):
    """Атомарно забирает одно уведомление для отправки."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                WITH candidate AS (
                    SELECT n.id
                    FROM sleep_notifications AS n
                    JOIN detected_sleep AS d
                      ON d.id = n.detected_sleep_id
                    WHERE n.user_id = %s
                      AND d.user_id = %s
                      AND n.status = 'pending'
                      AND NOT EXISTS (
                          SELECT 1
                          FROM sleep_records AS s
                          WHERE s.user_id = n.user_id
                            AND s.source =
                                'detected_confirmed:' ||
                                n.detected_sleep_id::text
                      )
                    ORDER BY n.id
                    LIMIT 1
                    FOR UPDATE OF n SKIP LOCKED
                )
                UPDATE sleep_notifications AS n
                SET status = 'sending',
                    last_error = NULL
                FROM candidate
                WHERE n.id = candidate.id
                RETURNING n.id, n.detected_sleep_id
                """,
                (user_id, user_id),
            )
            return cursor.fetchone()


def get_notification_details(user_id: int, detected_id: int):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT sleep_start, sleep_end, sleep_minutes
                FROM detected_sleep
                WHERE id = %s AND user_id = %s
                """,
                (detected_id, user_id),
            )
            return cursor.fetchone()


def update_notification_status(
    notification_id: int,
    status: str,
    message_id=None,
    error=None,
):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE sleep_notifications
                SET status = %s,
                    telegram_message_id = %s,
                    sent_at = CASE
                        WHEN %s = 'sent'
                        THEN CURRENT_TIMESTAMP::text
                        ELSE sent_at
                    END,
                    last_error = %s
                WHERE id = %s
                  AND status = 'sending'
                """,
                (
                    status,
                    message_id,
                    status,
                    str(error)[:1000] if error else None,
                    notification_id,
                ),
            )


async def send_pending_sleep_notifications(bot: Bot, user_id: int):
    """Отправляет ожидающие уведомления пользователю."""
    while True:
        notification = claim_notification(user_id)

        if notification is None:
            return

        notification_id, detected_id = notification

        try:
            record = get_notification_details(user_id, detected_id)

            if record is None:
                raise ValueError("Оценка сна не найдена")

            start, end, minutes = record

            start_dt = datetime.fromisoformat(start).astimezone(LOCAL_TZ)
            end_dt = datetime.fromisoformat(end).astimezone(LOCAL_TZ)

            text = (
                "🌙 <b>Sleep Tracker обнаружил возможный сон</b>\n\n"
                f"📅 {start_dt:%d.%m.%Y}\n"
                f"💤 Засыпание: {start_dt:%H:%M}\n"
                f"☀️ Пробуждение: {end_dt:%H:%M}\n"
                f"⏱ Оценка сна: {minutes // 60} ч {minutes % 60} мин\n\n"
                "Всё правильно?"
            )

            message = await bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="HTML",
                reply_markup=get_notification_keyboard(detected_id),
            )

            try:
                update_notification_status(
                    notification_id,
                    "sent",
                    message_id=message.message_id,
                )
            except Exception:
                logging.exception(
                    "Сообщение Telegram отправлено, но статус уведомления %s "
                    "не удалось сохранить. Telegram message_id=%s",
                    notification_id,
                    message.message_id,
                )
                return

            logging.info(
                "Уведомление о сне %s отправлено",
                detected_id,
            )

        except Exception as exc:
            logging.exception(
                "Ошибка отправки уведомления %s",
                detected_id,
            )
            update_notification_status(
                notification_id,
                "failed",
                error=exc,
            )
            return
