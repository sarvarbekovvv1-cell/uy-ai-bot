"""Settings and language management handlers."""

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import get_language_keyboard, get_main_menu_keyboard, get_settings_keyboard
from app.bot.locales import LOCALES, get_text
from app.services.user_service import UserService

settings_router = Router(name="settings")

SETTINGS_BUTTON_TEXTS = {
    locale_dict.get("btn_settings")
    for locale_dict in LOCALES.values()
    if locale_dict.get("btn_settings")
}


@settings_router.message(F.text.in_(SETTINGS_BUTTON_TEXTS))
async def handle_settings_entry(
    message: Message,
    session: AsyncSession,
) -> None:
    """Display settings menu."""
    user_service = UserService()
    user = (
        await user_service.get_by_telegram_id(session, message.from_user.id)
        if message.from_user
        else None
    )
    lang = user.language if user else "uz"

    await message.answer(
        get_text("settings_title", lang),
        reply_markup=get_settings_keyboard(lang),
    )


@settings_router.callback_query(F.data == "settings:change_lang")
async def handle_change_language_prompt(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Prompt user with language selection options."""
    user_service = UserService()
    user = (
        await user_service.get_by_telegram_id(session, callback.from_user.id)
        if callback.from_user
        else None
    )
    lang = user.language if user else "uz"

    if callback.message and isinstance(callback.message, Message):
        await callback.message.edit_text(
            get_text("choose_language", lang),
            reply_markup=get_language_keyboard(),
        )
    await callback.answer()


@settings_router.callback_query(F.data.startswith("lang:"))
async def handle_settings_language_update(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Update language preference from settings and re-render main navigation."""
    if not callback.data or not callback.from_user:
        return

    new_lang = callback.data.split(":")[1]
    if new_lang not in ("uz", "ru"):
        new_lang = "uz"

    user_service = UserService()
    await user_service.update_language(session, callback.from_user.id, new_lang)

    confirmation = (
        f"{get_text('language_updated', new_lang)}\n\n{get_text('main_menu_title', new_lang)}"
    )

    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(
            confirmation,
            reply_markup=get_main_menu_keyboard(new_lang),
        )
        try:
            await callback.message.delete()
        except Exception:
            pass

    await callback.answer(get_text("language_updated", new_lang))
