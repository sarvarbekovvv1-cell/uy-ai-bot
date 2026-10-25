"""Telegram bot standard command list configurations."""

from aiogram.types import BotCommand

BOT_COMMANDS_UZ = [
    BotCommand(command="start", description="Tizimni ishga tushirish"),
    BotCommand(command="help", description="Yordam va ma’lumot"),
    BotCommand(command="cancel", description="Joriy jarayonni bekor qilish"),
    BotCommand(command="review_properties", description="E'lonlarni tekshirish (xodimlar uchun)"),
]

BOT_COMMANDS_RU = [
    BotCommand(command="start", description="Запустить систему"),
    BotCommand(command="help", description="Справка и информация"),
    BotCommand(command="cancel", description="Отменить текущий процесс"),
    BotCommand(command="review_properties", description="Проверка объявлений (для персонала)"),
]


def get_default_bot_commands() -> list[BotCommand]:
    """Return default bot command list."""
    return BOT_COMMANDS_UZ
