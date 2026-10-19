import asyncio
import os

from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

if not API_ID or not API_HASH:
    raise SystemExit(
        "Укажи API_ID и API_HASH в файле .env"
    )

SESSION_DIR = Path("sessions")
SESSION_DIR.mkdir(exist_ok=True)

client = TelegramClient(
    str(SESSION_DIR / "sleep_tracker"),
    int(API_ID),
    API_HASH
)


async def main():
    try:
        await client.start()

        me = await client.get_me()

        print("Подключение к Telegram успешно!")
        print(f"ID: {me.id}")
        print(f"Имя: {me.first_name}")

    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
