import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "sleep_tracker.db"


def get_connection():
    return sqlite3.connect(DB_PATH, timeout=10)


def init_db():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS sleep_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                sleep_date TEXT NOT NULL,
                sleep_start TEXT NOT NULL,
                wake_up TEXT,
                duration_minutes INTEGER,
                source TEXT NOT NULL DEFAULT 'manual'
            )
        """)


def start_sleep(user_id):
    now = datetime.now()

    with get_connection() as connection:
        cursor = connection.execute("""
            SELECT id
            FROM sleep_records
            WHERE user_id = ? AND wake_up IS NULL
            LIMIT 1
        """, (user_id,))

        if cursor.fetchone():
            return False

        connection.execute("""
            INSERT INTO sleep_records
                (user_id, sleep_date, sleep_start, source)
            VALUES (?, ?, ?, ?)
        """, (
            user_id,
            now.date().isoformat(),
            now.isoformat(timespec="seconds"),
            "telegram"
        ))

    return True


def finish_sleep(user_id):
    now = datetime.now()

    with get_connection() as connection:
        cursor = connection.execute("""
            SELECT id, sleep_start
            FROM sleep_records
            WHERE user_id = ? AND wake_up IS NULL
            ORDER BY id DESC
            LIMIT 1
        """, (user_id,))

        record = cursor.fetchone()

        if record is None:
            return None

        record_id, sleep_start = record
        start = datetime.fromisoformat(sleep_start)

        duration = max(
            0,
            int((now - start).total_seconds() // 60)
        )

        connection.execute("""
            UPDATE sleep_records
            SET wake_up = ?, duration_minutes = ?
            WHERE id = ? AND user_id = ?
        """, (
            now.isoformat(timespec="seconds"),
            duration,
            record_id,
            user_id
        ))

    return duration


def get_sleep_history(user_id, limit=7):
    with get_connection() as connection:
        cursor = connection.execute("""
            SELECT sleep_date, sleep_start,
                   wake_up, duration_minutes
            FROM sleep_records
            WHERE user_id = ?
              AND wake_up IS NOT NULL
            ORDER BY sleep_date DESC, id DESC
            LIMIT ?
        """, (user_id, limit))

        return cursor.fetchall()


def get_sleep_statistics(user_id):
    with get_connection() as connection:
        cursor = connection.execute("""
            SELECT
                AVG(duration_minutes),
                MAX(duration_minutes),
                MIN(duration_minutes)
            FROM (
                SELECT duration_minutes
                FROM sleep_records
                WHERE user_id = ?
                  AND duration_minutes > 0
                ORDER BY sleep_date DESC, id DESC
                LIMIT 7
            )
        """, (user_id,))

        avg, maximum, minimum = cursor.fetchone()

        return (
            avg if avg is not None else 0,
            maximum if maximum is not None else 0,
            minimum if minimum is not None else 0
        )


if __name__ == "__main__":
    init_db()
    print("База данных готова!")
