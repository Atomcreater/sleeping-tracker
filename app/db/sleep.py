"""Операции со сном в PostgreSQL (psycopg 3).

Предполагается, что поля дат в таблицах пока имеют тип TEXT.
"""

from datetime import datetime, timedelta, timezone

from app.db.connection import get_connection


def get_current_time():
    """Возвращает текущее время в UTC."""
    return datetime.now(timezone.utc)


def _lock_user(cursor, user_id):
    """Блокировка операций со сном одного пользователя."""
    cursor.execute(
        "SELECT pg_advisory_xact_lock(%s::bigint)",
        (int(user_id),)
    )


def start_sleep(user_id):
    now = get_current_time()

    with get_connection() as connection:
        with connection.cursor() as cursor:
            _lock_user(cursor, user_id)
            cursor.execute("""
                SELECT id FROM sleep_records
                WHERE user_id = %s AND wake_up IS NULL
                LIMIT 1
            """, (user_id,))

            if cursor.fetchone():
                return False

            cursor.execute("""
                INSERT INTO sleep_records
                    (user_id, sleep_date, sleep_start, source)
                VALUES (%s, %s, %s, %s)
            """, (
                user_id,
                now.date().isoformat(),
                now.isoformat(timespec="seconds"),
                "telegram",
            ))

    return True


def finish_sleep(user_id):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            _lock_user(cursor, user_id)
            cursor.execute("""
                SELECT id, sleep_start FROM sleep_records
                WHERE user_id = %s AND wake_up IS NULL
                ORDER BY id DESC LIMIT 1
                FOR UPDATE
            """, (user_id,))
            record = cursor.fetchone()

            if record is None:
                return None

            record_id, sleep_start = record
            start = datetime.fromisoformat(sleep_start)
            # Старые записи без часового пояса считаем по прежней логике.
            now = datetime.now() if start.tzinfo is None else get_current_time()
            duration = max(0, int((now - start).total_seconds() // 60))

            cursor.execute("""
                UPDATE sleep_records
                SET wake_up = %s, duration_minutes = %s
                WHERE id = %s AND user_id = %s
            """, (now.isoformat(timespec="seconds"), duration, record_id, user_id))

    return duration


def get_sleep_history(user_id, limit=7):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT sleep_date, sleep_start, wake_up, duration_minutes
                FROM sleep_records
                WHERE user_id = %s AND wake_up IS NOT NULL
                ORDER BY sleep_date DESC, id DESC
                LIMIT %s
            """, (user_id, limit))
            return cursor.fetchall()


def get_sleep_statistics(user_id, limit=7):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT AVG(duration_minutes), MAX(duration_minutes),
                       MIN(duration_minutes)
                FROM (
                    SELECT duration_minutes FROM sleep_records
                    WHERE user_id = %s AND duration_minutes > 0
                    ORDER BY id DESC LIMIT %s
                ) AS recent_sleep
            """, (user_id, limit))
            avg, maximum, minimum = cursor.fetchone()

    return (avg or 0, maximum or 0, minimum or 0)




def save_detected_sleep(user_id, periods):
    new_ids = []
    local_tz = timezone(timedelta(hours=3))

    def normalize(value, sleep_date=None):
        if isinstance(value, datetime):
            dt = value
        else:
            try:
                dt = datetime.fromisoformat(str(value))
            except ValueError:
                if sleep_date is None:
                    raise
                dt = datetime.fromisoformat(
                    f"{sleep_date}T{value}"
                )

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=local_tz)

        return dt.astimezone(timezone.utc)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            _lock_user(cursor, user_id)

            cursor.execute("""
                SELECT sleep_start, sleep_end
                FROM detected_sleep
                WHERE user_id = %s
            """, (user_id,))

            detected_intervals = [
                (normalize(start), normalize(end))
                for start, end in cursor.fetchall()
            ]

            cursor.execute("""
                SELECT sleep_date, sleep_start, wake_up
                FROM sleep_records
                WHERE user_id = %s
            """, (user_id,))

            confirmed_intervals = []

            for sleep_date, start, end in cursor.fetchall():
                old_start = normalize(start, sleep_date)

                if end is None:
                    old_end = None
                else:
                    old_end = normalize(end, sleep_date)

                    # Поддержка старых записей в формате HH:MM
                    if old_end <= old_start and len(str(end)) <= 8:
                        old_end += timedelta(days=1)

                confirmed_intervals.append(
                    (old_start, old_end)
                )

            for period in periods:
                start = normalize(period["start"])
                end = normalize(period["end"])

                if end <= start:
                    continue

                # Не допускаем пересечения с обнаруженным сном
                duplicate = any(
                    start < old_end and end > old_start
                    for old_start, old_end in detected_intervals
                )

                # Не допускаем пересечения с подтверждённым сном
                if not duplicate:
                    duplicate = any(
                        end > old_start
                        and (old_end is None or start < old_end)
                        for old_start, old_end in confirmed_intervals
                    )

                if duplicate:
                    continue

                total_minutes = round(period["total_minutes"])
                activity_minutes = round(period["activity_minutes"])
                sleep_minutes = total_minutes - activity_minutes

                if total_minutes <= 0 or not 0 <= activity_minutes < total_minutes:
                    continue

                cursor.execute("""
                    INSERT INTO detected_sleep (
                        user_id,
                        sleep_start,
                        sleep_end,
                        total_minutes,
                        sleep_minutes,
                        activity_minutes
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, sleep_start, sleep_end)
                    DO NOTHING
                    RETURNING id
                """, (
                    user_id,
                    period["start"].isoformat(timespec="seconds"),
                    period["end"].isoformat(timespec="seconds"),
                    total_minutes,
                    sleep_minutes,
                    activity_minutes,
                ))

                result = cursor.fetchone()

                if result is not None:
                    new_ids.append(result[0])
                    detected_intervals.append((start, end))

    return new_ids




def get_pending_sleep(user_id):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT d.id, d.sleep_start, d.sleep_end,
                       d.sleep_minutes, d.activity_minutes
                FROM detected_sleep AS d
                WHERE d.user_id = %s
                  AND NOT EXISTS (
                      SELECT 1 FROM sleep_records AS s
                      WHERE s.user_id = d.user_id
                        AND s.source = 'detected_confirmed:' || d.id::text
                  )
                ORDER BY d.sleep_start DESC
                LIMIT 5
            """, (user_id,))
            return cursor.fetchall()


def confirm_detected_sleep(user_id, detected_id, corrected=None):
    local_tz = timezone(timedelta(hours=3))

    def parse(value, date=None):
        if isinstance(value, datetime):
            dt = value

        elif isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value)
            except ValueError:
                if date is None:
                    raise ValueError(
                        f"Для времени {value!r} необходимо указать дату"
                    )

                dt = datetime.fromisoformat(
                    f"{date}T{value}"
                )

        else:
            raise TypeError(
                f"Неподдерживаемый тип даты: {type(value)}"
            )

        if dt.tzinfo is None:
            return dt.replace(tzinfo=local_tz)

        return dt.astimezone(local_tz)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            # Все операции подтверждения и ручной записи для пользователя
            # используют один advisory lock, действующий до конца транзакции.
            _lock_user(cursor, user_id)
            cursor.execute("""
                SELECT sleep_start, sleep_end, sleep_minutes
                FROM detected_sleep
                WHERE id = %s AND user_id = %s
                FOR UPDATE
            """, (detected_id, user_id))
            row = cursor.fetchone()

            if row is None:
                return "Оценка не найдена."

            source = f"detected_confirmed:{detected_id}"
            cursor.execute("""
                SELECT 1 FROM sleep_records
                WHERE user_id = %s AND source = %s
            """, (user_id, source))
            if cursor.fetchone():
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

            cursor.execute("""
                SELECT sleep_date, sleep_start, wake_up
                FROM sleep_records
                WHERE user_id = %s
            """, (user_id,))

            for sleep_date, old_start, old_end in cursor.fetchall():

                old_start_dt = parse(old_start, sleep_date)

                if old_end is None:
                    old_end_dt = None
                else:
                    old_end_dt = parse(old_end, sleep_date)

                    # Если старый сон закончился после полуночи
                    if old_end_dt < old_start_dt:
                        old_end_dt += timedelta(days=1)

                if old_start_dt < end and (
                    old_end_dt is None or old_end_dt > start
                ):
                    return (
                        "Период пересекается с записью в истории "
                        "или незавершённым сном."
                    )

            cursor.execute("""
                INSERT INTO sleep_records (
                    user_id, sleep_date, sleep_start,
                    wake_up, duration_minutes, source
                ) VALUES (%s, %s, %s, %s, %s, %s)
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

def get_detected_sleep_by_id(user_id: int, detected_id: int):
    """
    Получает предполагаемый интервал сна по ID.
    Проверяет принадлежность записи пользователю.
    """

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT sleep_start, sleep_end, activity_minutes
                FROM detected_sleep
                WHERE id = %s AND user_id = %s
                """,
                (detected_id, user_id)
            )

            return cursor.fetchone()

def get_sleep_overlaps(user_id: int):
    """
    Возвращает записи сна пользователя для проверки пересечений.
    """

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    sleep_date,
                    sleep_start,
                    wake_up,
                    duration_minutes,
                    source
                FROM sleep_records
                WHERE user_id = %s
                ORDER BY sleep_date, sleep_start
                """,
                (user_id,)
            )

            return cursor.fetchall()

def find_sleep_overlaps(user_id: int, new_start: str, new_end: str):
    """
    Находит записи сна, пересекающиеся с указанным интервалом.
    Ничего не изменяет в PostgreSQL.
    """

    from datetime import datetime, timedelta, timezone

    local_tz = timezone(timedelta(hours=3))

    def parse_datetime(value, sleep_date=None):
        # Поддерживаем datetime и строки ISO
        if isinstance(value, datetime):
            dt = value
        else:
            value = str(value)

            try:
                dt = datetime.fromisoformat(value)
            except ValueError:
                # Старый формат HH:MM
                if sleep_date is None:
                    raise ValueError(
                        f"Неизвестный формат даты: {value}"
                    )

                dt = datetime.fromisoformat(
                    f"{sleep_date}T{value}"
                )

        # Приводим время к UTC+3
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=local_tz)
        else:
            dt = dt.astimezone(local_tz)

        return dt

    start_dt = parse_datetime(new_start)
    end_dt = parse_datetime(new_end)

    if end_dt <= start_dt:
        raise ValueError(
            "Время пробуждения должно быть позже засыпания."
        )

    records = get_sleep_overlaps(user_id)
    overlaps = []

    for record in records:
        (
            record_id,
            sleep_date,
            sleep_start,
            wake_up,
            duration_minutes,
            source
        ) = record

        # Незавершённый сон тоже может пересекаться
        old_start = parse_datetime(sleep_start, sleep_date)

        if wake_up is None:
            old_end = None
        else:
            old_end = parse_datetime(wake_up, sleep_date)

            # Для старых записей HH:MM учитываем переход через полночь
            if (
                len(str(wake_up)) == 5
                and old_end <= old_start
            ):
                old_end += timedelta(days=1)

        # Незавершённый сон считаем открытым интервалом
        is_overlap = (
            old_start < end_dt
            and (old_end is None or start_dt < old_end)
        )

        if is_overlap:
            overlaps.append({
                "id": record_id,
                "start": old_start,
                "end": old_end,
                "duration_minutes": duration_minutes,
                "source": source
            })

    return overlaps