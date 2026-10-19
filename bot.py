import asyncio
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from commands import router
from database import init_db

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")


async def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN не найден в файле .env")

    init_db()

    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    dp.include_router(router)

    try:
        print("Sleep Tracker запущен!")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
