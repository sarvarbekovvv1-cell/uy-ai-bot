"""Handlers for viewing owner's submitted properties."""

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import get_main_menu_keyboard
from app.bot.locales import LOCALES, get_text
from app.services.property_service import PropertyService
from app.services.user_service import UserService

my_properties_router = Router(name="my_properties")

MY_PROPERTIES_BUTTONS = {
    locale_dict.get("btn_my_properties")
    for locale_dict in LOCALES.values()
    if locale_dict.get("btn_my_properties")
}


@my_properties_router.message(F.text.in_(MY_PROPERTIES_BUTTONS))
async def handle_my_properties_list(
    message: Message,
    session: AsyncSession,
) -> None:
    """List all properties created by current authenticated user."""
    if not message.from_user:
        return

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, message.from_user.id)
    if not user:
        return

    lang = user.language
    prop_service = PropertyService()
    properties = await prop_service.list_owner_properties(session, owner_user_id=user.id)

    if not properties:
        await message.answer(
            get_text("my_properties_empty", lang),
            reply_markup=get_main_menu_keyboard(lang),
        )
        return

    lines = [get_text("my_properties_title", lang), ""]
    for p in properties:
        date_str = p.created_at.strftime("%Y-%m-%d") if p.created_at else ""
        lines.append(
            f"🆔 #{p.id} | {p.property_type.capitalize()} ({p.listing_type.upper()})\n"
            f"📍 {p.region}, {p.district}\n"
            f"💰 {p.price:,.0f} {p.currency} | Status: <b>{p.status.upper()}</b>\n"
            f"📅 {date_str}\n"
            f"{'—'*20}"
        )

    await message.answer("\n".join(lines), reply_markup=get_main_menu_keyboard(lang))
