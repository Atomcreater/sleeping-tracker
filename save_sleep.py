from datetime import datetime, timedelta, date
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "sleep_tracker.db"

start_time = input("Введите время начала сна (в формате ЧЧ:ММ): ")
end_time = input("Введите время окончания сна (в формате ЧЧ:ММ): ")

date_today = date.today()

start_hour,start_minute = map(int, start_time.split(':'))
end_hour,end_minute = map(int, end_time.split(':'))

start = datetime(date_today.year, date_today.month, date_today.day, start_hour, start_minute)
end = datetime(date_today.year, date_today.month, date_today.day, end_hour, end_minute)

if end < start:
    end += timedelta(days=1)

sleep_time = end - start

duration_minutes = int(sleep_time.total_seconds()  // 60)

connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()


cursor.execute(
    """
INSERT INTO sleep_records 
(sleep_date, sleep_start, wake_up, duration_minutes) 
VALUES (?, ?, ?, ?)
    """, (
        date_today.isoformat(),
        start_time,
        end_time,
        duration_minutes
    )
)

connection.commit()
connection.close()

print('Запись о сне успешно сохранена в базу данных!')