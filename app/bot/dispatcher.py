"""Telegram bot dispatcher and router initialization."""

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import (
    common_router,
    menu_router,
    my_properties_router,
    property_submission_router,
    registration_router,
    review_router,
    settings_router,
    start_router,
)
from app.bot.middlewares.db import DatabaseSessionMiddleware


def create_dispatcher() -> Dispatcher:
    """Create and configure aiogram Dispatcher with middleware and registered routers."""
    # Use in-memory storage for FSM workflow transitions
    dp = Dispatcher(storage=MemoryStorage())

    # Attach database session injection middleware
    db_middleware = DatabaseSessionMiddleware()
    dp.message.middleware(db_middleware)
    dp.callback_query.middleware(db_middleware)

    # Detach from previous dispatcher if already attached (permits re-creation in tests)
    routers = [
        common_router,
        start_router,
        review_router,
        registration_router,
        property_submission_router,
        my_properties_router,
        settings_router,
        menu_router,
    ]
    for r in routers:
        r._parent_router = None
        dp.include_router(r)

    return dp
