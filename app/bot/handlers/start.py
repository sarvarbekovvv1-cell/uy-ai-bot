"""Foundation Telegram bot handlers."""

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

start_router = Router(name="start")

START_MESSAGE = "🏢 UyAI tizimiga xush kelibsiz!\n\nTizim hozir ishlab chiqilmoqda."


@start_router.message(CommandStart())
async def handle_start_command(message: Message) -> None:
    """Handle /start command with foundation greeting."""
    await message.answer(START_MESSAGE)
