import sqlite3
from app.db import activity

def test_activity_source_filter(monkeypatch):
    # Создаём временную базу данных в памяти
    connection = sqlite3.connect(":memory:")

    connection.execute("""
        CREATE TABLE activity_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_time TEXT NOT NULL,
            event_type TEXT NOT NULL,
            source TEXT NOT NULL
        )
    """)

    events = [
        (1, "2026-10-20T23:00:00+03:00", "offline", "iphone"),
        (1, "2026-10-21T03:00:00+03:00", "online", "bot_interaction"),
        (1, "2026-10-21T08:00:00+03:00", "online", "iphone"),
    ]

    connection.executemany(
        """
        INSERT INTO activity_events
            (user_id, event_time, event_type, source)
        VALUES (?, ?, ?, ?)
        """,
        events,
    )

    # Подменяем подключение к настоящей БД
    monkeypatch.setattr(
        activity,
        "get_connection",
        lambda: connection,
    )

    # По умолчанию получаем только события iPhone
    result = activity.get_activity_events(user_id=1)

    assert len(result) == 2
    assert all(event[2] == "iphone" for event in result)

    # Проверяем возможность выбрать другой источник
    telegram_events = activity.get_activity_events(
        user_id=1,
        source="bot_interaction",
    )

    assert len(telegram_events) == 1

    connection.close()