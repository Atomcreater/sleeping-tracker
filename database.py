import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "sleep_tracker.db"

def get_current_time():
    return datetime.now(timezone.utc)

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
    
        connection.execute("""
            CREATE TABLE IF NOT EXISTS activity_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_time TEXT NOT NULL,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'telegram',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, event_time, event_type, source)
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS detected_sleep (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                sleep_start TEXT NOT NULL,
                sleep_end TEXT NOT NULL,
                total_minutes INTEGER NOT NULL,
                sleep_minutes INTEGER NOT NULL,
                activity_minutes INTEGER NOT NULL,
                source TEXT NOT NULL DEFAULT 'activity_analysis',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, sleep_start, sleep_end)
            )
        """)
    
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_activity_user_time
            ON activity_events(user_id, event_time)
        """)



def start_sleep(user_id):
    now = get_current_time()

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
    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT id, sleep_start
            FROM sleep_records
            WHERE user_id = ? AND wake_up IS NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,)
        )

        record = cursor.fetchone()

        if record is None:
            return None

        record_id, sleep_start = record
        start = datetime.fromisoformat(sleep_start)

        if start.tzinfo is None:
            # Старые записи создавались по локальному времени.
            # Для них сохраняем прежний способ расчёта.
            now = datetime.now()
        else:
            now = get_current_time()

        duration = max(
            0,
            int((now - start).total_seconds() // 60)
        )

        connection.execute(
            """
            UPDATE sleep_records
            SET wake_up = ?, duration_minutes = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                now.isoformat(timespec="seconds"),
                duration,
                record_id,
                user_id
            )
        )

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


def get_sleep_statistics(user_id, limit=7):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT
                AVG(duration_minutes),
                MAX(duration_minutes),
                MIN(duration_minutes)
            FROM (
                SELECT duration_minutes
                FROM sleep_records
                WHERE user_id = ?
                  AND duration_minutes > 0
                ORDER BY id DESC
                LIMIT ?
            )
            """,
            (user_id, limit)
        )

        avg, maximum, minimum = cursor.fetchone()

    return (
        avg or 0,
        maximum or 0,
        minimum or 0
    )

def save_activity_event(user_id, event_time, event_type, source="telegram"):

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


def get_activity_events(user_id: int, limit: int = 100):
    with get_connection() as connection:
        cursor = connection.execute("""
            SELECT event_time, event_type, source
            FROM (
                SELECT event_time, event_type, source
                FROM activity_events
                WHERE user_id = ?
                ORDER BY event_time DESC, id DESC
                LIMIT ?
            )
            ORDER BY event_time ASC
        """, (user_id, limit))

        return cursor.fetchall()


