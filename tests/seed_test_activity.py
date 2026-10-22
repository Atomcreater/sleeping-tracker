from datetime import datetime, timedelta, timezone

from database import init_db, get_connection, save_activity_event

TEST_USER_ID = 999999999
TEST_SOURCE = "test"

# Фиксированное время для воспроизводимых тестов
TZ = timezone(timedelta(hours=3))


def seed_test_activity():
    init_db()

    events = [
        (datetime(2026, 10, 20, 23, 0, tzinfo=TZ), "activity"),
        (datetime(2026, 10, 21, 3, 0, tzinfo=TZ), "activity"),
        (datetime(2026, 10, 21, 3, 15, tzinfo=TZ), "activity"),
        (datetime(2026, 10, 21, 8, 0, tzinfo=TZ), "activity"),
    ]

    # Удаляем только старые тестовые события
    with get_connection() as connection:
        connection.execute(
            """
            DELETE FROM activity_events
            WHERE user_id = ? AND source = ?
            """,
            (TEST_USER_ID, TEST_SOURCE),
        )

    for event_time, event_type in events:
        save_activity_event(
            user_id=TEST_USER_ID,
            event_time=event_time,
            event_type=event_type,
            source=TEST_SOURCE,
        )

    print(f"Добавлено тестовых событий: {len(events)}")


if __name__ == "__main__":
    seed_test_activity()
