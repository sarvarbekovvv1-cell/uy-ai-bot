"""Telegram bot handlers aggregation."""

from app.bot.handlers.common import common_router
from app.bot.handlers.menu import menu_router
from app.bot.handlers.registration import registration_router
from app.bot.handlers.settings import settings_router
from app.bot.handlers.start import start_router

__all__ = [
    "common_router",
    "start_router",
    "registration_router",
    "menu_router",
    "settings_router",
]
