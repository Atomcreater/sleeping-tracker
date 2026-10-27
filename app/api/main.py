import os
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from app.services.sleep_detector import (
    find_sleep_intervals_from_db,
    merge_sleeping_intervals,
)
from app.db.schema import init_db
from app.db.activity import save_activity_event
from app.db.sleep import save_detected_sleep

load_dotenv()

app = FastAPI()
API_TOKEN = os.getenv("ACTIVITY_API_TOKEN")


class ActivityEvent(BaseModel):
    event_type: str
    event_time: datetime


@app.on_event("startup")
async def startup():
    init_db()


@app.post("/activity")
async def receive_activity(
    event: ActivityEvent,
    authorization: str | None = Header(default=None),
):
    # Проверяем секретный токен перед сохранением события
    if not API_TOKEN or authorization != f"Bearer {API_TOKEN}":
        raise HTTPException(status_code=401, detail="Нет доступа")

    # Пока используем фиксированный ID для собственного аккаунта
    user_id = int(os.getenv("SLEEP_TRACKER_USER_ID"))

    saved = save_activity_event(
        user_id=user_id,
        event_time=event.event_time,
        event_type=event.event_type,
        source="iphone",
    )
    
        # После нового утреннего события проверяем завершённые периоды сна.
    if saved and event.event_type == "online":
        intervals = find_sleep_intervals_from_db(user_id)
        merged_intervals = merge_sleeping_intervals(intervals)

        # Сохраняем обнаруженные периоды сна без создания дубликатов.
        save_detected_sleep(user_id, merged_intervals)

    return {"success": True, "saved": saved}
