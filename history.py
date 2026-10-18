import sqlite3
from pathlib import Path
from statistics import format_duration

def get_sleep_history(user_id):
    DB_PATH = Path(__file__).resolve().parent / "sleep_tracker.db"

    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()
    cursor.execute(""" 
    SELECT sleep_date, sleep_start, wake_up, duration_minutes  
    FROM sleep_records
    WHERE user_id = ?  
    ORDER BY sleep_date DESC, id DESC  
    LIMIT 7
    """,(user_id,))
    
    records = cursor.fetchall()
    connection.close()
    return records

if __name__ == "__main__":
    print(get_sleep_history(709631290))