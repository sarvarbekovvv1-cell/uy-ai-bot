"""/start command handler with user lookup and idempotent onboarding routing."""

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import get_language_keyboard, get_main_menu_keyboard
from app.bot.locales import get_text
from app.bot.states import RegistrationStates
from app.services.user_service import UserService

start_router = Router(name="start")


@start_router.message(CommandStart())
async def handle_start_command(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Handle /start command idempotently based on user registration state."""
    if not message.from_user:
        return

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, message.from_user.id)

    # CASE B: Completed registered user
    if user and await user_service.is_registration_complete(user):
        await state.clear()
        lang = user.language
        welcome_text = f"{get_text('welcome_back', lang)}\n\n{get_text('main_menu_title', lang)}"
        await message.answer(
            welcome_text,
            reply_markup=get_main_menu_keyboard(lang),
        )
        return

    # CASE A & C: New user or partially registered user
    # Reset FSM and initiate language selection
    await state.clear()
    await state.set_state(RegistrationStates.choosing_language)

    await message.answer(
        get_text("choose_language", "uz"),
        reply_markup=get_language_keyboard(),
    )
