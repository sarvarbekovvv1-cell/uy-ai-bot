"""Tests for Broker Cabinet and Lead Management Telegram handlers."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.broker_cabinet import (
    handle_broker_command,
    handle_claim_lead,
    handle_followup_time_selected,
    handle_lead_history,
    handle_lead_view,
    handle_lost_reason_selected,
    handle_save_note,
    handle_set_stage,
    handle_start_add_note,
    handle_tasks_today_list,
    handle_unassigned_leads_list,
)
from app.bot.states import BrokerCabinetStates
from app.models.property import Property
from app.models.user import User
from app.repositories.role_repository import RoleRepository
from app.services.lead_service import LeadService


@pytest.fixture
async def setup_cabinet_data(db_session: AsyncSession) -> dict[str, int]:
    """Seed users, roles, properties, and leads for handler testing."""
    role_repo = RoleRepository()
    await role_repo.ensure_default_roles(db_session)

    customer = User(
        telegram_id=800001,
        language="uz",
        first_name="Customer",
        phone="+998908000001",
        consent_accepted_at=datetime.now(UTC),
    )
    sales_broker = User(
        telegram_id=800002,
        language="uz",
        first_name="SalesBroker",
        phone="+998908000002",
        consent_accepted_at=datetime.now(UTC),
    )
    unauthorized_user = User(
        telegram_id=800003,
        language="uz",
        first_name="BuyerOnly",
        phone="+998908000003",
        consent_accepted_at=datetime.now(UTC),
    )
    db_session.add_all([customer, sales_broker, unauthorized_user])
    await db_session.flush()

    await role_repo.assign_role(db_session, customer.id, "buyer")
    await role_repo.assign_role(db_session, sales_broker.id, "sales_broker")
    await role_repo.assign_role(db_session, unauthorized_user.id, "buyer")

    prop = Property(
        owner_user_id=customer.id,
        listing_type="sale",
        property_type="apartment",
        title="Cabinet Test Apartment",
        region="Toshkent",
        district="Yakkasaroy",
        address="Shota Rustaveli 15",
        rooms=2,
        total_area=55.0,
        condition="euro",
        cadastre_status="available",
        price=60000.0,
        currency="USD",
        status="approved",
    )
    db_session.add(prop)
    await db_session.flush()

    # Create unassigned lead
    lead_service = LeadService()
    lead = await lead_service.create_lead(
        db_session,
        customer_user_id=customer.id,
        property_id=prop.id,
        source="broker_contact",
    )

    return {
        "customer_id": customer.id,
        "broker_id": sales_broker.id,
        "unauthorized_id": unauthorized_user.id,
        "customer_tg_id": customer.telegram_id,
        "broker_tg_id": sales_broker.telegram_id,
        "unauthorized_tg_id": unauthorized_user.telegram_id,
        "property_id": prop.id,
        "lead_id": lead.id,
    }


@pytest.mark.asyncio
async def test_broker_command_rbac(
    db_session: AsyncSession, setup_cabinet_data: dict[str, int]
) -> None:
    """Verify /broker authorization check."""
    broker_tg_id = setup_cabinet_data["broker_tg_id"]
    unauth_tg_id = setup_cabinet_data["unauthorized_tg_id"]

    # 1. Authorized broker
    msg_broker = AsyncMock(spec=Message)
    msg_broker.from_user = TgUser(id=broker_tg_id, is_bot=False, first_name="Broker")
    msg_broker.text = "/broker"
    msg_broker.answer = AsyncMock()

    await handle_broker_command(msg_broker, db_session)
    msg_broker.answer.assert_called_once()
    assert "Broker kabineti" in msg_broker.answer.call_args[0][0]

    # 2. Unauthorized buyer
    msg_unauth = AsyncMock(spec=Message)
    msg_unauth.from_user = TgUser(id=unauth_tg_id, is_bot=False, first_name="Buyer")
    msg_unauth.text = "/broker"
    msg_unauth.answer = AsyncMock()

    await handle_broker_command(msg_unauth, db_session)
    msg_unauth.answer.assert_called_once()
    assert "vakolati mavjud emas" in msg_unauth.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_cabinet_unassigned_leads_and_claim(
    db_session: AsyncSession, setup_cabinet_data: dict[str, int]
) -> None:
    """Verify listing unassigned leads, viewing a lead, and claiming it."""
    broker_tg_id = setup_cabinet_data["broker_tg_id"]
    lead_id = setup_cabinet_data["lead_id"]

    # 1. List unassigned leads
    cb_list = AsyncMock(spec=CallbackQuery)
    cb_list.from_user = TgUser(id=broker_tg_id, is_bot=False, first_name="Broker")
    cb_list.data = "broker_cab:unassigned:0"
    cb_list.message = AsyncMock(spec=Message)
    cb_list.message.edit_text = AsyncMock()
    cb_list.answer = AsyncMock()

    await handle_unassigned_leads_list(cb_list, db_session)
    cb_list.answer.assert_called_once()
    assert "Yangi (erkin) leadlar" in cb_list.message.edit_text.call_args[0][0]

    # 2. View single lead card
    storage = MemoryStorage()
    state = FSMContext(
        storage=storage,
        key=StorageKey(bot_id=1, chat_id=broker_tg_id, user_id=broker_tg_id),
    )
    cb_view = AsyncMock(spec=CallbackQuery)
    cb_view.from_user = TgUser(id=broker_tg_id, is_bot=False, first_name="Broker")
    cb_view.data = f"lead_view:{lead_id}"
    cb_view.message = AsyncMock(spec=Message)
    cb_view.message.edit_text = AsyncMock()
    cb_view.answer = AsyncMock()

    await handle_lead_view(cb_view, db_session, state)
    assert f"Lead #{lead_id}" in cb_view.message.edit_text.call_args[0][0]
    # Phone hidden before claiming
    assert "Biriktirilgach ko‘rinadi" in cb_view.message.edit_text.call_args[0][0]

    # 3. Claim lead
    cb_claim = AsyncMock(spec=CallbackQuery)
    cb_claim.from_user = TgUser(id=broker_tg_id, is_bot=False, first_name="Broker")
    cb_claim.data = f"lead_act:claim:{lead_id}"
    cb_claim.message = AsyncMock(spec=Message)
    cb_claim.message.edit_text = AsyncMock()
    cb_claim.answer = AsyncMock()

    await handle_claim_lead(cb_claim, db_session)
    # Phone now visible after claiming
    assert "+998908000001" in cb_claim.message.edit_text.call_args[0][0]


@pytest.mark.asyncio
async def test_lead_stage_and_lost_flow(
    db_session: AsyncSession, setup_cabinet_data: dict[str, int]
) -> None:
    """Verify changing stage and closing lead as lost with reason."""
    broker_tg_id = setup_cabinet_data["broker_tg_id"]
    lead_id = setup_cabinet_data["lead_id"]

    # 1. Claim lead first
    lead_service = LeadService()
    await lead_service.claim_lead(
        db_session, lead_id=lead_id, broker_user_id=setup_cabinet_data["broker_id"]
    )

    # 2. Set stage to contacted
    cb_stage = AsyncMock(spec=CallbackQuery)
    cb_stage.from_user = TgUser(id=broker_tg_id, is_bot=False, first_name="Broker")
    cb_stage.data = f"lead_setstage:{lead_id}:contacted"
    cb_stage.message = AsyncMock(spec=Message)
    cb_stage.message.edit_text = AsyncMock()
    cb_stage.answer = AsyncMock()

    await handle_set_stage(cb_stage, db_session)
    assert "Bog‘lanildi" in cb_stage.message.edit_text.call_args[0][0]

    # 3. Close as lost with reason
    cb_lost = AsyncMock(spec=CallbackQuery)
    cb_lost.from_user = TgUser(id=broker_tg_id, is_bot=False, first_name="Broker")
    cb_lost.data = f"lead_lost:{lead_id}:price"
    cb_lost.message = AsyncMock(spec=Message)
    cb_lost.message.edit_text = AsyncMock()
    cb_lost.answer = AsyncMock()

    await handle_lost_reason_selected(cb_lost, db_session)
    assert "Bekor qilindi" in cb_lost.message.edit_text.call_args[0][0]
    assert "Narx to‘g‘ri kelmadi" in cb_lost.message.edit_text.call_args[0][0]


@pytest.mark.asyncio
async def test_followup_and_notes_handlers(
    db_session: AsyncSession, setup_cabinet_data: dict[str, int]
) -> None:
    """Verify task scheduling, completion, and internal notes submission."""
    broker_tg_id = setup_cabinet_data["broker_tg_id"]
    lead_id = setup_cabinet_data["lead_id"]

    storage = MemoryStorage()
    state = FSMContext(
        storage=storage,
        key=StorageKey(bot_id=1, chat_id=broker_tg_id, user_id=broker_tg_id),
    )

    # Claim lead
    lead_service = LeadService()
    await lead_service.claim_lead(
        db_session, lead_id=lead_id, broker_user_id=setup_cabinet_data["broker_id"]
    )

    # 1. Schedule follow-up
    cb_fu = AsyncMock(spec=CallbackQuery)
    cb_fu.from_user = TgUser(id=broker_tg_id, is_bot=False, first_name="Broker")
    cb_fu.data = f"fu_time:{lead_id}:call:1h"
    cb_fu.message = AsyncMock(spec=Message)
    cb_fu.message.edit_text = AsyncMock()
    cb_fu.answer = AsyncMock()

    await handle_followup_time_selected(cb_fu, db_session)
    cb_fu.answer.assert_called_once()
    assert "muvaffaqiyatli rejalashtirildi" in cb_fu.answer.call_args[0][0]

    # 2. View today's tasks
    cb_today = AsyncMock(spec=CallbackQuery)
    cb_today.from_user = TgUser(id=broker_tg_id, is_bot=False, first_name="Broker")
    cb_today.data = "broker_cab:tasks_today:0"
    cb_today.message = AsyncMock(spec=Message)
    cb_today.message.edit_text = AsyncMock()
    cb_today.message.answer = AsyncMock()
    cb_today.answer = AsyncMock()

    await handle_tasks_today_list(cb_today, db_session)
    assert "Bugungi vazifalar ro‘yxati" in cb_today.message.edit_text.call_args[0][0]
    assert "Vazifa #" in cb_today.message.answer.call_args[0][0]

    # 3. Add note
    cb_note = AsyncMock(spec=CallbackQuery)
    cb_note.from_user = TgUser(id=broker_tg_id, is_bot=False, first_name="Broker")
    cb_note.data = f"lead_act:add_note:{lead_id}"
    cb_note.message = AsyncMock(spec=Message)
    cb_note.message.answer = AsyncMock()
    cb_note.answer = AsyncMock()

    await handle_start_add_note(cb_note, state)
    assert await state.get_state() == BrokerCabinetStates.waiting_note_text

    msg_note = AsyncMock(spec=Message)
    msg_note.from_user = TgUser(id=broker_tg_id, is_bot=False, first_name="Broker")
    msg_note.text = "Customer prefers morning calls only."
    msg_note.answer = AsyncMock()

    await handle_save_note(msg_note, db_session, state)
    assert await state.get_state() is None
    assert "Eslatma saqlandi" in msg_note.answer.call_args_list[0][0][0]

    # 4. View history
    cb_hist = AsyncMock(spec=CallbackQuery)
    cb_hist.from_user = TgUser(id=broker_tg_id, is_bot=False, first_name="Broker")
    cb_hist.data = f"lead_act:history:{lead_id}"
    cb_hist.message = AsyncMock(spec=Message)
    cb_hist.message.edit_text = AsyncMock()
    cb_hist.answer = AsyncMock()

    await handle_lead_history(cb_hist, db_session)
    assert "tarixi" in cb_hist.message.edit_text.call_args[0][0]
