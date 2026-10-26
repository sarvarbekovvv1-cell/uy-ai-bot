"""Telegram handlers for saved favorite properties."""

import os
from typing import Any

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, FSInputFile, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import (
    get_main_menu_keyboard,
    get_property_card_keyboard,
    get_property_details_keyboard,
)
from app.bot.locales import LOCALES, get_text
from app.config import get_settings
from app.core.exceptions import PropertyNotFoundError
from app.logging import get_logger
from app.models.property import Property
from app.services.favorite_service import FavoriteService
from app.services.property_search_service import PropertySearchService
from app.services.user_service import UserService

logger = get_logger(__name__)

favorites_router = Router(name="favorites")

FAVORITES_BUTTONS = {
    locale_dict.get("btn_favorites")
    for locale_dict in LOCALES.values()
    if locale_dict.get("btn_favorites")
}


def get_media_cache_dir() -> str:
    """Return absolute path to configured media storage directory."""
    settings = get_settings()
    if os.path.isabs(settings.media_storage_dir):
        return settings.media_storage_dir
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    return os.path.abspath(os.path.join(base_dir, settings.media_storage_dir))


def resolve_property_photo(photo_item: Any) -> Any:
    """Resolve photo item into either Telegram file_id or local FSInputFile."""
    if not photo_item:
        return None
    file_id = getattr(photo_item, "telegram_file_id", None)
    if file_id and file_id.startswith("admin_file_"):
        uid = getattr(photo_item, "telegram_file_unique_id", None)
        if uid:
            storage_dir = get_media_cache_dir()
            for ext in (".jpg", ".png", ".webp"):
                candidate = os.path.join(storage_dir, f"{uid}{ext}")
                if os.path.exists(candidate):
                    return FSInputFile(candidate)
    return file_id


def format_card_caption(prop: Property, _lang: str = "uz") -> str:
    """Format short summary card for a property."""
    prop_type = prop.property_type.capitalize()
    return (
        f"🏠 {prop_type} ({prop.listing_type.upper()})\n"
        f"📍 {prop.region}, {prop.district}\n"
        f"🚪 {prop.rooms} xona | 📐 {prop.total_area} m²\n"
        f"🏢 {prop.floor}/{prop.total_floors} qavat\n"
        f"💰 {prop.price:,.0f} {prop.currency}\n"
        f"🛠 {prop.condition.capitalize()}\n"
        f"🆔 #{prop.id}"
    )


def format_detailed_view(prop: Property, lang: str = "uz") -> str:
    """Format comprehensive public property details without exposing owner PII."""
    prop_type = prop.property_type.capitalize()
    lines = [
        get_text("detail_title", lang).format(id=prop.id),
        "",
        f"🏷 Turi / Тип: {prop_type} ({prop.listing_type.upper()})",
        f"📍 Hudud / Регион: {prop.region}, {prop.district}",
        f"🚪 Xonalar soni / Комнаты: {prop.rooms}",
        f"📐 Umumiy maydon / Площадь: {prop.total_area} m²",
    ]
    if prop.living_area:
        lines.append(f"🛋 Yashash maydoni / Жилая площадь: {prop.living_area} m²")
    if prop.floor and prop.total_floors:
        lines.append(f"🏢 Qavat / Этаж: {prop.floor}/{prop.total_floors}")
    lines.append(f"🛠 Ta’mir / Ремонт: {prop.condition}")
    lines.append(f"🛋 Mebel: {'Bor / Есть' if prop.has_furniture else 'Yo‘q / Нет'}")
    lines.append(f"📄 Kadastr: {prop.cadastre_status}")
    lines.append(f"💰 Narxi / Цена: {prop.price:,.0f} {prop.currency}")
    if prop.negotiable:
        lines.append("🤝 Savdolashish / Торг: Bor / Есть")
    if prop.description:
        lines.append(f"\n📝 Qo‘shimcha ma'lumot:\n{prop.description}")

    return "\n".join(lines)


@favorites_router.message(F.text.in_(FAVORITES_BUTTONS))
async def handle_list_favorites(
    message: Message,
    session: AsyncSession,
) -> None:
    """Display user's saved approved properties."""
    if not message.from_user:
        return

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, message.from_user.id)
    if not user:
        return

    lang = user.language
    fav_service = FavoriteService()
    properties = await fav_service.list_saved_properties(session, user_id=user.id)

    if not properties:
        await message.answer(
            get_text("saved_properties_empty", lang),
            reply_markup=get_main_menu_keyboard(lang),
        )
        return

    await message.answer(get_text("saved_properties_title", lang))

    for p in properties:
        caption = format_card_caption(p, lang)
        card_kb = get_property_card_keyboard(p.id, is_fav=True, lang=lang)

        if p.media and len(p.media) > 0 and message.bot:
            try:
                first_photo = p.media[0]
                photo_payload = resolve_property_photo(first_photo)
                if photo_payload:
                    await message.answer_photo(
                        photo=photo_payload,
                        caption=caption,
                        reply_markup=card_kb,
                    )
                    continue
            except Exception:
                logger.warning(
                    "Failed to send property photo, falling back to text for id=%s",
                    p.id,
                )

        await message.answer(caption, reply_markup=card_kb)


@favorites_router.callback_query(F.data.startswith("search_prop:fav:"))
async def handle_add_favorite_callback(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Add property to favorites."""
    if not callback.data or not callback.from_user:
        return

    property_id = int(callback.data.split(":")[2])
    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        return

    lang = user.language
    fav_service = FavoriteService()

    try:
        await fav_service.add_favorite(session, user_id=user.id, property_id=property_id)
        try:
            await callback.answer(get_text("fav_added_alert", lang))
        except TelegramBadRequest:
            pass

        if callback.message and isinstance(callback.message, Message):
            is_details = False
            existing_markup = getattr(callback.message, "reply_markup", None)
            if existing_markup and hasattr(existing_markup, "inline_keyboard"):
                for row in existing_markup.inline_keyboard:
                    for btn in row:
                        cb_data = getattr(btn, "callback_data", None)
                        if cb_data and "viewing:create" in cb_data:
                            is_details = True
                            break
            new_kb = (
                get_property_details_keyboard(property_id, is_fav=True, lang=lang)
                if is_details
                else get_property_card_keyboard(property_id, is_fav=True, lang=lang)
            )
            await callback.message.edit_reply_markup(reply_markup=new_kb)
    except PropertyNotFoundError:
        try:
            await callback.answer(get_text("property_not_found", lang), show_alert=True)
        except TelegramBadRequest:
            pass


@favorites_router.callback_query(F.data.startswith("search_prop:unfav:"))
async def handle_remove_favorite_callback(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Remove property from favorites."""
    if not callback.data or not callback.from_user:
        return

    property_id = int(callback.data.split(":")[2])
    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        return

    lang = user.language
    fav_service = FavoriteService()

    await fav_service.remove_favorite(session, user_id=user.id, property_id=property_id)
    try:
        await callback.answer(get_text("fav_removed_alert", lang))
    except TelegramBadRequest:
        pass

    if callback.message and isinstance(callback.message, Message):
        is_details = False
        existing_markup = getattr(callback.message, "reply_markup", None)
        if existing_markup and hasattr(existing_markup, "inline_keyboard"):
            for row in existing_markup.inline_keyboard:
                for btn in row:
                    cb_data = getattr(btn, "callback_data", None)
                    if cb_data and "viewing:create" in cb_data:
                        is_details = True
                        break
        new_kb = (
            get_property_details_keyboard(property_id, is_fav=False, lang=lang)
            if is_details
            else get_property_card_keyboard(property_id, is_fav=False, lang=lang)
        )
        await callback.message.edit_reply_markup(reply_markup=new_kb)


@favorites_router.callback_query(F.data.startswith("search_prop:view:"))
async def handle_view_property_details(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Display public details for an approved property."""
    if not callback.data or not callback.from_user:
        return

    property_id = int(callback.data.split(":")[2])
    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    lang = user.language if user else "uz"

    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

    search_service = PropertySearchService()
    fav_service = FavoriteService()

    try:
        prop = await search_service.get_approved_details(session, property_id)
    except PropertyNotFoundError:
        if callback.message and isinstance(callback.message, Message):
            await callback.message.answer(get_text("property_not_found", lang))
        return

    is_fav = False
    if user:
        is_fav = await fav_service.is_favorite(session, user_id=user.id, property_id=property_id)
    details_text = format_detailed_view(prop, lang)
    detail_kb = get_property_details_keyboard(prop.id, is_fav=is_fav, lang=lang)

    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(details_text, reply_markup=detail_kb)
