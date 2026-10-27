from datetime import datetime
from app.db.connection import get_connection


def save_activity_event(user_id, event_time, event_type, source="telegram"):
    """Сохраняет событие активности пользователя."""

    if event_time is None:
        event_time = datetime.now().astimezone()

    with get_connection() as connection:
        cursor = connection.execute("""
            INSERT OR IGNORE INTO activity_events
                (user_id, event_time, event_type, source)
            VALUES (?, ?, ?, ?)
        """, (
            user_id,
            event_time.isoformat(timespec="seconds"),
            event_type,
            source
        ))

    return cursor.rowcount > 0


def get_activity_events(
    user_id: int,
    limit: int = 100,
    source: str = "iphone",
):
    """Возвращает последние события пользователя из указанного источника."""

    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT event_time, event_type, source
            FROM (
                SELECT event_time, event_type, source
                FROM activity_events
                WHERE user_id = ? AND source = ?
                ORDER BY event_time DESC, id DESC
                LIMIT ?
            )
            ORDER BY event_time ASC
            """,
            (user_id, source, limit),
        )

        return cursor.fetchall()