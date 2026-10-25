"""Telegram bot dispatcher and router initialization."""

from aiogram import Dispatcher

from app.bot.handlers import start_router


def create_dispatcher() -> Dispatcher:
    """Create and configure aiogram Dispatcher with registered routers."""
    dp = Dispatcher()

    # Register foundation routers
    dp.include_router(start_router)

    return dp
