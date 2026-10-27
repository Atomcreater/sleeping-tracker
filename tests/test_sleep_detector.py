from datetime import datetime, timedelta, timezone
from app.services.sleep_detector import (
    find_sleep_intervals,
    merge_sleeping_intervals,
)


TZ = timezone(timedelta(hours=3))


def test_sleep_with_night_activity():
    events = [
        (datetime(2026, 10, 20, 23, 0, tzinfo=TZ), "activity", "test"),
        (datetime(2026, 10, 21, 3, 0, tzinfo=TZ), "activity", "test"),
        (datetime(2026, 10, 21, 3, 15, tzinfo=TZ), "activity", "test"),
        (datetime(2026, 10, 21, 8, 0, tzinfo=TZ), "activity", "test"),
    ]
def test_empty_events():
    """Нет событий — нет предполагаемого сна."""
    intervals = find_sleep_intervals([])
    assert intervals == []


def test_single_event():
    """Одного события недостаточно для анализа."""
    events = [
        (datetime(2026, 10, 20, 23, 0, tzinfo=TZ), "activity", "test")
    ]

    intervals = find_sleep_intervals(events)

    assert intervals == []


def test_short_interval():
    """Промежуток меньше 4 часов не считается сном."""
    events = [
        (datetime(2026, 10, 20, 23, 0, tzinfo=TZ), "activity", "test"),
        (datetime(2026, 10, 21, 1, 0, tzinfo=TZ), "activity", "test"),
    ]

    # Находим возможные промежутки сна
    intervals = find_sleep_intervals(events, min_hours=0)

    # Проверяем итоговую продолжительность после объединения
    merged = merge_sleeping_intervals(intervals)

    assert merged == []


def test_duplicate_events():
    """Одинаковые события не должны искажать результат."""
    events = [
        (datetime(2026, 10, 20, 23, 0, tzinfo=TZ), "activity", "test"),
        (datetime(2026, 10, 20, 23, 0, tzinfo=TZ), "activity", "test"),
        (datetime(2026, 10, 21, 8, 0, tzinfo=TZ), "activity", "test"),
    ]

    intervals = find_sleep_intervals(events)
    periods = merge_sleeping_intervals(intervals)

    assert len(periods) == 1

    period = periods[0]

    assert period["total_minutes"] == 540
    assert period["sleep_minutes"] == 540
    assert period["activity_minutes"] == 0
    assert len(period["activity_periods"]) == 0

def test_daytime_interval():
    """Дневной промежуток не должен считаться ночным сном."""
    events = [
        (datetime(2026, 10, 20, 10, 0, tzinfo=TZ), "activity", "test"),
        (datetime(2026, 10, 20, 17, 0, tzinfo=TZ), "activity", "test"),
    ]

    intervals = find_sleep_intervals(events)

    assert intervals == []


def test_too_long_interval():
    """Промежуток больше 12 часов отклоняется."""
    events = [
        (datetime(2026, 10, 20, 21, 0, tzinfo=TZ), "activity", "test"),
        (datetime(2026, 10, 21, 11, 0, tzinfo=TZ), "activity", "test"),
    ]

    intervals = find_sleep_intervals(events)

    assert intervals == []


def test_minimum_sleep_duration():
    """Проверяем нижнюю границу — ровно 4 часа."""
    events = [
        (datetime(2026, 10, 20, 23, 0, tzinfo=TZ), "activity", "test"),
        (datetime(2026, 10, 21, 3, 0, tzinfo=TZ), "activity", "test"),
    ]

    intervals = find_sleep_intervals(events)

    assert len(intervals) == 1
    assert intervals[0][2] == 4

def test_night_awaking():
    """Проверяем объединение сна с коротким ночным пробуждением."""
    events = [
        ("2026-10-25T23:30:00+03:00", "offline", "iphone"),
        ("2026-10-26T03:00:00+03:00", "online", "iphone"),
        ("2026-10-26T03:10:00+03:00", "offline", "iphone"),
        ("2026-10-26T08:00:00+03:00", "online", "iphone"),
    ]

    intervals = find_sleep_intervals(events, min_hours=0)
    results = merge_sleeping_intervals(intervals)

    assert len(results) == 1

    sleep = results[0]

    assert sleep["total_minutes"] == 510
    assert sleep["sleep_minutes"] == 500
    assert sleep["activity_minutes"] == 10
    assert len(sleep["activity_periods"]) == 1