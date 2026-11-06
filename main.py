
import asyncio
import logging
import os

import uvicorn
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from app.api.api import app
from app.bot.commands import router
from app.db.schema import init_db
from app.services.background_monitor import background_sleep_monitor


async def run_bot(bot: Bot):
    dp = Dispatcher()
    dp.include_router(router)

    logging.info("Telegram-бот запускается...")
    await dp.start_polling(bot)


async def run_api():
    port = int(os.getenv("SERVER_PORT", os.getenv("PORT", "8000")))

    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )

    server = uvicorn.Server(config)
    await server.serve()


async def main():
    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    init_db()

    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("Не найдена переменная BOT_TOKEN")

    bot = Bot(token=token)

    logging.info("Запускаем Sleep Tracker...")

    try:
        await asyncio.gather(
            run_bot(bot),
            run_api(),
            background_sleep_monitor(bot),
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
