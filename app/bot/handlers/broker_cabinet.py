"""Telegram handlers for Broker Cabinet and Lead Management."""

import html
from datetime import UTC, datetime, timedelta

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import (
    MAIN_MENU_BUTTONS,
    get_broker_cabinet_keyboard,
    get_broker_leads_list_keyboard,
    get_followup_actions_keyboard,
    get_followup_time_shortcuts_keyboard,
    get_followup_type_keyboard,
    get_lead_card_keyboard,
    get_lead_history_back_keyboard,
    get_lead_lost_reason_keyboard,
    get_lead_stage_choice_keyboard,
)
from app.bot.locales import get_text
from app.bot.states import BrokerCabinetStates
from app.core.exceptions import (
    FollowUpNotFoundError,
    InvalidLeadTransitionError,
    LeadAlreadyAssignedError,
    LeadNotFoundError,
    LeadPermissionError,
    LeadValidationError,
)
from app.logging import get_logger
from app.models.lead import Lead, LeadFollowUp
from app.services.lead_service import LeadService
from app.services.user_service import UserService

logger = get_logger(__name__)

broker_cabinet_router = Router(name="broker_cabinet")


def format_lead_card(
    lead: Lead,
    is_assigned_to_me: bool = False,
    can_view_phone: bool = False,
    lang: str = "uz",
) -> str:
    """Format single lead details card."""
    prop = lead.property
    prop_type = (prop.property_type if prop else "Mulk").capitalize()
    listing_kind = f"{prop.listing_type.upper()}" if prop else ""
    region_info = f"{prop.region}, {prop.district}" if prop else "—"

    stage_title = get_text(f"stage_{lead.stage}", lang)
    source_title = lead.source.upper()

    lines = [
        f"📌 <b>Lead #{lead.id}</b>",
        f"🏷 Manba / Источник: <b>{source_title}</b>",
        f"🏠 {prop_type} #{lead.property_id} ({listing_kind})",
        f"📍 {region_info}",
        f"📊 Bosqich: <b>{stage_title}</b>",
    ]

    if lead.customer:
        customer_name = html.escape(lead.customer.first_name or "Mijoz")
        lines.append(f"👤 Mijoz: <b>{customer_name}</b>")
        if can_view_phone and lead.customer.phone:
            lines.append(f"📞 Telefon: <b>{lead.customer.phone}</b>")
        elif not is_assigned_to_me:
            lines.append("📞 Telefon: <i>🔒 Biriktirilgach ko‘rinadi</i>")

    broker_name = (
        html.escape(lead.broker.first_name or "Broker") if lead.broker else "<i>Biriktirilmagan</i>"
    )
    lines.append(f"👨‍💼 Broker: <b>{broker_name}</b>")

    if lead.close_reason and lead.stage in ("won", "lost"):
        reason_label = get_text(f"lost_reason_{lead.close_reason}", lang)
        lines.append(f"⚠️ Yopilish sababi: {reason_label}")

    if lead.notes:
        latest_note = lead.notes[0]
        lines.append(f"\n📝 Oxirgi eslatma: <i>{html.escape(latest_note.text)}</i>")

    return "\n".join(lines)


def format_followup_card(
    fu: LeadFollowUp,
    lang: str = "uz",
) -> str:
    """Format single follow-up task card."""
    type_title = get_text(f"task_{fu.task_type}", lang)
    due_str = fu.due_at.strftime("%d.%m.%Y %H:%M")

    lines = [
        f"⏰ <b>Vazifa #{fu.id}</b> ({type_title})",
        f"📌 Lead #{fu.lead_id}",
        f"🕐 Muddat: <b>{due_str}</b>",
        f"📌 Holat: <b>{fu.status.upper()}</b>",
    ]
    if fu.note:
        lines.append(f"💬 Izoh: {html.escape(fu.note)}")
    return "\n".join(lines)


# --- /broker Command & Home ---


@broker_cabinet_router.message(Command("broker"))
async def handle_broker_command(
    message: Message,
    session: AsyncSession,
) -> None:
    """Display broker cabinet menu for authorized brokers."""
    if not message.from_user:
        return

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, message.from_user.id)
    if not user:
        return

    lang = user.language
    lead_service = LeadService()

    allowed_types = await lead_service.get_broker_allowed_listing_types(session, user.id)
    if not allowed_types:
        await message.answer(get_text("broker_permission_denied", lang))
        return

    await message.answer(
        get_text("broker_cabinet_title", lang),
        reply_markup=get_broker_cabinet_keyboard(lang),
    )


@broker_cabinet_router.callback_query(F.data == "broker_cab:home")
async def handle_broker_cabinet_home(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Return to broker cabinet home menu."""
    await state.clear()
    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer()
        return

    lang = user.language
    lead_service = LeadService()

    allowed_types = await lead_service.get_broker_allowed_listing_types(session, user.id)
    if not allowed_types:
        await callback.answer(get_text("broker_permission_denied", lang), show_alert=True)
        return

    await callback.answer()
    if callback.message:
        try:
            await callback.message.edit_text(
                get_text("broker_cabinet_title", lang),
                reply_markup=get_broker_cabinet_keyboard(lang),
            )
        except TelegramBadRequest:
            await callback.message.answer(
                get_text("broker_cabinet_title", lang),
                reply_markup=get_broker_cabinet_keyboard(lang),
            )


# --- Unassigned Leads List ---


@broker_cabinet_router.callback_query(F.data.startswith("broker_cab:unassigned:"))
async def handle_unassigned_leads_list(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Display unassigned leads list."""
    if not callback.data or not callback.message:
        await callback.answer()
        return

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer()
        return

    lang = user.language
    page = int(callback.data.split(":")[2])
    limit = 5
    offset = page * limit

    lead_service = LeadService()
    try:
        leads = await lead_service.list_unassigned_leads(
            session,
            broker_user_id=user.id,
            limit=limit + 1,
            offset=offset,
        )
    except LeadPermissionError:
        await callback.answer(get_text("broker_permission_denied", lang), show_alert=True)
        return

    await callback.answer()

    if not leads and page == 0:
        await callback.message.edit_text(
            get_text("leads_empty_unassigned", lang),
            reply_markup=get_broker_leads_list_keyboard([], 0, 0, "unassigned", lang),
        )
        return

    has_more = len(leads) > limit
    page_leads = leads[:limit]
    total_pages = page + 2 if has_more else page + 1

    text = f"🔥 <b>Yangi (erkin) leadlar</b> (Sahifa {page + 1}):"
    await callback.message.edit_text(
        text,
        reply_markup=get_broker_leads_list_keyboard(
            page_leads, page, total_pages, "unassigned", lang
        ),
    )


# --- My Leads List ---


@broker_cabinet_router.callback_query(F.data.startswith("broker_cab:my:"))
async def handle_my_leads_list(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Display assigned leads list for this broker."""
    if not callback.data or not callback.message:
        await callback.answer()
        return

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer()
        return

    lang = user.language
    page = int(callback.data.split(":")[2])
    limit = 5
    offset = page * limit

    lead_service = LeadService()
    try:
        leads = await lead_service.list_my_leads(
            session,
            broker_user_id=user.id,
            limit=limit + 1,
            offset=offset,
        )
    except LeadPermissionError:
        await callback.answer(get_text("broker_permission_denied", lang), show_alert=True)
        return

    await callback.answer()

    if not leads and page == 0:
        await callback.message.edit_text(
            get_text("leads_empty_my", lang),
            reply_markup=get_broker_leads_list_keyboard([], 0, 0, "my", lang),
        )
        return

    has_more = len(leads) > limit
    page_leads = leads[:limit]
    total_pages = page + 2 if has_more else page + 1

    text = f"📋 <b>Mening leadlarim</b> (Sahifa {page + 1}):"
    await callback.message.edit_text(
        text,
        reply_markup=get_broker_leads_list_keyboard(page_leads, page, total_pages, "my", lang),
    )


# --- Tasks (Today & Overdue) ---


@broker_cabinet_router.callback_query(F.data.startswith("broker_cab:tasks_today:"))
async def handle_tasks_today_list(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Display tasks due today."""
    if not callback.data or not callback.message:
        await callback.answer()
        return

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer()
        return

    lang = user.language
    lead_service = LeadService()

    try:
        tasks = await lead_service.list_followups(
            session,
            broker_user_id=user.id,
            filter_type="today",
            limit=10,
        )
    except LeadPermissionError:
        await callback.answer(get_text("broker_permission_denied", lang), show_alert=True)
        return

    await callback.answer()

    if not tasks:
        await callback.message.edit_text(
            get_text("tasks_empty_today", lang),
            reply_markup=get_lead_history_back_keyboard(0, lang),
        )
        return

    await callback.message.edit_text("📅 <b>Bugungi vazifalar ro‘yxati:</b>")
    for t in tasks:
        card = format_followup_card(t, lang)
        await callback.message.answer(
            card,
            reply_markup=get_followup_actions_keyboard(t.id, t.lead_id, lang),
        )


@broker_cabinet_router.callback_query(F.data.startswith("broker_cab:tasks_overdue:"))
async def handle_tasks_overdue_list(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Display overdue tasks."""
    if not callback.data or not callback.message:
        await callback.answer()
        return

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer()
        return

    lang = user.language
    lead_service = LeadService()

    try:
        tasks = await lead_service.list_followups(
            session,
            broker_user_id=user.id,
            filter_type="overdue",
            limit=10,
        )
    except LeadPermissionError:
        await callback.answer(get_text("broker_permission_denied", lang), show_alert=True)
        return

    await callback.answer()

    if not tasks:
        await callback.message.edit_text(
            get_text("tasks_empty_overdue", lang),
            reply_markup=get_lead_history_back_keyboard(0, lang),
        )
        return

    await callback.message.edit_text("⏰ <b>Kechikkan vazifalar ro‘yxati:</b>")
    for t in tasks:
        card = format_followup_card(t, lang)
        await callback.message.answer(
            card,
            reply_markup=get_followup_actions_keyboard(t.id, t.lead_id, lang),
        )


# --- Broker Statistics ---


@broker_cabinet_router.callback_query(F.data == "broker_cab:stats")
async def handle_broker_stats(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Display aggregated statistics dashboard for broker."""
    if not callback.message:
        await callback.answer()
        return

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer()
        return

    lang = user.language
    lead_service = LeadService()

    try:
        stats = await lead_service.get_broker_stats(session, broker_user_id=user.id)
    except LeadPermissionError:
        await callback.answer(get_text("broker_permission_denied", lang), show_alert=True)
        return

    await callback.answer()

    stage_counts = stats["stage_counts"]
    lines = [
        get_text("lead_stats_title", lang),
        "",
        f"🔥 Yangi (erkin) leadlar: <b>{stats['unassigned_count']}</b>",
        f"📋 Mening faol leadlarim: <b>{stats['my_active_count']}</b>",
        f"📅 Bugungi vazifalar: <b>{stats['today_tasks_count']}</b>",
        f"⏰ Kechikkan vazifalar: <b>{stats['overdue_tasks_count']}</b>",
        "",
        "<b>Bosqichlar bo‘yicha:</b>",
        f"• {get_text('stage_new', lang)}: {stage_counts.get('new', 0)}",
        f"• {get_text('stage_contacted', lang)}: {stage_counts.get('contacted', 0)}",
        f"• {get_text('stage_qualified', lang)}: {stage_counts.get('qualified', 0)}",
        (
            f"• {get_text('stage_viewing_scheduled', lang)}: "
            f"{stage_counts.get('viewing_scheduled', 0)}"
        ),
        f"• {get_text('stage_negotiation', lang)}: {stage_counts.get('negotiation', 0)}",
        f"• {get_text('stage_won', lang)}: {stage_counts.get('won', 0)}",
        f"• {get_text('stage_lost', lang)}: {stage_counts.get('lost', 0)}",
    ]

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=get_lead_history_back_keyboard(0, lang),
    )


# --- Lead View & Card ---


@broker_cabinet_router.callback_query(F.data.startswith("lead_view:"))
async def handle_lead_view(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Display single lead card."""
    await state.clear()
    if not callback.data or not callback.message:
        await callback.answer()
        return

    lead_id = int(callback.data.split(":")[1])
    if lead_id == 0:
        # Back to cabinet
        await handle_broker_cabinet_home(callback, session, state)
        return

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer()
        return

    lang = user.language
    lead_service = LeadService()

    try:
        lead = await lead_service.get_lead(session, lead_id=lead_id, broker_user_id=user.id)
    except (LeadNotFoundError, LeadPermissionError) as e:
        await callback.answer(str(e), show_alert=True)
        return

    await callback.answer()

    is_assigned_to_me = lead.broker_user_id == user.id
    is_unassigned = lead.broker_user_id is None
    can_view_phone = await lead_service.can_view_customer_phone(
        session, lead=lead, requester_user_id=user.id
    )

    card_text = format_lead_card(
        lead,
        is_assigned_to_me=is_assigned_to_me,
        can_view_phone=can_view_phone,
        lang=lang,
    )
    kb = get_lead_card_keyboard(
        lead.id,
        lead.stage,
        is_assigned_to_me=is_assigned_to_me,
        is_unassigned=is_unassigned,
        lang=lang,
    )

    try:
        await callback.message.edit_text(card_text, reply_markup=kb)
    except TelegramBadRequest:
        await callback.message.answer(card_text, reply_markup=kb)


# --- Claim Lead ---


@broker_cabinet_router.callback_query(F.data.startswith("lead_act:claim:"))
async def handle_claim_lead(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Broker claims an unassigned lead."""
    if not callback.data or not callback.message:
        await callback.answer()
        return

    lead_id = int(callback.data.split(":")[2])
    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer()
        return

    lang = user.language
    lead_service = LeadService()

    try:
        await lead_service.claim_lead(session, lead_id=lead_id, broker_user_id=user.id)
        await callback.answer(get_text("lead_claimed_success", lang), show_alert=True)
    except (LeadNotFoundError, LeadPermissionError, LeadAlreadyAssignedError) as e:
        await callback.answer(str(e), show_alert=True)
        return

    # Refresh card view
    lead = await lead_service.get_lead(session, lead_id=lead_id, broker_user_id=user.id)
    can_view_phone = await lead_service.can_view_customer_phone(
        session, lead=lead, requester_user_id=user.id
    )
    card_text = format_lead_card(
        lead,
        is_assigned_to_me=True,
        can_view_phone=can_view_phone,
        lang=lang,
    )
    kb = get_lead_card_keyboard(
        lead.id,
        lead.stage,
        is_assigned_to_me=True,
        is_unassigned=False,
        lang=lang,
    )
    await callback.message.edit_text(card_text, reply_markup=kb)


# --- Stage Management ---


@broker_cabinet_router.callback_query(F.data.startswith("lead_act:stages:"))
async def handle_stage_selection_menu(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Show stage choice keyboard."""
    if not callback.data or not callback.message:
        await callback.answer()
        return

    lead_id = int(callback.data.split(":")[2])
    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer()
        return

    lang = user.language
    await callback.answer()
    await callback.message.edit_text(
        get_text("lead_stage_prompt", lang),
        reply_markup=get_lead_stage_choice_keyboard(lead_id, lang),
    )


@broker_cabinet_router.callback_query(F.data.startswith("lead_setstage:"))
async def handle_set_stage(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Set new lead stage."""
    if not callback.data or not callback.message:
        await callback.answer()
        return

    parts = callback.data.split(":")
    lead_id = int(parts[1])
    target_stage = parts[2]

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer()
        return

    lang = user.language
    lead_service = LeadService()

    if target_stage == "lost":
        await callback.answer()
        await callback.message.edit_text(
            get_text("lead_lost_reason_prompt", lang),
            reply_markup=get_lead_lost_reason_keyboard(lead_id, lang),
        )
        return

    try:
        updated = await lead_service.update_stage(
            session,
            lead_id=lead_id,
            broker_user_id=user.id,
            target_stage=target_stage,
        )
        stage_name = get_text(f"stage_{target_stage}", lang)
        await callback.answer(
            get_text("lead_stage_updated", lang).format(stage=stage_name),
            show_alert=True,
        )
    except (
        LeadNotFoundError,
        LeadPermissionError,
        InvalidLeadTransitionError,
        LeadValidationError,
    ) as e:
        await callback.answer(str(e), show_alert=True)
        return

    can_view_phone = await lead_service.can_view_customer_phone(
        session, lead=updated, requester_user_id=user.id
    )
    card_text = format_lead_card(
        updated,
        is_assigned_to_me=(updated.broker_user_id == user.id),
        can_view_phone=can_view_phone,
        lang=lang,
    )
    kb = get_lead_card_keyboard(
        updated.id,
        updated.stage,
        is_assigned_to_me=(updated.broker_user_id == user.id),
        is_unassigned=(updated.broker_user_id is None),
        lang=lang,
    )
    await callback.message.edit_text(card_text, reply_markup=kb)


@broker_cabinet_router.callback_query(F.data.startswith("lead_lost:"))
async def handle_lost_reason_selected(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Handle lost reason selection."""
    if not callback.data or not callback.message:
        await callback.answer()
        return

    parts = callback.data.split(":")
    lead_id = int(parts[1])
    reason = parts[2]

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer()
        return

    lang = user.language
    lead_service = LeadService()

    try:
        updated = await lead_service.update_stage(
            session,
            lead_id=lead_id,
            broker_user_id=user.id,
            target_stage="lost",
            close_reason=reason,
        )
        await callback.answer(
            get_text("lead_stage_updated", lang).format(stage=get_text("stage_lost", lang)),
            show_alert=True,
        )
    except (
        LeadNotFoundError,
        LeadPermissionError,
        InvalidLeadTransitionError,
        LeadValidationError,
    ) as e:
        await callback.answer(str(e), show_alert=True)
        return

    can_view_phone = await lead_service.can_view_customer_phone(
        session, lead=updated, requester_user_id=user.id
    )
    card_text = format_lead_card(
        updated,
        is_assigned_to_me=(updated.broker_user_id == user.id),
        can_view_phone=can_view_phone,
        lang=lang,
    )
    kb = get_lead_card_keyboard(
        updated.id,
        updated.stage,
        is_assigned_to_me=(updated.broker_user_id == user.id),
        is_unassigned=False,
        lang=lang,
    )
    await callback.message.edit_text(card_text, reply_markup=kb)


# --- Internal Notes ---


@broker_cabinet_router.callback_query(F.data.startswith("lead_act:add_note:"))
async def handle_start_add_note(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Prompt broker to input note text."""
    if not callback.data or not callback.message:
        await callback.answer()
        return

    lead_id = int(callback.data.split(":")[2])
    await state.set_state(BrokerCabinetStates.waiting_note_text)
    await state.update_data(lead_id=lead_id)

    await callback.answer()
    await callback.message.answer(get_text("lead_ask_note", "uz"))


@broker_cabinet_router.message(BrokerCabinetStates.waiting_note_text)
async def handle_save_note(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Save submitted note."""
    if not message.text or not message.from_user:
        return

    if message.text in MAIN_MENU_BUTTONS:
        await state.clear()
        return

    data = await state.get_data()
    lead_id = data.get("lead_id")
    await state.clear()

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, message.from_user.id)
    if not user or not lead_id:
        return

    lang = user.language
    lead_service = LeadService()

    try:
        await lead_service.add_note(
            session,
            lead_id=lead_id,
            author_user_id=user.id,
            text=message.text,
        )
        await message.answer(get_text("lead_note_saved", lang))
    except (LeadNotFoundError, LeadPermissionError, LeadValidationError) as e:
        await message.answer(str(e))
        return

    # Render lead card
    lead = await lead_service.get_lead(session, lead_id=lead_id, broker_user_id=user.id)
    can_view_phone = await lead_service.can_view_customer_phone(
        session, lead=lead, requester_user_id=user.id
    )
    card_text = format_lead_card(
        lead,
        is_assigned_to_me=(lead.broker_user_id == user.id),
        can_view_phone=can_view_phone,
        lang=lang,
    )
    kb = get_lead_card_keyboard(
        lead.id,
        lead.stage,
        is_assigned_to_me=(lead.broker_user_id == user.id),
        is_unassigned=False,
        lang=lang,
    )
    await message.answer(card_text, reply_markup=kb)


# --- Follow-Up Task Creation ---


@broker_cabinet_router.callback_query(F.data.startswith("lead_act:add_task:"))
async def handle_start_add_task(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Prompt broker to choose task type."""
    if not callback.data or not callback.message:
        await callback.answer()
        return

    lead_id = int(callback.data.split(":")[2])
    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer()
        return

    lang = user.language
    await callback.answer()
    await callback.message.edit_text(
        get_text("fu_ask_type", lang),
        reply_markup=get_followup_type_keyboard(lead_id, lang),
    )


@broker_cabinet_router.callback_query(F.data.startswith("fu_type:"))
async def handle_followup_type_selected(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Display time shortcuts after choosing task type."""
    if not callback.data or not callback.message:
        await callback.answer()
        return

    parts = callback.data.split(":")
    lead_id = int(parts[1])
    task_type = parts[2]

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer()
        return

    lang = user.language
    await callback.answer()
    await callback.message.edit_text(
        get_text("fu_ask_time", lang),
        reply_markup=get_followup_time_shortcuts_keyboard(lead_id, task_type, lang),
    )


@broker_cabinet_router.callback_query(F.data.startswith("fu_time:"))
async def handle_followup_time_selected(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Schedule follow-up task based on shortcut."""
    if not callback.data or not callback.message:
        await callback.answer()
        return

    parts = callback.data.split(":")
    lead_id = int(parts[1])
    task_type = parts[2]
    time_code = parts[3]

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer()
        return

    lang = user.language
    now = datetime.now(UTC)

    if time_code == "1h":
        due_at = now + timedelta(hours=1)
    elif time_code == "3h":
        due_at = now + timedelta(hours=3)
    elif time_code == "tomorrow_10":
        tomorrow = now + timedelta(days=1)
        # Tashkent is UTC+5, 10:00 local is 05:00 UTC
        due_at = tomorrow.replace(hour=5, minute=0, second=0, microsecond=0)
    elif time_code == "tomorrow_15":
        tomorrow = now + timedelta(days=1)
        # 15:00 local is 10:00 UTC
        due_at = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
    elif time_code == "2d":
        due_at = now + timedelta(days=2)
    else:
        due_at = now + timedelta(hours=2)

    lead_service = LeadService()
    try:
        fu = await lead_service.create_followup(
            session,
            lead_id=lead_id,
            broker_user_id=user.id,
            task_type=task_type,
            due_at=due_at,
        )
        due_str = fu.due_at.strftime("%d.%m.%Y %H:%M")
        await callback.answer(
            get_text("fu_created_success", lang).format(due_at=due_str),
            show_alert=True,
        )
    except (LeadNotFoundError, LeadPermissionError, LeadValidationError) as e:
        await callback.answer(str(e), show_alert=True)
        return

    # Return to lead card
    lead = await lead_service.get_lead(session, lead_id=lead_id, broker_user_id=user.id)
    can_view_phone = await lead_service.can_view_customer_phone(
        session, lead=lead, requester_user_id=user.id
    )
    card_text = format_lead_card(
        lead,
        is_assigned_to_me=(lead.broker_user_id == user.id),
        can_view_phone=can_view_phone,
        lang=lang,
    )
    kb = get_lead_card_keyboard(
        lead.id,
        lead.stage,
        is_assigned_to_me=(lead.broker_user_id == user.id),
        is_unassigned=False,
        lang=lang,
    )
    await callback.message.edit_text(card_text, reply_markup=kb)


# --- Follow-Up Task Actions (Complete / Cancel) ---


@broker_cabinet_router.callback_query(F.data.startswith("fu_act:done:"))
async def handle_complete_task(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Mark task completed."""
    if not callback.data or not callback.message:
        await callback.answer()
        return

    followup_id = int(callback.data.split(":")[2])
    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer()
        return

    lang = user.language
    lead_service = LeadService()

    try:
        await lead_service.complete_followup(
            session,
            followup_id=followup_id,
            broker_user_id=user.id,
        )
        await callback.answer(get_text("fu_completed_success", lang), show_alert=True)
        await callback.message.delete()
    except (FollowUpNotFoundError, LeadPermissionError) as e:
        await callback.answer(str(e), show_alert=True)


@broker_cabinet_router.callback_query(F.data.startswith("fu_act:cancel:"))
async def handle_cancel_task(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Cancel task."""
    if not callback.data or not callback.message:
        await callback.answer()
        return

    followup_id = int(callback.data.split(":")[2])
    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer()
        return

    lang = user.language
    lead_service = LeadService()

    try:
        await lead_service.cancel_followup(
            session,
            followup_id=followup_id,
            broker_user_id=user.id,
        )
        await callback.answer(get_text("fu_cancelled_success", lang), show_alert=True)
        await callback.message.delete()
    except (FollowUpNotFoundError, LeadPermissionError) as e:
        await callback.answer(str(e), show_alert=True)


# --- Lead History ---


@broker_cabinet_router.callback_query(F.data.startswith("lead_act:history:"))
async def handle_lead_history(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Display audit trail and history for a lead."""
    if not callback.data or not callback.message:
        await callback.answer()
        return

    lead_id = int(callback.data.split(":")[2])
    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, callback.from_user.id)
    if not user:
        await callback.answer()
        return

    lang = user.language
    lead_service = LeadService()

    try:
        lead = await lead_service.get_lead(session, lead_id=lead_id, broker_user_id=user.id)
    except (LeadNotFoundError, LeadPermissionError) as e:
        await callback.answer(str(e), show_alert=True)
        return

    await callback.answer()

    events = lead.events or []
    lines = [f"📜 <b>Lead #{lead.id} tarixi:</b>\n"]

    if not events:
        lines.append("<i>Tarix mavjud emas.</i>")
    else:
        for ev in events[:10]:
            t_str = ev.created_at.strftime("%d.%m.%Y %H:%M")
            actor = ev.actor.first_name if ev.actor else "Tizim"
            ev_desc = f"{ev.event_type} ({ev.old_value or ''} -> {ev.new_value or ''})"
            lines.append(f"• <b>{t_str}</b> | {actor}: {ev_desc}")

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=get_lead_history_back_keyboard(lead_id, lang),
    )
