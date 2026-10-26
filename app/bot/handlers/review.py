"""Staff property review command and action handlers."""

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import get_review_action_keyboard
from app.bot.locales import (
    format_cadastre,
    format_condition,
    format_furniture,
    format_listing_type,
    format_property_type,
    get_text,
)
from app.bot.states import PropertyReviewStates
from app.core.exceptions import AuthorizationError
from app.logging import get_logger
from app.services.property_service import PropertyService
from app.services.user_service import UserService

logger = get_logger(__name__)

review_router = Router(name="review")


@review_router.message(Command("review_properties"))
async def handle_review_properties_list(
    message: Message,
    session: AsyncSession,
) -> None:
    """List pending submitted properties for authorized staff members."""
    if not message.from_user:
        return

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, message.from_user.id)
    if not user:
        return

    lang = user.language
    prop_service = PropertyService()

    try:
        pending = await prop_service.list_pending_review_properties(
            session, reviewer_user_id=user.id
        )
    except AuthorizationError:
        await message.answer(get_text("unauthorized_review", lang))
        return

    if not pending:
        await message.answer(get_text("review_no_pending", lang))
        return

    # Show first pending property with action buttons
    prop = pending[0]
    await prop_service.start_review(session, property_id=prop.id, reviewer_user_id=user.id)

    title = get_text("review_item_title", lang).format(id=prop.id)
    prop_type = format_property_type(prop.property_type, lang)
    listing_type = format_listing_type(prop.listing_type, lang)
    cond = format_condition(prop.condition, lang)
    cadastre = format_cadastre(prop.cadastre_status, lang)
    furniture = format_furniture(prop.has_furniture, lang)

    details = (
        f"{title}\n\n"
        f"🏷 Turi: {prop_type} ({listing_type})\n"
        f"📍 Manzil: {prop.region}, {prop.district}, {prop.address}\n"
        f"🚪 Xonalar: {prop.rooms} | 📐 Maydon: {prop.total_area} m²\n"
        f"🏢 Qavat: {prop.floor}/{prop.total_floors}\n"
        f"🛠 Ta’mir holati: {cond} | 🛋 Mebel: {furniture}\n"
        f"📄 Kadastr: {cadastre}\n"
        f"💰 Narxi: {prop.price:,.0f} {prop.currency}\n"
        f"Status: <b>{prop.status.upper()}</b>"
    )

    await message.answer(details, reply_markup=get_review_action_keyboard(prop.id))


@review_router.callback_query(F.data.startswith("review_act:approve:"))
async def handle_approve_callback(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Approve property and send safe notification to owner."""
    if not callback.data or not callback.from_user:
        return

    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

    property_id = int(callback.data.split(":")[2])
    user_service = UserService()
    reviewer = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not reviewer:
        return

    prop_service = PropertyService()
    try:
        prop = await prop_service.approve_listing(
            session, property_id=property_id, reviewer_user_id=reviewer.id
        )
    except AuthorizationError:
        if callback.message and isinstance(callback.message, Message):
            await callback.message.answer(get_text("unauthorized_review", reviewer.language))
        return

    if callback.message and isinstance(callback.message, Message):
        await callback.message.edit_text(
            get_text("listing_approved_broker", reviewer.language).format(id=property_id)
        )

    # Safely notify owner without rolling back DB transaction if notification fails
    try:
        owner = await user_service.user_repo.get_by_id(session, prop.owner_user_id)
        if owner and callback.bot:
            owner_msg = get_text("approved_notification", owner.language).format(id=property_id)
            await callback.bot.send_message(chat_id=owner.telegram_id, text=owner_msg)
    except Exception as exc:
        logger.warning(
            "Could not notify owner for approved property id=%d: %s",
            property_id,
            exc.__class__.__name__,
        )


@review_router.callback_query(F.data.startswith("review_act:reject:"))
async def handle_reject_prompt(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Prompt reviewer to supply reason for property rejection."""
    if not callback.data:
        return

    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

    property_id = int(callback.data.split(":")[2])
    await state.update_data(reject_property_id=property_id)
    await state.set_state(PropertyReviewStates.waiting_rejection_reason)

    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer(get_text("ask_rejection_reason", "uz"))


@review_router.message(F.text, PropertyReviewStates.waiting_rejection_reason)
async def handle_rejection_reason(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Reject property with given reason and notify owner."""
    if not message.from_user:
        return

    data = await state.get_data()
    property_id = data.get("reject_property_id")
    reason = (message.text or "").strip()

    user_service = UserService()
    reviewer = await user_service.get_by_telegram_id(session, message.from_user.id)
    if not reviewer:
        return

    prop_service = PropertyService()
    try:
        prop = await prop_service.reject_listing(
            session,
            property_id=property_id,
            reviewer_user_id=reviewer.id,
            rejection_reason=reason,
        )
    except AuthorizationError:
        await message.answer(get_text("unauthorized_review", reviewer.language))
        await state.clear()
        return

    await state.clear()
    await message.answer(
        get_text("listing_rejected_broker", reviewer.language).format(id=property_id)
    )

    # Safely notify owner
    try:
        owner = await user_service.user_repo.get_by_id(session, prop.owner_user_id)
        if owner and message.bot:
            owner_msg = get_text("rejected_notification", owner.language).format(
                id=property_id, reason=reason
            )
            await message.bot.send_message(chat_id=owner.telegram_id, text=owner_msg)
    except Exception as exc:
        logger.warning(
            "Could not notify owner for rejected property id=%d: %s",
            property_id,
            exc.__class__.__name__,
        )
