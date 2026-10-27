from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌙 Начать сон",
                    callback_data="sleep"
                ),
                InlineKeyboardButton(
                    text="☀️ Проснулся",
                    callback_data="wake"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📅 История",
                    callback_data="history"
                ),
                InlineKeyboardButton(
                    text="📊 Статистика",
                    callback_data="stats"
                ),
            ],
            
            [
                InlineKeyboardButton(
                    text="🔍 Анализ сна",
                    callback_data="detect"
                ),
                InlineKeyboardButton(
                    text="⚙️ Настройки",
                    callback_data="settings"
                )
            ]
        ]
    )
