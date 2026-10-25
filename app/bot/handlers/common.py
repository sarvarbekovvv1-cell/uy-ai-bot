"""Common bot command handlers (/help, /cancel)."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import get_main_menu_keyboard, get_remove_keyboard
from app.bot.locales import get_text
from app.services.user_service import UserService

common_router = Router(name="common")


@common_router.message(Command("cancel"))
async def handle_cancel_command(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Cancel current FSM workflow and notify user."""
    user_service = UserService()
    user = (
        await user_service.get_by_telegram_id(session, message.from_user.id)
        if message.from_user
        else None
    )
    lang = user.language if user else "uz"

    await state.clear()

    cancel_msg = get_text("cancel_text", lang)

    if user and await user_service.is_registration_complete(user):
        await message.answer(cancel_msg, reply_markup=get_main_menu_keyboard(lang))
    else:
        await message.answer(cancel_msg, reply_markup=get_remove_keyboard())


@common_router.message(Command("help"))
async def handle_help_command(
    message: Message,
    session: AsyncSession,
) -> None:
    """Send localized help message describing UyAI and development status."""
    user_service = UserService()
    user = (
        await user_service.get_by_telegram_id(session, message.from_user.id)
        if message.from_user
        else None
    )
    lang = user.language if user else "uz"

    await message.answer(get_text("help_text", lang))
