import sqlite3
from pathlib import Path

db_path = Path(__file__).resolve().parent / "sleep_tracker.db"

connection = sqlite3.connect(db_path)
cursor = connection.cursor()

cursor.execute("PRAGMA table_info(sleep_records)")

columns = cursor.fetchall()

for column in columns:
    print(column[1], "-", column[2])

connection.close()
