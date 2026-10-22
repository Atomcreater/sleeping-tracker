import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from activity_middleware import ActivityMiddleware
from commands import router
from database import init_db


async def main():
    # Загружаем переменные окружения
    load_dotenv()

    token = os.getenv("BOT_TOKEN")

    if not token:
        raise ValueError("BOT_TOKEN не найден в файле .env")

    # Подготавливаем базу данных
    init_db()

    # Создаём Telegram-бота
    bot = Bot(token=token)
    dp = Dispatcher()

    # Регистрируем активность пользователя
    activity_middleware = ActivityMiddleware()

    dp.message.outer_middleware(activity_middleware)
    dp.callback_query.outer_middleware(activity_middleware)

    # Подключаем обработчики команд
    dp.include_router(router)

    try:
        logging.info("Sleep Tracker запущен")
        await dp.start_polling(bot)

    finally:
        await bot.session.close()
        logging.info("Сессия Telegram-бота закрыта")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    asyncio.run(main())