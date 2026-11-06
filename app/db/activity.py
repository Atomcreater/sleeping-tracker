from datetime import datetime
from app.db.connection import get_connection


def save_activity_event(user_id, event_time, event_type, source="telegram"):
    """Сохраняет событие активности пользователя."""

    if event_time is None:
        event_time = datetime.now().astimezone()

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO activity_events
                    (user_id, event_time, event_type, source)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, event_time, event_type, source)
                DO NOTHING
            """, (
                user_id,
                event_time.isoformat(timespec="seconds"),
                event_type,
                source
            ))

            saved = cursor.rowcount > 0

    return saved


def get_activity_events(
    user_id: int,
    limit: int | None = 100,
    source: str = "iphone",
    days: int | None = None,
):
    """
    Возвращает события активности пользователя.

    Если указан days, выбирает события за последние N дней.
    Если days не указан, использует limit.
    """

    if days is not None and days <= 0:
        raise ValueError("days должен быть положительным числом")

    if limit is not None and limit <= 0:
        raise ValueError("limit должен быть положительным числом")

    with get_connection() as connection:
        with connection.cursor() as cursor:

            if days is not None:
                cursor.execute("""
                    SELECT event_time, event_type, source
                    FROM activity_events
                    WHERE user_id = %s
                      AND source = %s
                      AND event_time::timestamptz >= NOW() - (%s * INTERVAL '1 day')
                    ORDER BY event_time::timestamptz ASC, id ASC
                """, (user_id, source, days))

            elif limit is not None:
                cursor.execute("""
                    SELECT event_time, event_type, source
                    FROM (
                        SELECT id, event_time, event_type, source
                        FROM activity_events
                        WHERE user_id = %s
                          AND source = %s
                        ORDER BY event_time::timestamptz DESC, id DESC
                        LIMIT %s
                    ) AS recent_events
                    ORDER BY event_time::timestamptz ASC, id ASC
                """, (user_id, source, limit))

            else:
                cursor.execute("""
                    SELECT event_time, event_type, source
                    FROM activity_events
                    WHERE user_id = %s
                      AND source = %s
                    ORDER BY event_time::timestamptz ASC, id ASC
                """, (user_id, source))

            return cursor.fetchall()