import os

import psycopg
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """
    Создаёт подключение к PostgreSQL.
    """

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL не найден в переменных окружения"
        )

    return psycopg.connect(database_url)