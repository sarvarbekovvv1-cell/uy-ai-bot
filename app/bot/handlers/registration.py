"""User onboarding and multi-step registration handlers."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import (
    get_consent_keyboard,
    get_main_menu_keyboard,
    get_phone_keyboard,
)
from app.bot.locales import get_text
from app.bot.states import RegistrationStates
from app.logging import get_logger
from app.services.user_service import UserService

logger = get_logger(__name__)

registration_router = Router(name="registration")


@registration_router.callback_query(
    F.data.startswith("lang:"), RegistrationStates.choosing_language
)
async def handle_language_choice(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Handle language selection button during onboarding."""
    if not callback.data or not callback.from_user:
        return

    lang = callback.data.split(":")[1]
    if lang not in ("uz", "ru"):
        lang = "uz"

    await state.update_data(language=lang)

    user_service = UserService()
    await user_service.initialize_user(
        session,
        telegram_id=callback.from_user.id,
        language=lang,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
    )

    await state.set_state(RegistrationStates.waiting_consent)

    if callback.message and isinstance(callback.message, Message):
        await callback.message.edit_text(
            get_text("consent_text", lang),
            reply_markup=get_consent_keyboard(lang),
        )
    await callback.answer()


@registration_router.callback_query(
    F.data == "consent:accept", RegistrationStates.waiting_consent
)
async def handle_consent_accept(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Handle user accepting privacy and terms consent."""
    data = await state.get_data()
    lang = data.get("language", "uz")

    await state.set_state(RegistrationStates.waiting_name)

    suggested_name = callback.from_user.first_name if callback.from_user else ""
    prompt_text = get_text("ask_name", lang)
    if suggested_name:
        prompt_text += f" ({suggested_name})"

    if callback.message and isinstance(callback.message, Message):
        await callback.message.edit_text(prompt_text)
    await callback.answer()


@registration_router.callback_query(
    F.data == "consent:decline", RegistrationStates.waiting_consent
)
async def handle_consent_decline(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Handle user declining privacy terms and cancel registration."""
    data = await state.get_data()
    lang = data.get("language", "uz")

    await state.clear()

    if callback.message and isinstance(callback.message, Message):
        await callback.message.edit_text(get_text("consent_declined", lang))
    await callback.answer()


@registration_router.message(F.text, RegistrationStates.waiting_name)
async def handle_name_input(
    message: Message,
    state: FSMContext,
) -> None:
    """Validate and store candidate name, then request contact phone number."""
    data = await state.get_data()
    lang = data.get("language", "uz")

    name = (message.text or "").strip()
    # Support normal Unicode names (Uzbek, Russian, etc.) with 2..50 character length
    if len(name) < 2 or len(name) > 50:
        await message.answer(get_text("invalid_name", lang))
        return

    await state.update_data(name=name)
    await state.set_state(RegistrationStates.waiting_phone)

    await message.answer(
        get_text("ask_phone", lang),
        reply_markup=get_phone_keyboard(lang),
    )


@registration_router.message(F.contact, RegistrationStates.waiting_phone)
async def handle_contact_phone(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Verify shared Telegram Contact ownership and complete user registration."""
    if not message.contact or not message.from_user:
        return

    data = await state.get_data()
    lang = data.get("language", "uz")
    name = data.get("name") or message.from_user.first_name

    # SECURITY CHECK: Verify contact belongs to the user who sent it
    if message.contact.user_id != message.from_user.id:
        logger.warning(
            "Rejected contact spoof attempt: contact.user_id=%s != sender.id=%d",
            str(message.contact.user_id),
            message.from_user.id,
        )
        await message.answer(get_text("invalid_contact_owner", lang))
        return

    raw_phone = message.contact.phone_number
    user_service = UserService()

    try:
        await user_service.complete_registration(
            session,
            telegram_id=message.from_user.id,
            phone=raw_phone,
            is_verified=True,
            first_name=name,
            language=lang,
        )
    except Exception:
        logger.error("Failed completing registration for telegram_id=%d", message.from_user.id)
        await message.answer(get_text("generic_error", lang))
        return

    await state.clear()

    # Send confirmation and render main customer navigation menu
    completion_text = (
        f"{get_text('registration_complete', lang)}\n\n{get_text('main_menu_title', lang)}"
    )
    await message.answer(completion_text, reply_markup=get_main_menu_keyboard(lang))


@registration_router.message(F.text, RegistrationStates.waiting_phone)
async def handle_manual_phone(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Process fallback manual phone number entry with verification marked False."""
    if not message.from_user or not message.text:
        return

    data = await state.get_data()
    lang = data.get("language", "uz")
    name = data.get("name") or message.from_user.first_name

    user_service = UserService()
    try:
        await user_service.complete_registration(
            session,
            telegram_id=message.from_user.id,
            phone=message.text,
            is_verified=False,  # Manual entry is unverified by Telegram contact protocol
            first_name=name,
            language=lang,
        )
    except Exception:
        await message.answer(
            get_text("invalid_phone_format", lang),
            reply_markup=get_phone_keyboard(lang),
        )
        return

    await state.clear()

    completion_text = (
        f"{get_text('registration_complete', lang)}\n\n{get_text('main_menu_title', lang)}"
    )
    await message.answer(completion_text, reply_markup=get_main_menu_keyboard(lang))
