"""Property submission wizard handlers for sale and rental listings."""

import re
from decimal import Decimal

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import (
    get_cadastre_keyboard,
    get_condition_keyboard,
    get_currency_keyboard,
    get_furniture_keyboard,
    get_location_keyboard,
    get_main_menu_keyboard,
    get_negotiable_keyboard,
    get_photos_keyboard,
    get_property_type_keyboard,
    get_remove_keyboard,
    get_submission_confirm_keyboard,
)
from app.bot.locales import LOCALES, get_text
from app.bot.states import PropertySubmissionStates
from app.core.exceptions import IncompletePropertyError
from app.logging import get_logger
from app.services.property_service import PropertyService
from app.services.user_service import UserService

logger = get_logger(__name__)

property_submission_router = Router(name="property_submission")

# Buttons triggering listing workflows
SELL_BUTTONS = {
    locale_dict.get("btn_sell")
    for locale_dict in LOCALES.values()
    if locale_dict.get("btn_sell")
}
RENT_BUTTONS = {
    locale_dict.get("btn_lease")
    for locale_dict in LOCALES.values()
    if locale_dict.get("btn_lease")
}


@property_submission_router.message(F.text.in_(SELL_BUTTONS | RENT_BUTTONS))
async def handle_start_submission(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Entry point for property listing wizard (sale or rent)."""
    if not message.from_user:
        return

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, message.from_user.id)
    if not user or not await user_service.is_registration_complete(user):
        await message.answer(get_text("consent_declined", "uz"))
        return

    lang = user.language
    listing_type = "sale" if message.text in SELL_BUTTONS else "rent"

    await state.clear()
    await state.update_data(listing_type=listing_type, user_id=user.id, language=lang)
    await state.set_state(PropertySubmissionStates.waiting_property_type)

    prompt = (
        get_text("explain_sell_process", lang)
        if listing_type == "sale"
        else get_text("explain_rent_process", lang)
    )
    await message.answer(prompt, reply_markup=get_property_type_keyboard(lang))


@property_submission_router.callback_query(
    F.data.startswith("proptype:"), PropertySubmissionStates.waiting_property_type
)
async def handle_property_type(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Process property type choice."""
    if not callback.data:
        return

    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

    prop_type = callback.data.split(":")[1]
    await state.update_data(property_type=prop_type)
    await state.set_state(PropertySubmissionStates.waiting_region)

    data = await state.get_data()
    lang = data.get("language", "uz")

    if callback.message and isinstance(callback.message, Message):
        await callback.message.edit_text(get_text("ask_region", lang))


@property_submission_router.message(F.text, PropertySubmissionStates.waiting_region)
async def handle_region(message: Message, state: FSMContext) -> None:
    """Store region and ask for district."""
    data = await state.get_data()
    lang = data.get("language", "uz")

    region = (message.text or "").strip()
    if len(region) < 2:
        await message.answer(get_text("ask_region", lang))
        return

    await state.update_data(region=region)
    await state.set_state(PropertySubmissionStates.waiting_district)
    await message.answer(get_text("ask_district", lang))


@property_submission_router.message(F.text, PropertySubmissionStates.waiting_district)
async def handle_district(message: Message, state: FSMContext) -> None:
    """Store district and ask for street/address."""
    data = await state.get_data()
    lang = data.get("language", "uz")

    district = (message.text or "").strip()
    if len(district) < 2:
        await message.answer(get_text("ask_district", lang))
        return

    await state.update_data(district=district)
    await state.set_state(PropertySubmissionStates.waiting_address)
    await message.answer(get_text("ask_address", lang))


@property_submission_router.message(F.text, PropertySubmissionStates.waiting_address)
async def handle_address(message: Message, state: FSMContext) -> None:
    """Store address and prompt for optional location coordinates."""
    data = await state.get_data()
    lang = data.get("language", "uz")

    address = (message.text or "").strip()
    if len(address) < 2:
        await message.answer(get_text("ask_address", lang))
        return

    await state.update_data(address=address)
    await state.set_state(PropertySubmissionStates.waiting_location)
    await message.answer(
        get_text("ask_location", lang),
        reply_markup=get_location_keyboard(lang),
    )


@property_submission_router.message(PropertySubmissionStates.waiting_location)
async def handle_location(message: Message, state: FSMContext) -> None:
    """Process location coordinates or skip action."""
    data = await state.get_data()
    lang = data.get("language", "uz")

    if message.location:
        await state.update_data(
            latitude=Decimal(str(round(message.location.latitude, 7))),
            longitude=Decimal(str(round(message.location.longitude, 7))),
        )
    else:
        await state.update_data(latitude=None, longitude=None)

    await state.set_state(PropertySubmissionStates.waiting_rooms)
    await message.answer(get_text("ask_rooms", lang), reply_markup=get_remove_keyboard())


@property_submission_router.message(F.text, PropertySubmissionStates.waiting_rooms)
async def handle_rooms(message: Message, state: FSMContext) -> None:
    """Validate and store rooms count."""
    data = await state.get_data()
    lang = data.get("language", "uz")

    text = (message.text or "").strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer(get_text("invalid_rooms", lang))
        return

    await state.update_data(rooms=int(text))
    await state.set_state(PropertySubmissionStates.waiting_total_area)
    await message.answer(get_text("ask_total_area", lang))


@property_submission_router.message(F.text, PropertySubmissionStates.waiting_total_area)
async def handle_total_area(message: Message, state: FSMContext) -> None:
    """Validate and store total area in square meters."""
    data = await state.get_data()
    lang = data.get("language", "uz")

    raw = (message.text or "").replace(",", ".").strip()
    try:
        area = Decimal(raw)
        if area <= 0:
            raise ValueError
    except Exception:
        await message.answer(get_text("invalid_area", lang))
        return

    await state.update_data(total_area=float(area))
    await state.set_state(PropertySubmissionStates.waiting_floor)
    await message.answer(get_text("ask_floor", lang))


@property_submission_router.message(F.text, PropertySubmissionStates.waiting_floor)
async def handle_floor(message: Message, state: FSMContext) -> None:
    """Validate and store floor."""
    data = await state.get_data()
    lang = data.get("language", "uz")

    raw = (message.text or "").strip()
    if not raw.isdigit() or int(raw) < 0:
        await message.answer(get_text("invalid_floor", lang))
        return

    await state.update_data(floor=int(raw))
    await state.set_state(PropertySubmissionStates.waiting_total_floors)
    await message.answer(get_text("ask_total_floors", lang))


@property_submission_router.message(F.text, PropertySubmissionStates.waiting_total_floors)
async def handle_total_floors(message: Message, state: FSMContext) -> None:
    """Validate and store total floors."""
    data = await state.get_data()
    lang = data.get("language", "uz")
    floor = data.get("floor", 0)

    raw = (message.text or "").strip()
    if not raw.isdigit() or int(raw) <= 0 or (floor and int(raw) < floor):
        await message.answer(get_text("invalid_total_floors", lang))
        return

    await state.update_data(total_floors=int(raw))
    await state.set_state(PropertySubmissionStates.waiting_condition)
    await message.answer(
        get_text("ask_condition", lang),
        reply_markup=get_condition_keyboard(lang),
    )


@property_submission_router.callback_query(
    F.data.startswith("propcond:"), PropertySubmissionStates.waiting_condition
)
async def handle_condition(callback: CallbackQuery, state: FSMContext) -> None:
    """Store condition and prompt for furniture."""
    if not callback.data:
        return
    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

    cond = callback.data.split(":")[1]
    await state.update_data(condition=cond)
    await state.set_state(PropertySubmissionStates.waiting_furniture)

    data = await state.get_data()
    lang = data.get("language", "uz")

    if callback.message and isinstance(callback.message, Message):
        await callback.message.edit_text(
            get_text("ask_furniture", lang),
            reply_markup=get_furniture_keyboard(lang),
        )


@property_submission_router.callback_query(
    F.data.startswith("propfurn:"), PropertySubmissionStates.waiting_furniture
)
async def handle_furniture(callback: CallbackQuery, state: FSMContext) -> None:
    """Store furniture boolean and prompt for cadastre status."""
    if not callback.data:
        return
    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

    has_furn = callback.data.split(":")[1] == "yes"
    await state.update_data(has_furniture=has_furn)
    await state.set_state(PropertySubmissionStates.waiting_cadastre)

    data = await state.get_data()
    lang = data.get("language", "uz")

    if callback.message and isinstance(callback.message, Message):
        await callback.message.edit_text(
            get_text("ask_cadastre", lang),
            reply_markup=get_cadastre_keyboard(lang),
        )


@property_submission_router.callback_query(
    F.data.startswith("propcad:"), PropertySubmissionStates.waiting_cadastre
)
async def handle_cadastre(callback: CallbackQuery, state: FSMContext) -> None:
    """Store cadastre status and prompt for price."""
    if not callback.data:
        return
    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

    cad = callback.data.split(":")[1]
    await state.update_data(cadastre_status=cad)
    await state.set_state(PropertySubmissionStates.waiting_price)

    data = await state.get_data()
    lang = data.get("language", "uz")

    if callback.message and isinstance(callback.message, Message):
        await callback.message.edit_text(get_text("ask_price", lang))


@property_submission_router.message(F.text, PropertySubmissionStates.waiting_price)
async def handle_price(message: Message, state: FSMContext) -> None:
    """Validate price and prompt for currency."""
    data = await state.get_data()
    lang = data.get("language", "uz")

    raw = re.sub(r"[\s,]", "", message.text or "").strip()
    try:
        price = Decimal(raw)
        if price <= 0:
            raise ValueError
    except Exception:
        await message.answer(get_text("invalid_price", lang))
        return

    await state.update_data(price=float(price))
    await state.set_state(PropertySubmissionStates.waiting_currency)
    await message.answer(
        get_text("ask_currency", lang),
        reply_markup=get_currency_keyboard(),
    )


@property_submission_router.callback_query(
    F.data.startswith("propcurr:"), PropertySubmissionStates.waiting_currency
)
async def handle_currency(callback: CallbackQuery, state: FSMContext) -> None:
    """Store currency and prompt for negotiable option."""
    if not callback.data:
        return
    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

    curr = callback.data.split(":")[1]
    await state.update_data(currency=curr)
    await state.set_state(PropertySubmissionStates.waiting_negotiable)

    data = await state.get_data()
    lang = data.get("language", "uz")

    if callback.message and isinstance(callback.message, Message):
        await callback.message.edit_text(
            get_text("ask_negotiable", lang),
            reply_markup=get_negotiable_keyboard(lang),
        )


@property_submission_router.callback_query(
    F.data.startswith("propneg:"), PropertySubmissionStates.waiting_negotiable
)
async def handle_negotiable(callback: CallbackQuery, state: FSMContext) -> None:
    """Store negotiable flag and prompt for description."""
    if not callback.data:
        return
    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

    neg = callback.data.split(":")[1] == "yes"
    await state.update_data(negotiable=neg)
    await state.set_state(PropertySubmissionStates.waiting_description)

    data = await state.get_data()
    lang = data.get("language", "uz")

    if callback.message and isinstance(callback.message, Message):
        await callback.message.edit_text(get_text("ask_description", lang))


@property_submission_router.message(F.text, PropertySubmissionStates.waiting_description)
async def handle_description(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Persist initial draft property and prompt for photos."""
    data = await state.get_data()
    lang = data.get("language", "uz")
    user_id = data.get("user_id")

    desc = (message.text or "").strip()
    if desc.lower() in ("yo'q", "yoq", "нет", "no", "-"):
        desc = None

    await state.update_data(description=desc)

    # Persist draft to database
    prop_service = PropertyService()
    lat = Decimal(str(data["latitude"])) if data.get("latitude") is not None else None
    lon = Decimal(str(data["longitude"])) if data.get("longitude") is not None else None

    draft = await prop_service.create_draft(
        session,
        owner_user_id=user_id,
        listing_type=data["listing_type"],
        property_type=data["property_type"],
        region=data["region"],
        district=data["district"],
        address=data["address"],
        rooms=data["rooms"],
        total_area=Decimal(str(data["total_area"])),
        condition=data["condition"],
        price=Decimal(str(data["price"])),
        currency=data["currency"],
        negotiable=data["negotiable"],
        floor=data.get("floor"),
        total_floors=data.get("total_floors"),
        latitude=lat,
        longitude=lon,
        has_furniture=data.get("has_furniture", False),
        cadastre_status=data.get("cadastre_status", "unknown"),
        description=desc,
    )

    await state.update_data(property_id=draft.id, photo_count=0)
    await state.set_state(PropertySubmissionStates.waiting_photos)

    await message.answer(
        get_text("ask_photos", lang),
        reply_markup=get_photos_keyboard(lang),
    )


@property_submission_router.message(F.photo, PropertySubmissionStates.waiting_photos)
async def handle_photo_upload(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Handle incoming photos for draft property."""
    if not message.photo or not message.from_user:
        return

    data = await state.get_data()
    lang = data.get("language", "uz")
    property_id = data.get("property_id")
    user_id = data.get("user_id")

    photo = message.photo[-1]
    prop_service = PropertyService()

    try:
        await prop_service.add_photo(
            session,
            property_id=property_id,
            owner_user_id=user_id,
            telegram_file_id=photo.file_id,
            telegram_file_unique_id=photo.file_unique_id,
        )
    except IncompletePropertyError:
        await message.answer(get_text("photo_max_reached", lang))
        return

    current_count = await prop_service.media_repo.count_by_property(session, property_id)
    await state.update_data(photo_count=current_count)

    await message.answer(
        get_text("photo_received", lang).format(count=current_count),
        reply_markup=get_photos_keyboard(lang),
    )


@property_submission_router.message(
    F.text.in_({"✅ Rasmlar tayyor", "✅ Фотографии готовы"}),
    PropertySubmissionStates.waiting_photos,
)
async def handle_photos_ready(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Verify photo count and present preview confirmation summary."""
    data = await state.get_data()
    lang = data.get("language", "uz")
    property_id = data.get("property_id")

    prop_service = PropertyService()
    photo_count = await prop_service.media_repo.count_by_property(session, property_id)
    if photo_count < 1:
        await message.answer(get_text("photo_min_error", lang))
        return

    summary = (
        f"{get_text('preview_title', lang)}\n\n"
        f"🏷 Turi / Тип: {data.get('property_type')}\n"
        f"📌 Yo‘nalish / Направление: {data.get('listing_type')}\n"
        f"📍 Manzil / Адрес: {data.get('region')}, {data.get('district')}, {data.get('address')}\n"
        f"🚪 Xonalar / Комнаты: {data.get('rooms')}\n"
        f"📐 Maydon / Площадь: {data.get('total_area')} m²\n"
        f"🏢 Qavat / Этаж: {data.get('floor')}/{data.get('total_floors')}\n"
        f"🛠 Ta’mir / Ремонт: {data.get('condition')}\n"
        f"🛋 Mebel / Мебель: {'Ha/Да' if data.get('has_furniture') else 'Yo‘q/Нет'}\n"
        f"📄 Kadastr / Кадастр: {data.get('cadastre_status')}\n"
        f"💰 Narxi / Цена: {data.get('price'):,.0f} {data.get('currency')}\n"
        f"🤝 Savdolashish / Торг: {'Ha/Да' if data.get('negotiable') else 'Yo‘q/Нет'}\n"
        f"📸 Rasmlar soni / Всего фото: {photo_count} ta"
    )

    await state.set_state(PropertySubmissionStates.waiting_confirmation)
    await message.answer(summary, reply_markup=get_submission_confirm_keyboard(lang))


@property_submission_router.callback_query(
    F.data == "propsubmit:confirm", PropertySubmissionStates.waiting_confirmation
)
async def handle_submit_confirmed(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Submit property to 'submitted' status and complete wizard."""
    data = await state.get_data()
    lang = data.get("language", "uz")
    property_id = data.get("property_id")
    user_id = data.get("user_id")

    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

    prop_service = PropertyService()
    await prop_service.submit_listing(session, property_id=property_id, owner_user_id=user_id)

    await state.clear()

    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(
            get_text("submission_success", lang),
            reply_markup=get_main_menu_keyboard(lang),
        )


@property_submission_router.callback_query(
    F.data == "propsubmit:cancel", PropertySubmissionStates.waiting_confirmation
)
async def handle_submit_canceled(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Cancel submission, leaving draft unsubmitted."""
    data = await state.get_data()
    lang = data.get("language", "uz")

    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

    await state.clear()

    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(
            get_text("cancel_text", lang),
            reply_markup=get_main_menu_keyboard(lang),
        )
