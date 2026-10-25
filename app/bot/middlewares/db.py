"""Database session injection middleware for aiogram handlers."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.database.session import get_session_factory
from app.logging import get_logger

logger = get_logger(__name__)


class DatabaseSessionMiddleware(BaseMiddleware):
    """Injects an asynchronous database session into event handler arguments."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # If a session was already injected (e.g. in tests), reuse it
        if "session" in data:
            return await handler(event, data)

        session_factory = get_session_factory()
        async with session_factory() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception as exc:
                await session.rollback()
                logger.error("Unhandled error in bot event handler: %s", exc.__class__.__name__)
                raise
