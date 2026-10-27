import sqlite3
from pathlib import Path


# Корневая директория проекта
BASE_DIR = Path(__file__).resolve().parents[2]

# Путь к базе данных
DB_PATH = BASE_DIR / "data" / "sleep_tracker.db"


def get_connection():
    """Создаёт подключение к базе данных SQLite."""

    # Создаём папку для базы данных, если она отсутствует
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Открываем подключение к базе данных
    return sqlite3.connect(DB_PATH, timeout=10)