"""Telegram bot dispatcher and router initialization."""

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import (
    ai_broker_router,
    appointments_router,
    broker_cabinet_router,
    broker_requests_router,
    common_router,
    favorites_router,
    menu_router,
    my_properties_router,
    property_submission_router,
    registration_router,
    review_router,
    search_router,
    settings_router,
    start_router,
)
from app.bot.middlewares.db import DatabaseSessionMiddleware
from app.bot.middlewares.escape import MenuEscapeMiddleware


def create_dispatcher() -> Dispatcher:
    """Create and configure aiogram Dispatcher with middleware and registered routers."""
    # Use in-memory storage for FSM workflow transitions
    dp = Dispatcher(storage=MemoryStorage())

    # Attach middlewares
    db_middleware = DatabaseSessionMiddleware()
    dp.message.middleware(db_middleware)
    dp.callback_query.middleware(db_middleware)

    # Attach menu escape middleware so main menu buttons immediately clear AI broker state
    dp.message.middleware(MenuEscapeMiddleware())

    # Detach from previous dispatcher if already attached (permits re-creation in tests)
    routers = [
        common_router,
        start_router,
        review_router,
        broker_requests_router,
        broker_cabinet_router,
        registration_router,
        property_submission_router,
        search_router,
        favorites_router,
        appointments_router,
        my_properties_router,
        settings_router,
        ai_broker_router,
        menu_router,
    ]
    for r in routers:
        r._parent_router = None
        dp.include_router(r)

    return dp
