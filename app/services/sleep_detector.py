from datetime import datetime, timedelta, timezone
from app.db.activity import get_activity_events

LOCAL_TZ = timezone(timedelta(hours=3))

def normalize_datetime(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)

    if value.tzinfo is None:
        value = value.replace(tzinfo=LOCAL_TZ)

    return value.astimezone(LOCAL_TZ)


def merge_sleeping_intervals(
    intervals,
    max_gap_minutes=20,
    min_hours=4,
    max_hours=12,
):
    if not intervals:
        return []

    intervals = sorted(intervals, key=lambda item: item[0])
    merged = []

    current_start, current_end, _ = intervals[0]
    activity_periods = []

    for start, end, _ in intervals[1:]:
        gap_minutes = (start - current_end).total_seconds() / 60

        if 0 <= gap_minutes <= max_gap_minutes:
            # Короткую активность между частями сна учитываем отдельно.
            if gap_minutes > 0:
                activity_periods.append(
                    (current_end, start, gap_minutes)
                )

            current_end = end

        else:
            merged.append(
                build_sleep_result(
                    current_start,
                    current_end,
                    activity_periods,
                )
            )

            current_start = start
            current_end = end
            activity_periods = []

    # Добавляем последний собранный период.
    merged.append(
        build_sleep_result(
            current_start,
            current_end,
            activity_periods,
        )
    )

    # Проверяем длительность после объединения частей ночи.
    return [
        period
        for period in merged
        if min_hours * 60 <= period["sleep_minutes"] <= max_hours * 60
        and period["total_minutes"] <= max_hours * 60
    ]

def build_sleep_result(start, end, activity_periods):
    total_minutes = (end - start).total_seconds() / 60

    activity_minutes = sum(period[2] for period in activity_periods)

    sleep_minutes = total_minutes - activity_minutes

    return {
        "start": start,
        "end": end,
        "total_minutes": total_minutes,
        "sleep_minutes": sleep_minutes,
        "activity_minutes": activity_minutes,
        "activity_periods": activity_periods,
    }


def find_sleep_intervals(events, min_hours=4, max_hours=12):
    # Приводим время к +03:00 и удаляем одинаковые события.
    points = sorted(
        {
            (normalize_datetime(event_time), event_type, source)
            for event_time, event_type, source in events
            if event_type in ("online", "offline", "activity")
        },
        key=lambda item: (item[0], item[1], item[2]),
    )

    sleep_intervals = []

    for current, following in zip(points, points[1:]):
        start_dt, event_type, source = current
        end_dt, next_type, _ = following

        # Конец промежутка должен подтверждаться новой активностью.
        if next_type not in ("online", "activity"):
            continue

        # Для iPhone отсчитываем отсутствие активности от закрытия.
        # Для прежних источников сохраняем оценку между событиями.
        starts_after_close = event_type == "offline"
        starts_after_activity = (
            source != "iphone"
            and event_type in ("online", "activity")
        )

        if not (starts_after_close or starts_after_activity):
            continue

        hours = (end_dt - start_dt).total_seconds() / 3600

        # Учитываем интервалы, которые начинаются ночью
        # или продолжают сон после кратковременного пробуждения.
        starts_at_night = start_dt.hour >= 20 or start_dt.hour <= 6

        # Учитываем минимальную длительность в зависимости от режима поиска.
        if min_hours <= hours <= max_hours and hours > 0 and starts_at_night:
            sleep_intervals.append((start_dt, end_dt, hours))

    return sleep_intervals


def find_sleep_intervals_from_db(user_id, source="iphone"):
    events = get_activity_events(user_id, source=source)

    sleep_intervals = find_sleep_intervals(
        events,
        min_hours=0,
    )

    return sleep_intervals



if __name__ == "__main__":
    activity = [
        ("2026-10-19T00:30:00", "online", "telegram"),
        ("2026-10-19T01:00:00", "online", "telegram"),
        ("2026-10-19T08:30:00", "online", "telegram"),
        ("2026-10-19T09:00:00", "offline", "telegram"),
        ("2026-10-19T10:00:00", "online", "telegram"),
        ("2026-10-19T13:00:00", "online", "telegram"),
    ]

    print(find_sleep_intervals(activity))