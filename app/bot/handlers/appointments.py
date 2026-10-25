"""Telegram handlers for customer viewing requests, appointments, and broker contact."""

import html
from datetime import UTC, datetime, timedelta

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import (
    MAIN_MENU_BUTTONS,
    get_appointment_cancel_confirm_keyboard,
    get_appointment_card_keyboard,
    get_broker_contact_confirm_keyboard,
    get_main_menu_keyboard,
    get_viewing_confirm_keyboard,
    get_viewing_date_keyboard,
    get_viewing_time_keyboard,
)
from app.bot.locales import LOCALES, get_text
from app.bot.states import ViewingRequestStates
from app.core.exceptions import (
    DuplicateViewingRequestError,
    InvalidViewingTransitionError,
    PropertyUnavailableError,
    ViewingPermissionError,
    ViewingRequestNotFoundError,
    ViewingValidationError,
)
from app.logging import get_logger
from app.models.viewing_request import ViewingRequest
from app.services.property_search_service import PropertySearchService
from app.services.user_service import UserService
from app.services.viewing_request_service import ViewingRequestService

logger = get_logger(__name__)

appointments_router = Router(name="appointments")

APPOINTMENTS_BUTTONS = {
    locale_dict.get("btn_appointments")
    for locale_dict in LOCALES.values()
    if locale_dict.get("btn_appointments")
} | {"📅 Uchrashuvlarim", "📅 Мои встречи"}


def format_appointment_card(req: ViewingRequest, lang: str = "uz") -> str:  # noqa: ARG001
    """Format customer view for a viewing or broker contact request."""
    prop = req.property
    prop_type = (prop.property_type if prop else "Mulk").capitalize()
    listing_kind = f"({prop.listing_type.upper()})" if prop else ""
    region_info = f"{prop.region}, {prop.district}" if prop else "—"

    status_badges = {
        "pending": "⏳ Kutilmoqda / В ожидании",
        "assigned": "👨‍💼 Brokerga biriktirildi / Назначен брокер",
        "accepted": "✅ Tasdiqlandi / Подтверждено",
        "rejected": "❌ Rad etildi / Отклонено",
        "cancelled": "🚫 Bekor qilindi / Отменено",
        "completed": "🏁 Yakunlandi / Завершено",
    }
    badge = status_badges.get(req.status, req.status.upper())

    lines = [
        f"🆔 <b>So‘rov #{req.id}</b>",
        f"🏠 {prop_type} {listing_kind} #{req.property_id}",
        f"📍 {region_info}",
    ]

    if req.request_type == "viewing":
        date_str = req.preferred_date.strftime("%d.%m.%Y") if req.preferred_date else "—"
        time_str = req.preferred_time or "—"
        lines.append(f"📅 Afzal sana / Дата: <b>{date_str}</b>")
        lines.append(f"🕐 Afzal vaqt / Время: <b>{time_str}</b>")
    else:
        lines.append("📞 Turi / Тип: <b>Broker bilan bog‘lanish</b>")

    if req.customer_comment:
        lines.append(f"💬 Izoh / Комментарий: {html.escape(req.customer_comment)}")

    lines.append(f"📌 Status: <b>{badge}</b>")

    if req.rejection_reason and req.status == "rejected":
        lines.append(f"⚠️ Rad sababi: {html.escape(req.rejection_reason)}")
    if req.outcome and req.status == "completed":
        lines.append(f"🎯 Natija / Результат: {req.outcome}")

    return "\n".join(lines)


# --- Customer Appointments List ---


@appointments_router.message(F.text.in_(APPOINTMENTS_BUTTONS))
async def handle_my_appointments(
    message: Message,
    session: AsyncSession,
) -> None:
    """List customer's appointments and requests."""
    if not message.from_user:
        return

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, message.from_user.id)
    if not user:
        return

    lang = user.language
    viewing_service = ViewingRequestService()
    requests = await viewing_service.list_customer_requests(session, customer_user_id=user.id)

    if not requests:
        await message.answer(
            get_text("appointments_empty", lang),
            reply_markup=get_main_menu_keyboard(lang),
        )
        return

    await message.answer(get_text("appointments_title", lang))

    for req in requests:
        card_text = format_appointment_card(req, lang)
        is_cancellable = req.status in ("pending", "assigned", "accepted")
        kb = get_appointment_card_keyboard(req.id, cancellable=is_cancellable, lang=lang)
        await message.answer(card_text, reply_markup=kb)


# --- Customer Request Cancellation ---


@appointments_router.callback_query(F.data.startswith("req:cancel:"))
async def handle_cancel_appointment_prompt(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Ask customer confirmation before cancelling request."""
    if not callback.data or not callback.from_user:
        return

    request_id = int(callback.data.split(":")[2])
    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    lang = user.language if user else "uz"

    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

    prompt_text = get_text("cancel_confirm_prompt", lang)
    kb = get_appointment_cancel_confirm_keyboard(request_id, lang=lang)

    if callback.message and isinstance(callback.message, Message):
        await callback.message.reply(prompt_text, reply_markup=kb)


@appointments_router.callback_query(F.data.startswith("req:cancel_confirm:"))
async def handle_confirm_cancel_appointment(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Perform request cancellation."""
    if not callback.data or not callback.from_user:
        return

    request_id = int(callback.data.split(":")[2])
    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        return

    lang = user.language
    viewing_service = ViewingRequestService()

    try:
        await viewing_service.cancel_customer_request(
            session,
            request_id=request_id,
            customer_user_id=user.id,
        )
        try:
            await callback.answer(get_text("cancel_request_success", lang), show_alert=True)
        except TelegramBadRequest:
            pass

        if callback.message and isinstance(callback.message, Message):
            await callback.message.edit_text(get_text("cancel_request_success", lang))
    except (
        ViewingPermissionError,
        InvalidViewingTransitionError,
        ViewingRequestNotFoundError,
    ) as e:
        try:
            await callback.answer(str(e), show_alert=True)
        except TelegramBadRequest:
            pass


@appointments_router.callback_query(F.data == "req:cancel_back")
async def handle_cancel_back(callback: CallbackQuery) -> None:
    """Acknowledge back action and delete cancel prompt."""
    try:
        await callback.answer()
        if callback.message and isinstance(callback.message, Message):
            await callback.message.delete()
    except TelegramBadRequest:
        pass


# --- Viewing Request Wizard ---


@appointments_router.callback_query(F.data.startswith("viewing:create:"))
async def handle_start_viewing_wizard(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Initialize viewing appointment request wizard."""
    if not callback.data or not callback.from_user:
        return

    property_id = int(callback.data.split(":")[2])
    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user or not await user_service.is_registration_complete(user):
        try:
            await callback.answer("Iltimos, avval ro‘yxatdan o‘ting: /start", show_alert=True)
        except TelegramBadRequest:
            pass
        return

    lang = user.language

    # Verify property is approved
    search_service = PropertySearchService()
    try:
        prop = await search_service.get_approved_details(session, property_id)
    except Exception:
        try:
            await callback.answer(get_text("property_unavailable_error", lang), show_alert=True)
        except TelegramBadRequest:
            pass
        return

    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

    await state.clear()
    await state.set_state(ViewingRequestStates.choosing_date)
    await state.update_data(
        property_id=property_id,
        property_title=prop.title or f"#{prop.id}",
        language=lang,
    )

    prompt = get_text("viewing_ask_date", lang)
    if callback.message and isinstance(callback.message, Message):
        await callback.message.reply(prompt, reply_markup=get_viewing_date_keyboard(lang))


@appointments_router.callback_query(
    ViewingRequestStates.choosing_date, F.data.startswith("view_date:")
)
async def handle_viewing_date_choice(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Handle date buttons (today, tomorrow, custom, cancel)."""
    action = callback.data.split(":")[1] if callback.data else ""
    data = await state.get_data()
    lang = data.get("language", "uz")

    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

    if action == "cancel":
        await state.clear()
        if callback.message and isinstance(callback.message, Message):
            await callback.message.edit_text(get_text("cancel_text", lang))
        return

    today = datetime.now(UTC).date()

    if action == "today":
        selected_date = today
        await state.update_data(preferred_date=selected_date.isoformat())
        await state.set_state(ViewingRequestStates.choosing_time)
        if callback.message and isinstance(callback.message, Message):
            date_label = selected_date.strftime("%d.%m.%Y")
            time_prompt = get_text("viewing_ask_time", lang)
            await callback.message.edit_text(
                f"📅 <b>{date_label}</b>\n\n{time_prompt}",
                reply_markup=get_viewing_time_keyboard(lang),
            )
    elif action == "tomorrow":
        selected_date = today + timedelta(days=1)
        await state.update_data(preferred_date=selected_date.isoformat())
        await state.set_state(ViewingRequestStates.choosing_time)
        if callback.message and isinstance(callback.message, Message):
            date_label = selected_date.strftime("%d.%m.%Y")
            time_prompt = get_text("viewing_ask_time", lang)
            await callback.message.edit_text(
                f"📅 <b>{date_label}</b>\n\n{time_prompt}",
                reply_markup=get_viewing_time_keyboard(lang),
            )
    elif action == "custom":
        await state.set_state(ViewingRequestStates.waiting_custom_date)
        if callback.message and isinstance(callback.message, Message):
            await callback.message.edit_text(get_text("viewing_ask_custom_date", lang))


@appointments_router.message(
    ViewingRequestStates.waiting_custom_date, ~F.text.in_(MAIN_MENU_BUTTONS)
)
async def handle_custom_date_input(
    message: Message,
    state: FSMContext,
) -> None:
    """Process DD.MM.YYYY custom date string."""
    data = await state.get_data()
    lang = data.get("language", "uz")

    text = (message.text or "").strip()
    if text in ("/cancel", "✏️ Bekor qilish", "❌ Bekor qilish"):
        await state.clear()
        await message.answer(
            get_text("cancel_text", lang), reply_markup=get_main_menu_keyboard(lang)
        )
        return

    try:
        parsed_date = datetime.strptime(text, "%d.%m.%Y").date()
        today = datetime.now(UTC).date()
        if parsed_date < today:
            await message.answer(get_text("viewing_invalid_date", lang))
            return
    except ValueError:
        await message.answer(get_text("viewing_invalid_date", lang))
        return

    await state.update_data(preferred_date=parsed_date.isoformat())
    await state.set_state(ViewingRequestStates.choosing_time)
    await message.answer(
        f"📅 <b>{parsed_date.strftime('%d.%m.%Y')}</b>\n\n{get_text('viewing_ask_time', lang)}",
        reply_markup=get_viewing_time_keyboard(lang),
    )


@appointments_router.callback_query(
    ViewingRequestStates.choosing_time, F.data.startswith("view_time:")
)
async def handle_viewing_time_choice(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Process selected time slot."""
    raw_time = callback.data.split(":", 1)[1] if callback.data else ""
    data = await state.get_data()
    lang = data.get("language", "uz")

    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

    if raw_time == "cancel":
        await state.clear()
        if callback.message and isinstance(callback.message, Message):
            await callback.message.edit_text(get_text("cancel_text", lang))
        return

    await state.update_data(preferred_time=raw_time)
    await state.set_state(ViewingRequestStates.waiting_comment)

    prompt = get_text("viewing_ask_comment", lang)
    if callback.message and isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"🕐 <b>{raw_time}</b>\n\n{prompt}",
        )


@appointments_router.message(ViewingRequestStates.waiting_comment, ~F.text.in_(MAIN_MENU_BUTTONS))
async def handle_viewing_comment(
    message: Message,
    state: FSMContext,
) -> None:
    """Process comment input or skip."""
    data = await state.get_data()
    lang = data.get("language", "uz")

    text = (message.text or "").strip()
    if text in ("/cancel", "✏️ Bekor qilish", "❌ Bekor qilish"):
        await state.clear()
        await message.answer(
            get_text("cancel_text", lang), reply_markup=get_main_menu_keyboard(lang)
        )
        return

    comment: str | None = None
    if text.lower() not in (
        "skip",
        "o‘tkazib yuborish",
        "o'tkazib yuborish",
        "пропустить",
        "⏭ o‘tkazib yuborish",
    ):
        comment = text[:1000]

    await state.update_data(customer_comment=comment)
    await state.set_state(ViewingRequestStates.confirming)

    # Render preview
    pref_date = data.get("preferred_date", "")
    pref_time = data.get("preferred_time", "")
    prop_id = data.get("property_id")
    title = data.get("property_title", "")

    preview = (
        f"{get_text('viewing_preview_title', lang)}\n\n"
        f"🏠 Mulk #{prop_id} - {title}\n"
        f"📅 Afzal sana / Дата: <b>{pref_date}</b>\n"
        f"🕐 Afzal vaqt / Время: <b>{pref_time}</b>\n"
        f"💬 Izoh / Комментарий: {html.escape(comment or '—')}"
    )
    await message.answer(preview, reply_markup=get_viewing_confirm_keyboard(lang))


@appointments_router.callback_query(
    ViewingRequestStates.confirming, F.data.startswith("view_confirm:")
)
async def handle_viewing_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Finalize viewing request submission."""
    choice = callback.data.split(":")[1] if callback.data else ""
    data = await state.get_data()
    lang = data.get("language", "uz")

    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

    if choice != "yes":
        await state.clear()
        if callback.message and isinstance(callback.message, Message):
            await callback.message.edit_text(get_text("cancel_text", lang))
        return

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await state.clear()
        return

    viewing_service = ViewingRequestService()
    prop_id = data.get("property_id")
    date_iso = data.get("preferred_date")
    pref_time = data.get("preferred_time")
    comment = data.get("customer_comment")

    try:
        parsed_date = datetime.fromisoformat(date_iso).date()
        await viewing_service.create_viewing_request(
            session,
            customer_user_id=user.id,
            property_id=prop_id,
            preferred_date=parsed_date,
            preferred_time=pref_time,
            customer_comment=comment,
        )
        await state.clear()

        success_text = get_text("viewing_submitted_success", lang)
        if callback.message and isinstance(callback.message, Message):
            await callback.message.edit_text(success_text)
    except DuplicateViewingRequestError:
        await state.clear()
        err_msg = get_text("duplicate_request_error", lang)
        if callback.message and isinstance(callback.message, Message):
            await callback.message.edit_text(err_msg)
    except PropertyUnavailableError:
        await state.clear()
        err_msg = get_text("property_unavailable_error", lang)
        if callback.message and isinstance(callback.message, Message):
            await callback.message.edit_text(err_msg)
    except ViewingValidationError as e:
        if callback.message and isinstance(callback.message, Message):
            await callback.message.answer(str(e))


# --- Broker Contact Request Flow ---


@appointments_router.callback_query(F.data.startswith("broker:contact:"))
async def handle_broker_contact_prompt(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Prompt confirmation before creating broker contact request."""
    if not callback.data or not callback.from_user:
        return

    property_id = int(callback.data.split(":")[2])
    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user or not await user_service.is_registration_complete(user):
        try:
            await callback.answer("Iltimos, avval ro‘yxatdan o‘ting: /start", show_alert=True)
        except TelegramBadRequest:
            pass
        return

    lang = user.language
    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

    prompt_text = get_text("broker_contact_confirm_prompt", lang)
    kb = get_broker_contact_confirm_keyboard(property_id, lang=lang)

    if callback.message and isinstance(callback.message, Message):
        await callback.message.reply(prompt_text, reply_markup=kb)


@appointments_router.callback_query(F.data.startswith("broker_contact:confirm:"))
async def handle_broker_contact_confirm(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Submit broker contact request."""
    if not callback.data or not callback.from_user:
        return

    property_id = int(callback.data.split(":")[2])
    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        return

    lang = user.language
    viewing_service = ViewingRequestService()

    try:
        await viewing_service.create_broker_contact_request(
            session,
            customer_user_id=user.id,
            property_id=property_id,
        )
        try:
            await callback.answer(get_text("broker_contact_submitted_success", lang))
        except TelegramBadRequest:
            pass

        if callback.message and isinstance(callback.message, Message):
            await callback.message.edit_text(get_text("broker_contact_submitted_success", lang))
    except DuplicateViewingRequestError:
        err_msg = get_text("duplicate_request_error", lang)
        try:
            await callback.answer(err_msg, show_alert=True)
        except TelegramBadRequest:
            pass
        if callback.message and isinstance(callback.message, Message):
            await callback.message.edit_text(err_msg)
    except PropertyUnavailableError:
        err_msg = get_text("property_unavailable_error", lang)
        try:
            await callback.answer(err_msg, show_alert=True)
        except TelegramBadRequest:
            pass
        if callback.message and isinstance(callback.message, Message):
            await callback.message.edit_text(err_msg)


@appointments_router.callback_query(F.data == "broker_contact:cancel")
async def handle_broker_contact_cancel(callback: CallbackQuery) -> None:
    """Cancel broker contact prompt."""
    try:
        await callback.answer()
        if callback.message and isinstance(callback.message, Message):
            await callback.message.delete()
    except TelegramBadRequest:
        pass
