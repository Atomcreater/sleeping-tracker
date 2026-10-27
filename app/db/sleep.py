from datetime import datetime, timezone, timedelta
from app.db.connection import get_connection

def get_current_time():
    """Возвращает текущее время в UTC."""
    return datetime.now(timezone.utc)


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


def save_detected_sleep(user_id, periods):
    with get_connection() as connection:
        for period in periods:
            # Сохраняем целые минуты с согласованной суммой.
            total_minutes = round(period["total_minutes"])
            activity_minutes = round(period["activity_minutes"])
            sleep_minutes = total_minutes - activity_minutes

            connection.execute("""
                INSERT INTO detected_sleep (
                    user_id,
                    sleep_start,
                    sleep_end,
                    total_minutes,
                    sleep_minutes,
                    activity_minutes
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, sleep_start, sleep_end)
                DO UPDATE SET
                    total_minutes = excluded.total_minutes,
                    sleep_minutes = excluded.sleep_minutes,
                    activity_minutes = excluded.activity_minutes
            """, (
                user_id,
                period["start"].isoformat(timespec="seconds"),
                period["end"].isoformat(timespec="seconds"),
                total_minutes,
                sleep_minutes,
                activity_minutes,
            ))

def get_pending_sleep(user_id):
    with get_connection() as connection:
        return connection.execute("""
            SELECT d.id, d.sleep_start, d.sleep_end,
                   d.sleep_minutes, d.activity_minutes
            FROM detected_sleep AS d
            WHERE d.user_id = ?
              AND NOT EXISTS (
                  SELECT 1
                  FROM sleep_records AS s
                  WHERE s.user_id = d.user_id
                    AND s.source = 'detected_confirmed:' || d.id
              )
            ORDER BY d.sleep_start DESC
            LIMIT 5
        """, (user_id,)).fetchall()


def confirm_detected_sleep(user_id, detected_id, corrected=None):
    local_tz = timezone(timedelta(hours=3))

    def parse(value):
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=local_tz)
        return dt.astimezone(local_tz)

    with get_connection() as connection:
        # Проверка и сохранение выполняются одной транзакцией.
        connection.execute("BEGIN IMMEDIATE")

        row = connection.execute("""
            SELECT sleep_start, sleep_end, sleep_minutes
            FROM detected_sleep
            WHERE id = ? AND user_id = ?
        """, (detected_id, user_id)).fetchone()

        if row is None:
            return "Оценка не найдена."

        # Связываем запись истории с исходной оценкой.
        source = f"detected_confirmed:{detected_id}"

        existing = connection.execute("""
            SELECT 1 FROM sleep_records
            WHERE user_id = ? AND source = ?
        """, (user_id, source)).fetchone()

        if existing:
            return "Эта оценка уже подтверждена."

        if corrected is None:
            start, end = parse(row[0]), parse(row[1])
            minutes = row[2]
        else:
            start_text, end_text, awake_minutes = corrected
            start, end = parse(start_text), parse(end_text)
            total = int((end - start).total_seconds() // 60)

            if not 0 <= awake_minutes < total:
                return (
                    "Минуты бодрствования должны быть неотрицательными "
                    "и меньше длительности периода."
                )

            minutes = total - awake_minutes

        if end <= start or minutes <= 0:
            return (
                "Окончание должно быть позже начала, "
                "длительность сна — больше нуля."
            )

        if end > datetime.now(local_tz):
            return "Нельзя подтвердить сон с окончанием в будущем."

        # Не добавляем второй сон поверх существующей записи.
        records = connection.execute("""
            SELECT sleep_start, wake_up
            FROM sleep_records
            WHERE user_id = ?
        """, (user_id,)).fetchall()

        for old_start, old_end in records:
            if parse(old_start) < end and (
                old_end is None or parse(old_end) > start
            ):
                return (
                    "Период пересекается с записью в истории "
                    "или незавершённым сном."
                )

        connection.execute("""
            INSERT INTO sleep_records (
                user_id, sleep_date, sleep_start,
                wake_up, duration_minutes, source
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            start.date().isoformat(),
            start.isoformat(timespec="seconds"),
            end.isoformat(timespec="seconds"),
            minutes,
            source,
        ))

    return (
        f"Сон сохранён: {minutes // 60} ч {minutes % 60} мин.\n"
        "Смотри /history и /stats."
    )