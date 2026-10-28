"""Telegram bot handlers for AI property market valuation."""

import re
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import (
    get_main_menu_keyboard,
    get_valuation_actions_keyboard,
    get_valuation_condition_keyboard,
    get_valuation_currency_keyboard,
    get_valuation_districts_keyboard,
    get_valuation_floor_keyboard,
    get_valuation_listing_type_keyboard,
    get_valuation_payment_keyboard,
    get_valuation_property_type_keyboard,
    get_valuation_rooms_keyboard,
)
from app.bot.locales import LOCALES, format_condition, get_text
from app.bot.states import PropertySubmissionStates, PropertyValuationStates
from app.config import get_settings
from app.logging import get_logger
from app.repositories.valuation_order_repository import ValuationOrderRepository
from app.schemas.valuation import PropertyValuationInput, PropertyValuationResult
from app.services.payment import ValuationPaymentService
from app.services.user_service import UserService
from app.services.valuation import ValuationService

logger = get_logger(__name__)

valuation_router = Router(name="valuation")

VALUATION_BUTTONS = {
    locale_dict.get("btn_valuation")
    for locale_dict in LOCALES.values()
    if locale_dict.get("btn_valuation")
} | {
    "📊 Uyimni baholash",
    "📊 Uyimni AI orqali baholash",
    "📊 Оценка недвижимости",
}

DISTRICT_NORMALIZE = {
    "chilonzor": "Chilonzor",
    "чиланзар": "Chilonzor",
    "yunusobod": "Yunusobod",
    "юнусабад": "Yunusobod",
    "mirzo ulug'bek": "Mirzo Ulug‘bek",
    "mirzo ulugbek": "Mirzo Ulug‘bek",
    "мирзо улугбек": "Mirzo Ulug‘bek",
    "мирзо-улугбек": "Mirzo Ulug‘bek",
    "yakkasaroy": "Yakkasaroy",
    "яккасарай": "Yakkasaroy",
    "mirobod": "Mirobod",
    "миробад": "Mirobod",
    "shayxontohur": "Shayxontohur",
    "шайхантахур": "Shayxontohur",
    "olmazor": "Olmazor",
    "алмазар": "Olmazor",
    "uchtepa": "Uchtepa",
    "учтепа": "Uchtepa",
    "yashnobod": "Yashnobod",
    "яшнабад": "Yashnobod",
    "sergeli": "Sergeli",
    "сергели": "Sergeli",
    "bektemir": "Bektemir",
    "бектемир": "Bektemir",
    "yangihayot": "Yangihayot",
    "янгихаёт": "Yangihayot",
}


def normalize_district(name: str) -> str:
    """Normalize district name from Uzbek/Russian variants to standard string."""
    cleaned = name.strip().lower()
    return DISTRICT_NORMALIZE.get(cleaned, name.strip().title())


def get_valuation_service() -> ValuationService:
    """Create valuation service instance with configured GenAI provider if available."""
    settings = get_settings()
    llm_provider = None
    if settings.gemini_api_key:
        try:
            from app.ai.gemini_provider import GeminiLLMProvider

            llm_provider = GeminiLLMProvider(settings=settings)
        except Exception as e:
            logger.warning("Could not initialize GeminiLLMProvider: %s", e)

    return ValuationService(llm_provider=llm_provider)


@valuation_router.message(F.text.in_(VALUATION_BUTTONS) | F.text.in_({"/valuation", "/baholash"}))
async def handle_start_valuation(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Entry point for property market valuation wizard."""
    if not message.from_user:
        return

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, message.from_user.id)
    if not user or not await user_service.is_registration_complete(user):
        await message.answer(get_text("consent_declined", "uz"))
        return

    lang = user.language
    await state.clear()
    await state.update_data(user_id=user.id, language=lang, region="Toshkent shahri")
    await state.set_state(PropertyValuationStates.waiting_listing_type)

    await message.answer(
        get_text("val_welcome", lang),
        reply_markup=get_valuation_listing_type_keyboard(lang),
    )


@valuation_router.callback_query(
    PropertyValuationStates.waiting_listing_type, F.data.startswith("val_lt:")
)
async def handle_valuation_listing_type(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Select transaction listing type (sale or rent)."""
    await callback.answer()
    if not callback.data:
        return

    listing_type = callback.data.split(":", 1)[1]
    data = await state.get_data()
    lang = data.get("language", "uz")

    await state.update_data(listing_type=listing_type)
    await state.set_state(PropertyValuationStates.waiting_property_type)

    if callback.message and isinstance(callback.message, Message):
        try:
            await callback.message.edit_text(
                get_text("val_choose_property_type", lang),
                reply_markup=get_valuation_property_type_keyboard(lang),
            )
        except TelegramBadRequest:
            await callback.message.answer(
                get_text("val_choose_property_type", lang),
                reply_markup=get_valuation_property_type_keyboard(lang),
            )


@valuation_router.callback_query(
    PropertyValuationStates.waiting_property_type, F.data.startswith("val_pt:")
)
async def handle_valuation_property_type(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Select property type, rejecting unsupported commercial/land types."""
    await callback.answer()
    if not callback.data:
        return

    property_type = callback.data.split(":", 1)[1]
    data = await state.get_data()
    lang = data.get("language", "uz")

    if property_type in ("commercial", "land"):
        await state.clear()
        if callback.message and isinstance(callback.message, Message):
            await callback.message.answer(
                get_text("val_unsupported_type", lang),
                reply_markup=get_main_menu_keyboard(lang),
            )
        return

    await state.update_data(property_type=property_type)
    await state.set_state(PropertyValuationStates.waiting_district)

    if callback.message and isinstance(callback.message, Message):
        try:
            await callback.message.edit_text(
                get_text("val_choose_district", lang),
                reply_markup=get_valuation_districts_keyboard(lang),
            )
        except TelegramBadRequest:
            await callback.message.answer(
                get_text("val_choose_district", lang),
                reply_markup=get_valuation_districts_keyboard(lang),
            )


@valuation_router.callback_query(
    PropertyValuationStates.waiting_district, F.data.startswith("val_dst:")
)
async def handle_valuation_district_callback(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Handle district selection via inline button."""
    await callback.answer()
    if not callback.data:
        return

    district = callback.data.split(":", 1)[1]
    await process_district_selection(district, state, callback.message)


@valuation_router.message(PropertyValuationStates.waiting_district, F.text)
async def handle_valuation_district_text(
    message: Message,
    state: FSMContext,
) -> None:
    """Handle district selection via text input."""
    if not message.text:
        return
    await process_district_selection(message.text, state, message)


async def process_district_selection(
    district_raw: str,
    state: FSMContext,
    target_message: Message | None,
) -> None:
    """Normalize district and advance to room count selection."""
    district = normalize_district(district_raw)
    data = await state.get_data()
    lang = data.get("language", "uz")

    await state.update_data(district=district)
    await state.set_state(PropertyValuationStates.waiting_rooms)

    if target_message:
        text = get_text("val_choose_rooms", lang)
        markup = get_valuation_rooms_keyboard()
        try:
            await target_message.edit_text(text, reply_markup=markup)
        except (TelegramBadRequest, AttributeError):
            await target_message.answer(text, reply_markup=markup)


@valuation_router.callback_query(
    PropertyValuationStates.waiting_rooms, F.data.startswith("val_rooms:")
)
async def handle_valuation_rooms_callback(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Handle room count selection via inline buttons."""
    await callback.answer()
    if not callback.data:
        return

    rooms_str = callback.data.split(":", 1)[1]
    rooms = int(rooms_str)
    await process_rooms_selection(rooms, state, callback.message)


@valuation_router.message(PropertyValuationStates.waiting_rooms, F.text)
async def handle_valuation_rooms_text(
    message: Message,
    state: FSMContext,
) -> None:
    """Handle room count selection via text input."""
    if not message.text:
        return

    try:
        rooms = int(message.text.strip())
        if not (1 <= rooms <= 50):
            raise ValueError()
    except ValueError:
        data = await state.get_data()
        lang = data.get("language", "uz")
        await message.answer(
            get_text("val_choose_rooms", lang), reply_markup=get_valuation_rooms_keyboard()
        )
        return

    await process_rooms_selection(rooms, state, message)


async def process_rooms_selection(
    rooms: int,
    state: FSMContext,
    target_message: Message | None,
) -> None:
    """Save rooms and advance to total area input."""
    data = await state.get_data()
    lang = data.get("language", "uz")

    await state.update_data(rooms=rooms)
    await state.set_state(PropertyValuationStates.waiting_area)

    if target_message:
        text = get_text("val_ask_area", lang)
        try:
            await target_message.edit_text(text)
        except (TelegramBadRequest, AttributeError):
            await target_message.answer(text)


@valuation_router.message(PropertyValuationStates.waiting_area, F.text)
async def handle_valuation_area(
    message: Message,
    state: FSMContext,
) -> None:
    """Handle total area input with positive Decimal validation."""
    if not message.text:
        return

    data = await state.get_data()
    lang = data.get("language", "uz")

    cleaned_text = message.text.replace(",", ".").strip()
    try:
        area = Decimal(cleaned_text)
        if area <= Decimal("0") or area > Decimal("10000"):
            raise InvalidOperation()
    except InvalidOperation:
        await message.answer(get_text("val_invalid_area", lang))
        return

    await state.update_data(total_area=str(area))
    await state.set_state(PropertyValuationStates.waiting_condition)

    await message.answer(
        get_text("val_choose_condition", lang),
        reply_markup=get_valuation_condition_keyboard(lang),
    )


@valuation_router.callback_query(
    PropertyValuationStates.waiting_condition, F.data.startswith("val_cond:")
)
async def handle_valuation_condition(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Handle condition selection."""
    await callback.answer()
    if not callback.data:
        return

    condition = callback.data.split(":", 1)[1]
    data = await state.get_data()
    lang = data.get("language", "uz")
    property_type = data.get("property_type", "apartment")

    await state.update_data(condition=condition)

    if property_type == "apartment":
        await state.set_state(PropertyValuationStates.waiting_floor)
        if callback.message and isinstance(callback.message, Message):
            try:
                await callback.message.edit_text(
                    get_text("val_ask_floor", lang),
                    reply_markup=get_valuation_floor_keyboard(lang),
                )
            except TelegramBadRequest:
                await callback.message.answer(
                    get_text("val_ask_floor", lang),
                    reply_markup=get_valuation_floor_keyboard(lang),
                )
    else:
        # Houses skip floor step
        await state.set_state(PropertyValuationStates.waiting_currency)
        if callback.message and isinstance(callback.message, Message):
            try:
                await callback.message.edit_text(
                    get_text("val_choose_currency", lang),
                    reply_markup=get_valuation_currency_keyboard(),
                )
            except TelegramBadRequest:
                await callback.message.answer(
                    get_text("val_choose_currency", lang),
                    reply_markup=get_valuation_currency_keyboard(),
                )


@valuation_router.callback_query(PropertyValuationStates.waiting_floor, F.data == "val_floor:skip")
async def handle_valuation_floor_skip(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Handle skipping floor input."""
    await callback.answer()
    data = await state.get_data()
    lang = data.get("language", "uz")

    await state.update_data(floor=None, total_floors=None)
    await state.set_state(PropertyValuationStates.waiting_currency)

    if callback.message and isinstance(callback.message, Message):
        try:
            await callback.message.edit_text(
                get_text("val_choose_currency", lang),
                reply_markup=get_valuation_currency_keyboard(),
            )
        except TelegramBadRequest:
            await callback.message.answer(
                get_text("val_choose_currency", lang),
                reply_markup=get_valuation_currency_keyboard(),
            )


@valuation_router.message(PropertyValuationStates.waiting_floor, F.text)
async def handle_valuation_floor_text(
    message: Message,
    state: FSMContext,
) -> None:
    """Handle floor and total_floors text input (e.g. '4/9' or '3')."""
    if not message.text:
        return

    data = await state.get_data()
    lang = data.get("language", "uz")

    match = re.match(r"^(\d{1,2})\s*/\s*(\d{1,2})$", message.text.strip())
    floor: int | None = None
    total_floors: int | None = None

    if match:
        f_val, tf_val = int(match.group(1)), int(match.group(2))
        if f_val > tf_val or f_val < 1:
            await message.answer(
                get_text("val_ask_floor", lang),
                reply_markup=get_valuation_floor_keyboard(lang),
            )
            return
        floor = f_val
        total_floors = tf_val
    else:
        try:
            f_val = int(message.text.strip())
            if not (1 <= f_val <= 100):
                raise ValueError()
            floor = f_val
        except ValueError:
            await message.answer(
                get_text("val_ask_floor", lang),
                reply_markup=get_valuation_floor_keyboard(lang),
            )
            return

    await state.update_data(floor=floor, total_floors=total_floors)
    await state.set_state(PropertyValuationStates.waiting_currency)

    await message.answer(
        get_text("val_choose_currency", lang),
        reply_markup=get_valuation_currency_keyboard(),
    )


def format_valuation_input_summary(inp: PropertyValuationInput, lang: str = "uz") -> str:
    """Format submitted property parameters for customer review and payment confirmation."""
    prop_type_label = "Kvartira" if inp.property_type == "apartment" else "Hovli / Uy"
    if lang == "ru":
        prop_type_label = "Квартира" if inp.property_type == "apartment" else "Дом / Участок"
    listing_label = "Sotuv" if inp.listing_type == "sale" else "Ijara"
    if lang == "ru":
        listing_label = "Продажа" if inp.listing_type == "sale" else "Аренда"

    cond_label = format_condition(inp.condition, lang) if inp.condition else "-"
    floor_label = (
        f"{inp.floor}/{inp.total_floors}"
        if inp.floor and inp.total_floors
        else (f"{inp.floor}" if inp.floor else "-")
    )

    if lang == "ru":
        return (
            f"{get_text('val_order_summary_title', lang)}\n\n"
            f"• <b>Тип:</b> {prop_type_label} ({listing_label})\n"
            f"• <b>Локация:</b> {inp.region}, {inp.district}\n"
            f"• <b>Комнат:</b> {inp.rooms}\n"
            f"• <b>Площадь:</b> {inp.total_area} м²\n"
            f"• <b>Ремонт:</b> {cond_label}\n"
            f"• <b>Этаж:</b> {floor_label}\n"
        )
    return (
        f"{get_text('val_order_summary_title', lang)}\n\n"
        f"• <b>Turi:</b> {prop_type_label} ({listing_label})\n"
        f"• <b>Hudud:</b> {inp.region}, {inp.district}\n"
        f"• <b>Xonalar:</b> {inp.rooms}\n"
        f"• <b>Maydoni:</b> {inp.total_area} m²\n"
        f"• <b>Ta'miri:</b> {cond_label}\n"
        f"• <b>Qavati:</b> {floor_label}\n"
    )


@valuation_router.callback_query(
    PropertyValuationStates.waiting_currency, F.data.startswith("val_curr:")
)
async def handle_valuation_currency(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    valuation_service: ValuationService | None = None,
    val_pay_svc: ValuationPaymentService | None = None,
) -> None:
    """Finalize input, enforce monetization check, and create payment order."""
    await callback.answer()
    if not callback.data or not callback.from_user:
        return

    currency = callback.data.split(":", 1)[1]
    data = await state.get_data()
    lang = data.get("language", "uz")

    await state.update_data(currency=currency)

    # Construct validated input
    val_input = PropertyValuationInput(
        listing_type=data.get("listing_type", "sale"),
        property_type=data.get("property_type", "apartment"),
        region=data.get("region", "Toshkent shahri"),
        district=data.get("district", "Chilonzor"),
        total_area=Decimal(data.get("total_area", "50")),
        rooms=int(data.get("rooms", 2)),
        condition=data.get("condition"),
        floor=data.get("floor"),
        total_floors=data.get("total_floors"),
        currency=currency,  # type: ignore[arg-type]
    )

    # In production (valuation_service is None), always enforce monetization
    if val_pay_svc is None and valuation_service is None:
        val_pay_svc = ValuationPaymentService()

    if val_pay_svc is not None:
        # Monetization check: If price is not set or payment providers are not configured
        if not val_pay_svc.is_service_ready():
            notice_text = get_text("val_payment_service_unconfigured", lang)
            markup = get_main_menu_keyboard(lang)
            await state.clear()
            if callback.message and isinstance(callback.message, Message):
                await callback.message.answer(notice_text, reply_markup=markup)
            return

        # User lookup
        user_service = UserService()
        user = await user_service.get_by_telegram_id(session, callback.from_user.id)
        if not user:
            await callback.answer("Foydalanuvchi topilmadi.", show_alert=True)
            return

        # Create ValuationOrder
        order = await val_pay_svc.create_valuation_order(
            session,
            user_id=user.id,
            telegram_id=callback.from_user.id,
            property_input=val_input,
        )
        await session.commit()

        # Save order details in FSM state
        await state.update_data(
            order_id=order.order_id,
            val_input=val_input.model_dump(mode="json"),
        )
        await state.set_state(PropertyValuationStates.waiting_payment)

        # Format summary and payment prompt
        summary_text = format_valuation_input_summary(val_input, lang)
        price_fmt = f"{int(order.amount_uzs):,}".replace(",", " ")
        price_notice = get_text("val_price_notice", lang).replace("{price}", price_fmt)
        prompt_text = (
            f"{summary_text}\n"
            f"🆔 <b>Buyurtma ID:</b> <code>{order.order_id}</code>\n\n"
            f"{price_notice}"
        )

        links = val_pay_svc.get_payment_links(order)
        markup = get_valuation_payment_keyboard(
            order_id=order.order_id,
            click_url=links.get("click"),
            payme_url=links.get("payme"),
            lang=lang,
        )

        if callback.message and isinstance(callback.message, Message):
            try:
                await callback.message.edit_text(prompt_text, reply_markup=markup)
            except TelegramBadRequest:
                await callback.message.answer(prompt_text, reply_markup=markup)
        return

    # Direct calculation path (for explicit test mock injection)
    result: PropertyValuationResult = await valuation_service.valuate_property(
        session,
        val_input,
        language=lang,
    )
    card_text = format_valuation_result_card(val_input, result, lang)
    comps_data = [comp.model_dump() for comp in result.comparable_properties]
    await state.update_data(
        last_result=result.model_dump(mode="json"),
        comps_data=comps_data,
        subject_listing_type=val_input.listing_type,
    )
    await state.set_state(PropertyValuationStates.viewing_result)

    markup = get_valuation_actions_keyboard(
        has_comps=bool(result.comparable_properties),
        listing_type=val_input.listing_type,
        lang=lang,
    )

    if callback.message and isinstance(callback.message, Message):
        try:
            await callback.message.edit_text(card_text, reply_markup=markup)
        except TelegramBadRequest:
            await callback.message.answer(card_text, reply_markup=markup)


@valuation_router.callback_query(F.data.startswith("val_check_pay:"))
async def handle_check_valuation_payment(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    val_pay_svc: ValuationPaymentService | None = None,
) -> None:
    """Verify server-side payment status and show valuation card if paid."""
    if not callback.data or not callback.from_user:
        return

    order_id = callback.data.split(":", 1)[1]
    order_repo = ValuationOrderRepository()
    order = await order_repo.get_by_order_id(session, order_id)

    data = await state.get_data()
    lang = data.get("language", "uz")

    if not order:
        await callback.answer("Buyurtma topilmadi.", show_alert=True)
        return

    # Security check: User must own the order
    if order.telegram_id != callback.from_user.id:
        await callback.answer("Ruxsatsiz amal!", show_alert=True)
        return

    if order.payment_status != "paid":
        pending_msg = get_text("val_payment_pending", lang).replace("{order_id}", order_id)
        await callback.answer("To‘lov hali tasdiqlanmadi.", show_alert=True)
        if callback.message and isinstance(callback.message, Message):
            try:
                if val_pay_svc is None:
                    val_pay_svc = ValuationPaymentService()
                links = val_pay_svc.get_payment_links(order)
                markup = get_valuation_payment_keyboard(
                    order_id=order.order_id,
                    click_url=links.get("click"),
                    payme_url=links.get("payme"),
                    lang=lang,
                )
                await callback.message.edit_text(pending_msg, reply_markup=markup)
            except TelegramBadRequest:
                pass
        return

    # Payment verified! If valuation not completed yet, fulfill now
    await callback.answer("To‘lov tasdiqlandi!")
    if val_pay_svc is None:
        val_pay_svc = ValuationPaymentService()

    result = await val_pay_svc.fulfill_order_and_valuate(session, order_id)
    if not result:
        if callback.message and isinstance(callback.message, Message):
            await callback.message.answer(
                "Baholashda texnik xatolik yuz berdi. Iltimos, qayta urinib ko‘ring."
            )
        return

    val_input = PropertyValuationInput.model_validate(order.property_input)
    card_text = format_valuation_result_card(val_input, result, lang)

    # Save comps in state for detailed viewing
    comps_data = [comp.model_dump() for comp in result.comparable_properties]
    await state.update_data(
        last_result=result.model_dump(mode="json"),
        comps_data=comps_data,
        subject_listing_type=val_input.listing_type,
    )
    await state.set_state(PropertyValuationStates.viewing_result)

    markup = get_valuation_actions_keyboard(
        has_comps=bool(result.comparable_properties),
        listing_type=val_input.listing_type,
        lang=lang,
    )
    if callback.message and isinstance(callback.message, Message):
        try:
            await callback.message.edit_text(card_text, reply_markup=markup)
        except TelegramBadRequest:
            await callback.message.answer(card_text, reply_markup=markup)


@valuation_router.callback_query(F.data.startswith("val_cancel_pay:"))
async def handle_cancel_valuation_payment(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Cancel pending valuation payment and return to main menu."""
    await callback.answer()
    if not callback.data:
        return

    order_id = callback.data.split(":", 1)[1]
    order_repo = ValuationOrderRepository()
    order = await order_repo.get_by_order_id(session, order_id)
    if order and order.payment_status == "pending":
        order.payment_status = "cancelled"
        await session.commit()

    data = await state.get_data()
    lang = data.get("language", "uz")
    await state.clear()

    cancel_msg = get_text("val_payment_cancelled", lang)
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(cancel_msg, reply_markup=get_main_menu_keyboard(lang))


@valuation_router.callback_query(
    F.data.startswith("val_pay_click:") | F.data.startswith("val_pay_payme:")
)
async def handle_unconfigured_provider_click(callback: CallbackQuery) -> None:
    """Notice when provider is selected but credentials are not yet configured."""
    await callback.answer(
        "To‘lov provayderi sozlanish jarayonida. Iltimos, administrator bilan bog‘laning.",
        show_alert=True,
    )


def format_valuation_result_card(
    inp: PropertyValuationInput,
    res: PropertyValuationResult,
    lang: str = "uz",
) -> str:
    """Format safe, explainable property valuation result card."""
    if res.insufficient_data:
        return get_text("val_insufficient_data", lang)

    title = get_text("val_card_title", lang)
    prop_type_label = "Kvartira" if inp.property_type == "apartment" else "Hovli / Uy"
    if lang == "ru":
        prop_type_label = "Квартира" if inp.property_type == "apartment" else "Дом / Участок"

    currency = res.currency
    est_fmt = f"{int(res.estimated_price):,}".replace(",", " ") if res.estimated_price else "N/A"
    min_fmt = (
        f"{int(res.estimated_min_price):,}".replace(",", " ") if res.estimated_min_price else "N/A"
    )
    max_fmt = (
        f"{int(res.estimated_max_price):,}".replace(",", " ") if res.estimated_max_price else "N/A"
    )

    if currency == "USD":
        range_str = f"${min_fmt} – ${max_fmt}"
        central_str = f"${est_fmt}"
        m2_str = f"${res.median_price_per_m2}" if res.median_price_per_m2 else "N/A"
    else:
        range_str = f"{min_fmt} – {max_fmt} {currency}"
        central_str = f"{est_fmt} {currency}"
        m2_str = f"{res.median_price_per_m2} {currency}" if res.median_price_per_m2 else "N/A"

    conf_map = {
        "uz": {"low": "Past", "medium": "O‘rta", "high": "Yuqori"},
        "ru": {"low": "Низкий", "medium": "Средний", "high": "Высокий"},
        "en": {"low": "Low", "medium": "Medium", "high": "High"},
    }
    conf_label = conf_map.get(lang, conf_map["uz"]).get(res.confidence, res.confidence)
    cond_label = format_condition(inp.condition, lang)

    explanation_text = ""
    if res.explanation and res.explanation.summary:
        explanation_text = f"\n\n🤖 <b>AI tahlil va izoh:</b>\n{res.explanation.summary}"
        if lang == "ru":
            explanation_text = f"\n\n🤖 <b>Анализ и пояснение AI:</b>\n{res.explanation.summary}"

    if lang == "ru":
        return (
            f"{title}\n\n"
            f"📍 <b>{inp.region}, {inp.district}</b>\n"
            f"🏠 {prop_type_label}\n"
            f"🚪 {inp.rooms} комн.\n"
            f"📐 {inp.total_area} м²\n"
            f"✨ {cond_label}\n\n"
            f"💰 <b>Ориентировочная рыночная цена:</b>\n"
            f"<b>{range_str}</b>\n\n"
            f"🎯 <b>Центральная оценка:</b>\n"
            f"<b>{central_str}</b>\n\n"
            f"📈 <b>Уровень достоверности:</b> {conf_label}\n"
            f"🏘 <b>Сравненные аналоги:</b> {res.comparable_count} шт.\n"
            f"📐 <b>Медианная цена/м²:</b> {m2_str}/м²"
            f"{explanation_text}\n\n"
            f"⚠️ <i>Это расчетная рыночная оценка на основе данных UyAI, "
            f"не является официальной экспертизой.</i>"
        )

    return (
        f"{title}\n\n"
        f"📍 <b>{inp.region}, {inp.district}</b>\n"
        f"🏠 {prop_type_label}\n"
        f"🚪 {inp.rooms} xona\n"
        f"📐 {inp.total_area} m²\n"
        f"✨ {cond_label}\n\n"
        f"💰 <b>Taxminiy bozor bahosi:</b>\n"
        f"<b>{range_str}</b>\n\n"
        f"🎯 <b>Markaziy baho:</b>\n"
        f"<b>{central_str}</b>\n\n"
        f"📈 <b>Ishonchlilik:</b> {conf_label}\n"
        f"🏘 <b>Taqqoslangan e'lonlar:</b> {res.comparable_count} ta\n"
        f"📐 <b>Median narx/m²:</b> {m2_str}/m²"
        f"{explanation_text}\n\n"
        f"⚠️ <i>Bu taxminiy bozor bahosi bo‘lib, rasmiy baholash hisoblanmaydi.</i>"
    )


@valuation_router.callback_query(PropertyValuationStates.viewing_result, F.data == "val_act:comps")
async def handle_valuation_view_comps(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Display top approved comparable listings used in the calculation."""
    await callback.answer()
    data = await state.get_data()
    lang = data.get("language", "uz")
    comps_data = data.get("comps_data", [])

    if not comps_data:
        await callback.answer(get_text("val_no_comps", lang), show_alert=True)
        return

    header = get_text("val_comps_header", lang)
    lines = [header]
    for i, c in enumerate(comps_data[:3], start=1):
        price_fmt = f"{int(c['price']):,}".replace(",", " ")
        curr = c["currency"]
        p_str = f"${price_fmt}" if curr == "USD" else f"{price_fmt} {curr}"
        lines.append(
            f"{i}. <b>#{c['id']} — {c['rooms']} xonali ({c['total_area']} m²)</b>\n"
            f"   📍 {c['district']} | 💰 {p_str} ({c['price_per_m2']} {curr}/m²)\n"
            f"   Holati: {c.get('condition') or '—'}\n"
        )

    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer("\n".join(lines))


@valuation_router.callback_query(PropertyValuationStates.viewing_result, F.data == "val_act:search")
async def handle_valuation_action_search(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Redirect user to property search wizard."""
    await callback.answer()
    data = await state.get_data()
    lang = data.get("language", "uz")
    await state.clear()

    if callback.message and isinstance(callback.message, Message):
        search_prompt = "🏠 Qidiruv bo‘limiga xush kelibsiz. Qidiruv turini tanlang:"
        if lang == "ru":
            search_prompt = "🏠 Добро пожаловать в поиск недвижимости. Выберите категорию:"
        await callback.message.answer(
            search_prompt,
            reply_markup=get_main_menu_keyboard(lang),
        )


@valuation_router.callback_query(PropertyValuationStates.viewing_result, F.data == "val_act:submit")
async def handle_valuation_action_submit(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Redirect user to property submission wizard for sale or rent."""
    await callback.answer()
    data = await state.get_data()
    lang = data.get("language", "uz")
    listing_type = data.get("subject_listing_type", "sale")
    user_id = data.get("user_id")

    await state.clear()
    await state.update_data(listing_type=listing_type, user_id=user_id, language=lang)
    await state.set_state(PropertySubmissionStates.waiting_property_type)

    prompt = (
        get_text("explain_sell_process", lang)
        if listing_type == "sale"
        else get_text("explain_rent_process", lang)
    )

    from app.bot.keyboards import get_property_type_keyboard

    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(
            prompt,
            reply_markup=get_property_type_keyboard(lang),
        )


@valuation_router.callback_query(PropertyValuationStates.viewing_result, F.data == "val_act:broker")
async def handle_valuation_action_broker(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Redirect user to broker contact service."""
    await callback.answer()
    data = await state.get_data()
    lang = data.get("language", "uz")
    await state.clear()

    broker_text = (
        "👨‍💼 <b>Professional broker xizmati</b>\n\n"
        "Bizning malakali brokerlarimiz ko‘chmas mulkingizni eng ma'qul narxda sotish, "
        "sotib olish yoki ijaraga berishda yordam berishadi.\n\n"
        "Aloqa uchun telefon: <b>+998 71 200 00 00</b>"
    )
    if lang == "ru":
        broker_text = (
            "👨‍💼 <b>Услуги профессионального брокера</b>\n\n"
            "Наши сертифицированные брокеры помогут вам выгодно продать, "
            "купить или сдать в аренду вашу недвижимость.\n\n"
            "Телефон для связи: <b>+998 71 200 00 00</b>"
        )

    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(
            broker_text,
            reply_markup=get_main_menu_keyboard(lang),
        )


@valuation_router.callback_query(PropertyValuationStates.viewing_result, F.data == "val_act:menu")
async def handle_valuation_action_menu(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Exit valuation flow and return to main menu."""
    await callback.answer()
    data = await state.get_data()
    lang = data.get("language", "uz")
    await state.clear()

    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(
            get_text("main_menu_title", lang),
            reply_markup=get_main_menu_keyboard(lang),
        )
