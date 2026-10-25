"""Telegram handlers for staff broker viewing request management."""

import html

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import (
    MAIN_MENU_BUTTONS,
    get_broker_outcome_keyboard,
    get_broker_request_card_keyboard,
    get_main_menu_keyboard,
)
from app.bot.locales import get_text
from app.bot.states import BrokerViewingStates
from app.core.exceptions import (
    InvalidViewingTransitionError,
    PropertyUnavailableError,
    ViewingPermissionError,
    ViewingRequestNotFoundError,
    ViewingValidationError,
)
from app.logging import get_logger
from app.models.viewing_request import ViewingRequest
from app.services.user_service import UserService
from app.services.viewing_request_service import ViewingRequestService

logger = get_logger(__name__)

broker_requests_router = Router(name="broker_requests")


def format_broker_request_card(
    req: ViewingRequest,
    is_assigned_to_me: bool = False,
    lang: str = "uz",  # noqa: ARG001
) -> str:
    """Format staff view for a viewing or broker contact request.

    Privacy rule: Only shows customer phone after claim/assignment to this broker.
    """
    prop = req.property
    prop_type = (prop.property_type if prop else "Mulk").capitalize()
    listing_kind = f"{prop.listing_type.upper()}" if prop else ""
    region_info = f"{prop.region}, {prop.district}" if prop else "—"

    lines = [
        f"📋 <b>So‘rov #{req.id}</b>",
        f"🏷 Turi / Тип: <b>{req.request_type.upper()}</b> ({listing_kind})",
        f"🏠 {prop_type} #{req.property_id} - {prop.title if prop else ''}",
        f"📍 {region_info}",
    ]

    if req.request_type == "viewing":
        date_str = req.preferred_date.strftime("%d.%m.%Y") if req.preferred_date else "—"
        time_str = req.preferred_time or "—"
        lines.append(f"📅 Afzal sana / Дата: <b>{date_str}</b>")
        lines.append(f"🕐 Afzal vaqt / Время: <b>{time_str}</b>")

    if req.customer:
        customer_name = html.escape(req.customer.first_name or "Mijoz")
        lines.append(f"👤 Mijoz: <b>{customer_name}</b>")
        # Only show phone to assigned broker
        if is_assigned_to_me and req.customer.phone:
            lines.append(f"📞 Telefon: <b>{req.customer.phone}</b>")

    if req.customer_comment:
        lines.append(f"💬 Izoh / Комментарий: {html.escape(req.customer_comment)}")

    lines.append(f"📌 Holat: <b>{req.status.upper()}</b>")

    if req.rejection_reason and req.status == "rejected":
        lines.append(f"⚠️ Rad sababi: {html.escape(req.rejection_reason)}")
    if req.outcome and req.status == "completed":
        lines.append(f"🎯 Natija / Результат: <b>{req.outcome}</b>")

    return "\n".join(lines)


async def send_customer_notification(
    bot: any,
    customer_tg_id: int,
    text: str,
) -> None:
    """Safely notify customer without failing database transaction."""
    try:
        await bot.send_message(chat_id=customer_tg_id, text=text)
    except Exception as e:
        logger.warning(
            "Failed to send viewing notification to customer_tg_id=%s: %s",
            customer_tg_id,
            e,
        )


# --- /viewing_requests Command ---


@broker_requests_router.message(Command("viewing_requests"))
async def handle_viewing_requests_command(
    message: Message,
    session: AsyncSession,
) -> None:
    """Display pending and assigned viewing requests for authorized brokers."""
    if not message.from_user:
        return

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, message.from_user.id)
    if not user:
        return

    lang = user.language
    viewing_service = ViewingRequestService()

    try:
        requests = await viewing_service.list_broker_requests(
            session,
            broker_user_id=user.id,
            statuses=["pending", "assigned", "accepted"],
        )
    except ViewingPermissionError:
        await message.answer(get_text("broker_permission_denied", lang))
        return

    if not requests:
        await message.answer(
            get_text("broker_requests_empty", lang),
            reply_markup=get_main_menu_keyboard(lang),
        )
        return

    await message.answer(get_text("broker_requests_title", lang))

    for req in requests:
        is_assigned_to_me = req.broker_user_id == user.id
        card_text = format_broker_request_card(
            req,
            is_assigned_to_me=is_assigned_to_me,
            lang=lang,
        )
        kb = get_broker_request_card_keyboard(
            request_id=req.id,
            status=req.status,
            is_assigned_to_me=is_assigned_to_me,
            lang=lang,
        )
        await message.answer(card_text, reply_markup=kb)


# --- Broker Actions: Claim ---


@broker_requests_router.callback_query(F.data.startswith("broker_req:claim:"))
async def handle_broker_claim(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Claim unassigned request."""
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
        claimed = await viewing_service.claim_request(
            session,
            request_id=request_id,
            broker_user_id=user.id,
        )
        try:
            await callback.answer(get_text("broker_claim_success", lang))
        except TelegramBadRequest:
            pass

        if callback.message and isinstance(callback.message, Message):
            updated_text = format_broker_request_card(claimed, is_assigned_to_me=True, lang=lang)
            new_kb = get_broker_request_card_keyboard(
                request_id=claimed.id,
                status=claimed.status,
                is_assigned_to_me=True,
                lang=lang,
            )
            await callback.message.edit_text(updated_text, reply_markup=new_kb)
    except (
        ViewingPermissionError,
        InvalidViewingTransitionError,
        ViewingRequestNotFoundError,
    ) as e:
        try:
            await callback.answer(str(e), show_alert=True)
        except TelegramBadRequest:
            pass


# --- Broker Actions: Accept ---


@broker_requests_router.callback_query(F.data.startswith("broker_req:accept:"))
async def handle_broker_accept(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Accept viewing or broker contact request."""
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
        accepted = await viewing_service.accept_request(
            session,
            request_id=request_id,
            broker_user_id=user.id,
        )
        try:
            await callback.answer(get_text("broker_accept_success", lang))
        except TelegramBadRequest:
            pass

        # Notify customer
        if callback.bot and accepted.customer:
            cust_lang = accepted.customer.language or "uz"
            prop_title = (
                accepted.property.title if accepted.property else f"#{accepted.property_id}"
            )
            if accepted.request_type == "viewing":
                date_str = (
                    accepted.preferred_date.strftime("%d.%m.%Y") if accepted.preferred_date else ""
                )
                time_str = accepted.preferred_time or ""
                notify_text = get_text("customer_notify_accepted", cust_lang).format(
                    prop_id=accepted.property_id,
                    title=prop_title,
                    date=date_str,
                    time=time_str,
                )
            else:
                notify_text = get_text("customer_notify_contact_accepted", cust_lang).format(
                    prop_id=accepted.property_id,
                )
            await send_customer_notification(
                callback.bot, accepted.customer.telegram_id, notify_text
            )

        if callback.message and isinstance(callback.message, Message):
            updated_text = format_broker_request_card(accepted, is_assigned_to_me=True, lang=lang)
            new_kb = get_broker_request_card_keyboard(
                request_id=accepted.id,
                status=accepted.status,
                is_assigned_to_me=True,
                lang=lang,
            )
            await callback.message.edit_text(updated_text, reply_markup=new_kb)
    except (
        ViewingPermissionError,
        PropertyUnavailableError,
        InvalidViewingTransitionError,
        ViewingRequestNotFoundError,
    ) as e:
        try:
            await callback.answer(str(e), show_alert=True)
        except TelegramBadRequest:
            pass


# --- Broker Actions: Reject ---


@broker_requests_router.callback_query(F.data.startswith("broker_req:reject:"))
async def handle_broker_reject_start(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Prompt broker for rejection reason."""
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

    await state.set_state(BrokerViewingStates.waiting_rejection_reason)
    await state.update_data(request_id=request_id, language=lang)

    if callback.message and isinstance(callback.message, Message):
        await callback.message.reply(get_text("broker_ask_reject_reason", lang))


@broker_requests_router.message(
    BrokerViewingStates.waiting_rejection_reason, ~F.text.in_(MAIN_MENU_BUTTONS)
)
async def handle_broker_reject_reason(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Process rejection reason and finalize rejection."""
    data = await state.get_data()
    request_id = data.get("request_id")
    lang = data.get("language", "uz")

    reason = (message.text or "").strip()
    if reason in ("/cancel", "✏️ Bekor qilish", "❌ Bekor qilish"):
        await state.clear()
        await message.answer(
            get_text("cancel_text", lang), reply_markup=get_main_menu_keyboard(lang)
        )
        return

    if not message.from_user:
        return

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, message.from_user.id)
    if not user:
        await state.clear()
        return

    viewing_service = ViewingRequestService()

    try:
        rejected = await viewing_service.reject_request(
            session,
            request_id=request_id,
            broker_user_id=user.id,
            reason=reason,
        )
        await state.clear()
        await message.answer(get_text("broker_reject_success", lang))

        # Notify customer
        if message.bot and rejected.customer:
            cust_lang = rejected.customer.language or "uz"
            safe_reason = html.escape(reason)
            notify_text = get_text("customer_notify_rejected", cust_lang).format(
                prop_id=rejected.property_id,
                reason=safe_reason,
            )
            await send_customer_notification(
                message.bot, rejected.customer.telegram_id, notify_text
            )
    except ViewingValidationError as e:
        await message.answer(str(e))
    except Exception as e:
        await state.clear()
        await message.answer(f"Xatolik: {e}")


# --- Broker Actions: Complete ---


@broker_requests_router.callback_query(F.data.startswith("broker_req:complete:"))
async def handle_broker_complete_prompt(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Display outcome choices for completing a viewing."""
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

    prompt_text = get_text("broker_select_outcome", lang)
    kb = get_broker_outcome_keyboard(request_id, lang=lang)

    if callback.message and isinstance(callback.message, Message):
        await callback.message.reply(prompt_text, reply_markup=kb)


@broker_requests_router.callback_query(F.data.startswith("broker_out:"))
async def handle_broker_outcome_selected(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Finalize viewing completion with outcome."""
    if not callback.data or not callback.from_user:
        return

    parts = callback.data.split(":")
    outcome = parts[1]
    request_id = int(parts[2])

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        return

    lang = user.language
    viewing_service = ViewingRequestService()

    try:
        completed = await viewing_service.complete_request(
            session,
            request_id=request_id,
            broker_user_id=user.id,
            outcome=outcome,
        )
        try:
            await callback.answer(get_text("broker_complete_success", lang))
        except TelegramBadRequest:
            pass

        # Notify customer
        if callback.bot and completed.customer:
            cust_lang = completed.customer.language or "uz"
            notify_text = get_text("customer_notify_completed", cust_lang).format(
                prop_id=completed.property_id,
            )
            await send_customer_notification(
                callback.bot, completed.customer.telegram_id, notify_text
            )

        if callback.message and isinstance(callback.message, Message):
            updated_text = format_broker_request_card(completed, is_assigned_to_me=True, lang=lang)
            await callback.message.edit_text(updated_text)
    except (
        ViewingPermissionError,
        InvalidViewingTransitionError,
        ViewingValidationError,
        ViewingRequestNotFoundError,
    ) as e:
        try:
            await callback.answer(str(e), show_alert=True)
        except TelegramBadRequest:
            pass
