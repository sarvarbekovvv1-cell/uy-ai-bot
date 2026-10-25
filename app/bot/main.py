"""Telegram bot runner entrypoint."""

import asyncio
import sys

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.bot.dispatcher import create_dispatcher
from app.config import get_settings
from app.logging import get_logger, setup_logging

logger = get_logger(__name__)


def create_bot(token: str | None = None) -> Bot:
    """Create a configured Bot instance without starting network activity."""
    if token is None:
        settings = get_settings()
        token = settings.bot_token

    if not token or token.strip() == "":
        raise ValueError(
            "BOT_TOKEN is not configured. Please set BOT_TOKEN in your environment or .env file."
        )

    return Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


async def start_bot() -> None:
    """Start bot polling session."""
    settings = get_settings()
    setup_logging(settings.log_level)

    try:
        bot = create_bot()
    except ValueError as e:
        logger.error("Failed to initialize bot: %s", e)
        sys.exit(1)

    dispatcher = create_dispatcher()

    logger.info("Starting Telegram bot polling for %s...", settings.app_name)
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("Telegram bot polling stopped.")


if __name__ == "__main__":
    asyncio.run(start_bot())
