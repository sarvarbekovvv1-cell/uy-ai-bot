"""Telegram handlers for property discovery and search."""

import re
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.favorites import format_card_caption
from app.bot.keyboards import (
    MAIN_MENU_BUTTONS,
    get_main_menu_keyboard,
    get_property_card_keyboard,
    get_remove_keyboard,
    get_search_currency_keyboard,
    get_search_pagination_keyboard,
    get_search_property_type_keyboard,
    get_search_restart_keyboard,
    get_search_rooms_keyboard,
    get_search_skip_keyboard,
)
from app.bot.locales import LOCALES, get_text
from app.bot.states import PropertySearchStates
from app.logging import get_logger
from app.models.property import PROPERTY_TYPES
from app.schemas.property_search import PropertySearchFilters
from app.services.favorite_service import FavoriteService
from app.services.property_search_service import PropertySearchService
from app.services.user_service import UserService

logger = get_logger(__name__)

search_router = Router(name="property_search")

BUY_BUTTONS = {
    locale_dict.get("btn_buy") for locale_dict in LOCALES.values() if locale_dict.get("btn_buy")
} | {"🏠 Uy sotib olish", "🏠 Купить недвижимость"}

RENT_BUTTONS = {
    locale_dict.get("btn_rent") for locale_dict in LOCALES.values() if locale_dict.get("btn_rent")
} | {"🔑 Uy ijaraga olish", "🔑 Арендовать недвижимость", "🔑 Снять недвижимость"}

SKIP_BUTTONS = {
    locale_dict.get("btn_skip") for locale_dict in LOCALES.values() if locale_dict.get("btn_skip")
}

CANCEL_BUTTONS = {
    locale_dict.get("btn_cancel_submit")
    for locale_dict in LOCALES.values()
    if locale_dict.get("btn_cancel_submit")
}


def is_cancel(text: str | None) -> bool:
    """Check if message text is a cancel action."""
    return text in CANCEL_BUTTONS or text == "/cancel"


def is_skip(text: str | None) -> bool:
    """Check if message text is a skip action."""
    if not text:
        return False
    normalized = text.strip().lower()
    return (
        text in SKIP_BUTTONS
        or "o'tkazib yuborish" in normalized
        or "o‘tkazib yuborish" in normalized
        or "пропустить" in normalized
        or "skip" in normalized
    )


async def cancel_search(message: Message, state: FSMContext, lang: str) -> None:
    """Clear state and present cancel notification with main menu."""
    await state.clear()
    await message.answer(
        get_text("cancel_text", lang),
        reply_markup=get_main_menu_keyboard(lang),
    )


async def render_search_page(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    page: int = 1,
) -> None:
    """Render a page of search results."""
    data = await state.get_data()
    lang = data.get("language", "uz")
    user_id = data.get("user_id")

    filters_dict = {
        "listing_type": data.get("listing_type", "sale"),
        "property_type": data.get("property_type"),
        "region": data.get("region"),
        "district": data.get("district"),
        "rooms": data.get("rooms"),
        "min_rooms": data.get("min_rooms"),
        "min_price": data.get("min_price"),
        "max_price": data.get("max_price"),
        "currency": data.get("currency"),
        "min_area": data.get("min_area"),
    }

    try:
        filters = PropertySearchFilters(**filters_dict)
    except Exception as e:
        logger.error("Invalid search filters in state: %s", e)
        await message.answer(
            get_text("generic_error", lang),
            reply_markup=get_main_menu_keyboard(lang),
        )
        return

    search_service = PropertySearchService()
    fav_service = FavoriteService()

    properties, total_count, total_pages = await search_service.search(
        session, filters=filters, page=page, page_size=5
    )

    if total_count == 0:
        await message.answer(
            get_text("search_no_results", lang),
            reply_markup=get_search_restart_keyboard(lang),
        )
        return

    await message.answer(
        get_text("search_results_found", lang).format(
            total=total_count, page=page, total_pages=total_pages
        )
    )

    for p in properties:
        is_fav = False
        if user_id:
            is_fav = await fav_service.is_favorite(session, user_id=user_id, property_id=p.id)
        caption = format_card_caption(p, lang)
        card_kb = get_property_card_keyboard(p.id, is_fav=is_fav, lang=lang)

        if p.media and len(p.media) > 0 and message.bot:
            try:
                first_photo = p.media[0]
                await message.answer_photo(
                    photo=first_photo.telegram_file_id,
                    caption=caption,
                    reply_markup=card_kb,
                )
                continue
            except Exception:
                logger.warning(
                    "Failed to render property photo, falling back to text for id=%s",
                    p.id,
                )

        await message.answer(caption, reply_markup=card_kb)

    # Send pagination controls
    pagination_kb = get_search_pagination_keyboard(page, total_pages, lang)
    await message.answer(f"📄 {page}/{total_pages}", reply_markup=pagination_kb)


# --- Entry Points ---


@search_router.message(F.text.in_(BUY_BUTTONS))
async def handle_start_buy_search(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Start search wizard for buying properties (listing_type='sale')."""
    await _start_search(message, state, session, listing_type="sale")


@search_router.message(F.text.in_(RENT_BUTTONS))
async def handle_start_rent_search(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Start search wizard for renting properties (listing_type='rent')."""
    await _start_search(message, state, session, listing_type="rent")


async def _start_search(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    listing_type: str,
    user_tg_id: int | None = None,
) -> None:
    """Initialize search flow for customer."""
    tg_id = user_tg_id or (message.from_user.id if message.from_user else None)
    if not tg_id:
        return

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, tg_id)
    if not user or not await user_service.is_registration_complete(user):
        await message.answer("Iltimos, avval ro‘yxatdan o‘tishni yakunlang: /start")
        return

    lang = user.language
    await state.clear()
    await state.set_state(PropertySearchStates.choosing_property_type)
    await state.update_data(listing_type=listing_type, language=lang, user_id=user.id)

    prompt = get_text("search_start_sale" if listing_type == "sale" else "search_start_rent", lang)
    await message.answer(prompt, reply_markup=get_search_property_type_keyboard(lang))


# --- FSM Steps ---


@search_router.message(PropertySearchStates.choosing_property_type, ~F.text.in_(MAIN_MENU_BUTTONS))
async def handle_property_type(
    message: Message,
    state: FSMContext,
) -> None:
    """Process property type selection."""
    data = await state.get_data()
    lang = data.get("language", "uz")

    if is_cancel(message.text):
        await cancel_search(message, state, lang)
        return

    text = (message.text or "").strip().lower()
    selected_type: str | None = None

    if "kvartira" in text or "квартира" in text:
        selected_type = "apartment"
    elif "hovli" in text or "дом" in text or "uy" in text:
        selected_type = "house"
    elif "tijorat" in text or "коммерческ" in text:
        selected_type = "commercial"
    elif "yer" in text or "участ" in text or "земл" in text:
        selected_type = "land"
    elif "barcha" in text or "все" in text or "barchasi" in text:
        selected_type = None
    elif text in PROPERTY_TYPES:
        selected_type = text

    await state.update_data(property_type=selected_type)
    await state.set_state(PropertySearchStates.waiting_region)
    await message.answer(get_text("search_ask_region", lang), reply_markup=get_remove_keyboard())


@search_router.message(PropertySearchStates.waiting_region, ~F.text.in_(MAIN_MENU_BUTTONS))
async def handle_region(
    message: Message,
    state: FSMContext,
) -> None:
    """Process region selection."""
    data = await state.get_data()
    lang = data.get("language", "uz")

    if is_cancel(message.text):
        await cancel_search(message, state, lang)
        return

    region = (message.text or "").strip()
    if not region or len(region) < 2:
        await message.answer(get_text("search_ask_region", lang))
        return

    await state.update_data(region=region)
    await state.set_state(PropertySearchStates.waiting_district)
    await message.answer(
        get_text("search_ask_district", lang),
        reply_markup=get_search_skip_keyboard(lang),
    )


@search_router.message(PropertySearchStates.waiting_district, ~F.text.in_(MAIN_MENU_BUTTONS))
async def handle_district(
    message: Message,
    state: FSMContext,
) -> None:
    """Process district selection or skip."""
    data = await state.get_data()
    lang = data.get("language", "uz")

    if is_cancel(message.text):
        await cancel_search(message, state, lang)
        return

    district = None if is_skip(message.text) else (message.text or "").strip()
    await state.update_data(district=district)

    await state.set_state(PropertySearchStates.choosing_rooms)
    await message.answer(
        get_text("search_ask_rooms", lang),
        reply_markup=get_search_rooms_keyboard(lang),
    )


@search_router.message(PropertySearchStates.choosing_rooms, ~F.text.in_(MAIN_MENU_BUTTONS))
async def handle_rooms(
    message: Message,
    state: FSMContext,
) -> None:
    """Process rooms filter."""
    data = await state.get_data()
    lang = data.get("language", "uz")

    if is_cancel(message.text):
        await cancel_search(message, state, lang)
        return

    text = (message.text or "").strip()
    rooms: int | None = None
    min_rooms: int | None = None

    if text in {"1", "2", "3", "4"}:
        rooms = int(text)
    elif text == "5+":
        min_rooms = 5
    elif text.isdigit():
        val = int(text)
        if val >= 5:
            min_rooms = 5
        elif val >= 1:
            rooms = val

    await state.update_data(rooms=rooms, min_rooms=min_rooms)
    await state.set_state(PropertySearchStates.waiting_min_price)
    await message.answer(
        get_text("search_ask_min_price", lang),
        reply_markup=get_search_skip_keyboard(lang),
    )


@search_router.message(PropertySearchStates.waiting_min_price, ~F.text.in_(MAIN_MENU_BUTTONS))
async def handle_min_price(
    message: Message,
    state: FSMContext,
) -> None:
    """Process minimum price filter."""
    data = await state.get_data()
    lang = data.get("language", "uz")

    if is_cancel(message.text):
        await cancel_search(message, state, lang)
        return

    min_price: Decimal | None = None
    if not is_skip(message.text):
        raw = re.sub(r"[^\d.]", "", message.text or "")
        try:
            min_price = Decimal(raw)
            if min_price < 0:
                await message.answer(get_text("price_invalid_number", lang))
                return
        except InvalidOperation:
            await message.answer(get_text("price_invalid_number", lang))
            return

    await state.update_data(min_price=min_price)
    await state.set_state(PropertySearchStates.waiting_max_price)
    await message.answer(
        get_text("search_ask_max_price", lang),
        reply_markup=get_search_skip_keyboard(lang),
    )


@search_router.message(PropertySearchStates.waiting_max_price, ~F.text.in_(MAIN_MENU_BUTTONS))
async def handle_max_price(
    message: Message,
    state: FSMContext,
) -> None:
    """Process maximum price filter and advance to currency or min area."""
    data = await state.get_data()
    lang = data.get("language", "uz")

    if is_cancel(message.text):
        await cancel_search(message, state, lang)
        return

    max_price: Decimal | None = None
    if not is_skip(message.text):
        raw = re.sub(r"[^\d.]", "", message.text or "")
        try:
            max_price = Decimal(raw)
            if max_price <= 0:
                await message.answer(get_text("price_invalid_number", lang))
                return
        except InvalidOperation:
            await message.answer(get_text("price_invalid_number", lang))
            return

    min_price = data.get("min_price")
    if min_price is not None and max_price is not None and min_price > max_price:
        await message.answer(get_text("price_range_error", lang))
        return

    await state.update_data(max_price=max_price)

    # If any price filter was specified, currency is required
    if min_price is not None or max_price is not None:
        await state.set_state(PropertySearchStates.choosing_currency)
        await message.answer(
            get_text("search_ask_currency", lang),
            reply_markup=get_search_currency_keyboard(lang),
        )
    else:
        await state.set_state(PropertySearchStates.waiting_min_area)
        await message.answer(
            get_text("search_ask_min_area", lang),
            reply_markup=get_search_skip_keyboard(lang),
        )


@search_router.message(PropertySearchStates.choosing_currency, ~F.text.in_(MAIN_MENU_BUTTONS))
async def handle_currency(
    message: Message,
    state: FSMContext,
) -> None:
    """Process currency selection."""
    data = await state.get_data()
    lang = data.get("language", "uz")

    if is_cancel(message.text):
        await cancel_search(message, state, lang)
        return

    text = (message.text or "").strip().upper()
    currency = "USD"
    if "UZS" in text:
        currency = "UZS"

    await state.update_data(currency=currency)
    await state.set_state(PropertySearchStates.waiting_min_area)
    await message.answer(
        get_text("search_ask_min_area", lang),
        reply_markup=get_search_skip_keyboard(lang),
    )


@search_router.message(PropertySearchStates.waiting_min_area, ~F.text.in_(MAIN_MENU_BUTTONS))
async def handle_min_area(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Process min area filter and execute search."""
    data = await state.get_data()
    lang = data.get("language", "uz")

    if is_cancel(message.text):
        await cancel_search(message, state, lang)
        return

    min_area: Decimal | None = None
    if not is_skip(message.text):
        raw = re.sub(r"[^\d.]", "", message.text or "")
        try:
            min_area = Decimal(raw)
            if min_area <= 0:
                await message.answer(get_text("area_invalid_number", lang))
                return
        except InvalidOperation:
            await message.answer(get_text("area_invalid_number", lang))
            return

    await state.update_data(min_area=min_area)
    await state.set_state(PropertySearchStates.showing_results)

    await message.answer(get_text("search_searching", lang), reply_markup=get_remove_keyboard())
    await render_search_page(message, state, session, page=1)


# --- Pagination and Navigation ---


@search_router.callback_query(F.data.startswith("search_page:"))
async def handle_search_page_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Paginate search results."""
    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

    if not callback.data or not callback.message or not isinstance(callback.message, Message):
        return

    page = int(callback.data.split(":")[1])
    await render_search_page(callback.message, state, session, page=page)


@search_router.callback_query(F.data == "search_nav:restart")
async def handle_search_restart_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Restart search flow."""
    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

    if not callback.message or not isinstance(callback.message, Message):
        return

    data = await state.get_data()
    listing_type = data.get("listing_type", "sale")
    user_tg_id = callback.from_user.id if callback.from_user else None
    await _start_search(
        callback.message,
        state,
        session,
        listing_type=listing_type,
        user_tg_id=user_tg_id,
    )


@search_router.callback_query(F.data == "search_nav:noop")
async def handle_search_noop_callback(callback: CallbackQuery) -> None:
    """Acknowledge noop callback."""
    try:
        await callback.answer()
    except TelegramBadRequest:
        pass
