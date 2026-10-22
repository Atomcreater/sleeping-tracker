
from datetime import datetime
from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from database import save_activity_event


class ActivityMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:

        user = data.get("event_from_user")

        if getattr(event, "text", None) == "/detect":
            return await handler(event, data)

        if user is not None:
            user_id = user.id
            event_time = datetime.now().astimezone()

            save_activity_event(
                user_id,
                event_time,
                "online",
                "bot_interaction",
            )

        return await handler(event, data)
