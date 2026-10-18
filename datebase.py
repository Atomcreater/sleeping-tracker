import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "sleep_tracker.db"

connection = sqlite3.connect(DB_PATH, timeout=10)
cursor = connection.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS sleep_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sleep_date TEXT NOT NULL,
    sleep_start TEXT NOT NULL,
    wake_up TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual'
)
""")

connection.commit()
connection.close()

print("База данных создана!")
