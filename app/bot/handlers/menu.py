"""Main menu navigation and placeholder handlers for UyAI."""

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.locales import LOCALES, get_text
from app.services.user_service import UserService

menu_router = Router(name="menu")

# Collect all localized button labels for placeholder buttons
PLACEHOLDER_BUTTON_KEYS = [
    "btn_valuation",
    "btn_map",
    "btn_ai_broker",
    "btn_appointments",
    "btn_contact_broker",
]

PLACEHOLDER_TEXTS: set[str] = set()
for locale_dict in LOCALES.values():
    for key in PLACEHOLDER_BUTTON_KEYS:
        if key in locale_dict:
            PLACEHOLDER_TEXTS.add(locale_dict[key])


@menu_router.message(F.text.in_(PLACEHOLDER_TEXTS))
async def handle_placeholder_menu_buttons(
    message: Message,
    session: AsyncSession,
) -> None:
    """Respond to menu placeholder buttons confirming future phase implementation."""
    user_service = UserService()
    user = (
        await user_service.get_by_telegram_id(session, message.from_user.id)
        if message.from_user
        else None
    )
    lang = user.language if user else "uz"

    await message.answer(get_text("feature_in_development", lang))
