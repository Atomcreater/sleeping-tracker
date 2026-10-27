import sqlite3
from pathlib import Path


# Корневая папка проекта sleeping-tracker.
BASE_DIR = Path(__file__).resolve().parents[2]

# Путь к существующей базе данных SQLite.
DB_PATH = BASE_DIR / "data" / "sleep_tracker.db"

def get_connection():
    """Создаёт подключение к базе данных."""
    return sqlite3.connect(DB_PATH, timeout=10)