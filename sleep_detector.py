
from datetime import datetime, timedelta, timezone
from database import get_activity_events

LOCAL_TZ = timezone(timedelta(hours=3))

def normalize_datetime(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)

    if value.tzinfo is None:
        value = value.replace(tzinfo=LOCAL_TZ)

    return value.astimezone(LOCAL_TZ)


def merge_sleeping_intervals(intervals, max_gap_minutes=20):

    if not intervals:
        return []

    intervals = sorted(intervals, key=lambda item: item[0])

    merged = []

    current_start, current_end, _ = intervals[0]
    activity_periods = []

    for start, end, _ in intervals[1:]:
        gap_minutes = (start - current_end).total_seconds() / 60

        if 0 <= gap_minutes <= max_gap_minutes:
            if gap_minutes > 0:
                activity_periods.append((current_end, start, gap_minutes))

            current_end = end

        else:
            merged.append(build_sleep_result(current_start,current_end,activity_periods))

            current_start = start
            current_end = end
            activity_periods = []

    merged.append(build_sleep_result(current_start,current_end,activity_periods))

    return merged


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
    online_time = set()
    sleep_intervals = []

    for event_time, event_type, source in events:
        if event_type in ("online", "activity"):
            online_time.add(normalize_datetime(event_time))

    online_time = sorted(online_time)

    for start_dt, end_dt in zip(online_time, online_time[1:]):
        duration_time = end_dt - start_dt
        hours = duration_time.total_seconds() / 3600

        if (
            min_hours <= hours <= max_hours
            and (20 <= start_dt.hour or start_dt.hour <= 6)
        ):
            sleep_intervals.append((start_dt, end_dt, hours))

    return sleep_intervals


def find_sleep_intervals_from_db(user_id):
    events = get_activity_events(user_id)
    sleep_intervals = find_sleep_intervals(events)
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