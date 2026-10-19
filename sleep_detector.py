
from datetime import datetime, timedelta


def detect_sleep(activity_times):
    """
    Ищет самый длинный ночной промежуток
    между событиями активности.
    """

    if len(activity_times) < 2:
        return None

    # Сортируем события по времени
    activity_times = sorted(activity_times)

    longest_sleep = None
    max_duration = timedelta(0)

    # Проверяем каждую пару соседних событий
    for i in range(len(activity_times) - 1):
        start = activity_times[i]
        end = activity_times[i + 1]

        duration = end - start

        # Рассматриваем интервалы от 4 до 14 часов
        if not timedelta(hours=4) <= duration <= timedelta(hours=14):
            continue

        # Интервал должен начинаться вечером или ночью
        if not (start.hour >= 20 or start.hour <= 3):
            continue

        # Интервал должен заканчиваться утром или днём
        if not (4 <= end.hour <= 14):
            continue

        if duration > max_duration:
            max_duration = duration
            longest_sleep = {
                "start": start,
                "end": end,
                "duration": duration,
            }

    return longest_sleep


if __name__ == "__main__":
    activity = [
        datetime(2026, 10, 18, 23, 30),
        datetime(2026, 10, 18, 21, 15),
        datetime(2026, 10, 19, 00, 30),
        datetime(2026, 10, 19, 8, 20),
        datetime(2026, 10, 19, 10, 10),
    ]

    result = detect_sleep(activity)

    if result:
        print("Предполагаемый период сна найден!")
        print("Начало:", result["start"])
        print("Конец:", result["end"])
        print("Длительность:", result["duration"])
    else:
        print("Подходящий ночной интервал не найден.")
