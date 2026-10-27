from app.db.connection import get_connection


def init_db():
    """Создаёт таблицы базы данных, если они ещё не существуют."""

    with get_connection() as connection:

        # Таблица записей о сне.
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

        # Таблица событий активности.
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

        # Таблица автоматически обнаруженных периодов сна.
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

        # Индекс для быстрого поиска событий активности.
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_activity_user_time
            ON activity_events(user_id, event_time)
        """)

        # Таблица для отслеживания утренних уведомлений.
        connection.execute("""
            CREATE TABLE IF NOT EXISTS sleep_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                detected_sleep_id INTEGER NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN (
                        'pending',
                        'sending',
                        'sent',
                        'confirmed',
                        'failed'
                    )),
                telegram_message_id INTEGER,
                sent_at TEXT,
                last_error TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (detected_sleep_id)
                    REFERENCES detected_sleep(id)
            )
        """)