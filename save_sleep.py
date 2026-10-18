import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "sleep_tracker.db"


def start_sleep(user_id):
    now = datetime.now()

    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT id FROM sleep_records
            WHERE user_id = ? AND wake_up IS NULL
            LIMIT 1
        """, (user_id,))

        if cursor.fetchone():
            return False

        cursor.execute("""
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

    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()

        cursor.execute("""
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

        duration = int((now - start).total_seconds() // 60)

        cursor.execute("""
            UPDATE sleep_records
            SET wake_up = ?, duration_minutes = ?
            WHERE id = ?
        """, (
            now.isoformat(timespec="seconds"),
            duration,
            record_id
        ))

    return duration
