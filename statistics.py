import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "sleep_tracker.db"

def format_duration(duration_minutes):
    hours = duration_minutes // 60
    minutes = duration_minutes % 60
    return f"{hours} ч {minutes} мин"

def get_sleep_statistics(user_id):
    avg_duration = get_sleep_avg7(user_id)
    max_duration, min_duration = get_sleep_max_min(user_id)

    return avg_duration, max_duration, min_duration


def get_sleep_avg7(user_id):
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT AVG(duration_minutes)
        FROM (
            SELECT duration_minutes
            FROM sleep_records
            WHERE duration_minutes > 0
            AND user_id = ?
            ORDER BY sleep_date DESC, id DESC
            LIMIT 7
        )
    """, (user_id,))
    result = cursor.fetchone()
    avg_duration = result[0] if result[0] is not None else 0
    connection.close()
    return avg_duration

def get_sleep_max_min(user_id):
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT MAX(duration_minutes), MIN(duration_minutes)
        FROM (
            SELECT duration_minutes
            FROM sleep_records
            WHERE duration_minutes > 0
            AND user_id = ?
            ORDER BY sleep_date DESC, id DESC
            LIMIT 7
        )
    """, (user_id,))
    result = cursor.fetchone()
    max_duration = result[0] if result[0] is not None else 0
    min_duration = result[1] if result[1] is not None else 0
    connection.close()
    return max_duration, min_duration

if __name__ == "__main__":
    user_id = 123456789  # Для теста замени на свой Telegram ID
    print(get_sleep_statistics(user_id))
