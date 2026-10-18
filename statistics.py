import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "sleep_tracker.db"

def format_duration(duration_minutes):
    hours = duration_minutes // 60
    minutes = duration_minutes % 60
    return f"{hours} ч {minutes} мин"

connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()

cursor.execute("SELECT COUNT(*) FROM sleep_records")

result = cursor.fetchone()
count = result[0] if result else 0

cursor.execute("SELECT AVG(duration_minutes) FROM sleep_records")

result_1 = cursor.fetchone()
avg_duration = result_1[0] if result_1 is not None else 0


cursor.execute("SELECT MAX(duration_minutes), MIN(duration_minutes) FROM sleep_records")

result_2 = cursor.fetchone()
max_duration = result_2[0] if result_2[0] is not None else 0
min_duration = result_2[1] if result_2[1] is not None else 0

cursor.execute("SELECT sleep_date, sleep_start, wake_up, duration_minutes FROM sleep_records ORDER BY sleep_date DESC, id DESC LIMIT 7")

records = cursor.fetchall()

print('||История сна||')
if records is None or len(records) == 0:
    print("Нет записей о сне.")
else:   
    for record in records:
        sleep_date, sleep_start, wake_up, duration_minutes = record
        formatted_duration = format_duration(duration_minutes)
        print(f"Дата: {sleep_date} | Заснул в: {sleep_start} | Проснулся в: {wake_up} | Продолжительность сна: {formatted_duration}")   

connection.close()

