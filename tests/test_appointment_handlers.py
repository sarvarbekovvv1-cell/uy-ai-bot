"""Tests for viewing request handlers, broker contact, appointments, and broker workflow."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Chat, Message, Update
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.dispatcher import create_dispatcher
from app.bot.handlers.appointments import (
    handle_broker_contact_confirm,
    handle_cancel_appointment_prompt,
    handle_confirm_cancel_appointment,
    handle_custom_date_input,
    handle_my_appointments,
    handle_start_viewing_wizard,
    handle_viewing_comment,
    handle_viewing_confirm,
    handle_viewing_date_choice,
    handle_viewing_time_choice,
)
from app.bot.handlers.broker_requests import (
    handle_broker_accept,
    handle_broker_claim,
    handle_broker_outcome_selected,
    handle_broker_reject_reason,
    handle_broker_reject_start,
    handle_viewing_requests_command,
)
from app.bot.locales import get_text
from app.bot.states import BrokerViewingStates, ViewingRequestStates
from app.models.property import Property
from app.models.user import User
from app.repositories.role_repository import RoleRepository
from app.repositories.viewing_request_repository import ViewingRequestRepository
from app.services.viewing_request_service import ViewingRequestService


@pytest.fixture
async def setup_users_and_prop(db_session: AsyncSession) -> dict[str, int]:
    """Seed real database users and approved properties for handler tests."""
    role_repo = RoleRepository()
    await role_repo.ensure_default_roles(db_session)

    # Customer
    customer = User(
        telegram_id=700001,
        language="uz",
        first_name="Customer",
        phone="+998907000001",
        consent_accepted_at=datetime.now(UTC),
    )
    # Sales broker
    broker = User(
        telegram_id=700002,
        language="uz",
        first_name="SalesBroker",
        phone="+998907000002",
        consent_accepted_at=datetime.now(UTC),
    )
    # Regular buyer (unauthorized broker)
    buyer = User(
        telegram_id=700003,
        language="uz",
        first_name="BuyerOnly",
        phone="+998907000003",
        consent_accepted_at=datetime.now(UTC),
    )
    db_session.add_all([customer, broker, buyer])
    await db_session.flush()

    await role_repo.assign_role(db_session, customer.id, "buyer")
    await role_repo.assign_role(db_session, broker.id, "sales_broker")
    await role_repo.assign_role(db_session, buyer.id, "buyer")

    prop = Property(
        owner_user_id=customer.id,
        listing_type="sale",
        property_type="apartment",
        title="Shinam Kvartira",
        region="Toshkent",
        district="Yunusobod",
        address="Amir Temur, 5",
        rooms=3,
        total_area=75.0,
        condition="euro",
        cadastre_status="available",
        price=85000,
        currency="USD",
        status="approved",
    )
    db_session.add(prop)
    await db_session.flush()

    return {
        "customer_id": customer.id,
        "customer_tg_id": customer.telegram_id,
        "broker_id": broker.id,
        "broker_tg_id": broker.telegram_id,
        "buyer_id": buyer.id,
        "buyer_tg_id": buyer.telegram_id,
        "property_id": prop.id,
    }


def make_message_update(user_id: int, text: str, update_id: int = 1) -> Update:
    """Create an Update with a Message for integration testing."""
    chat = Chat(id=user_id, type="private")
    from_user = TgUser(id=user_id, is_bot=False, first_name="Tester")
    msg = Message(
        message_id=update_id,
        date=datetime.now(UTC),
        chat=chat,
        from_user=from_user,
        text=text,
    )
    return Update(update_id=update_id, message=msg)


def make_callback_update(user_id: int, callback_data: str, update_id: int = 1) -> Update:
    """Create an Update with a CallbackQuery for integration testing."""
    from_user = TgUser(id=user_id, is_bot=False, first_name="Tester")
    chat = Chat(id=user_id, type="private")
    msg = Message(
        message_id=update_id,
        date=datetime.now(UTC),
        chat=chat,
        from_user=from_user,
        text="Original message",
    )
    cb = CallbackQuery(
        id=str(update_id),
        from_user=from_user,
        chat_instance="1",
        message=msg,
        data=callback_data,
    )
    return Update(update_id=update_id, callback_query=cb)


@pytest.mark.asyncio
async def test_viewing_wizard_e2e_flow(
    db_session: AsyncSession, setup_users_and_prop: dict[str, int]
) -> None:
    """Test full viewing request creation wizard."""
    prop_id = setup_users_and_prop["property_id"]
    cust_tg_id = setup_users_and_prop["customer_tg_id"]

    storage = MemoryStorage()
    key = StorageKey(bot_id=123, chat_id=cust_tg_id, user_id=cust_tg_id)
    state = FSMContext(storage=storage, key=key)

    # 1. Start wizard from property callback
    cb_start = AsyncMock(spec=CallbackQuery)
    cb_start.data = f"viewing:create:{prop_id}"
    cb_start.from_user = TgUser(id=cust_tg_id, is_bot=False, first_name="Cust")
    cb_start.message = AsyncMock(spec=Message)
    cb_start.message.reply = AsyncMock()
    cb_start.answer = AsyncMock()

    await handle_start_viewing_wizard(cb_start, state, db_session)
    assert await state.get_state() == ViewingRequestStates.choosing_date

    # 2. Choose tomorrow
    cb_date = AsyncMock(spec=CallbackQuery)
    cb_date.data = "view_date:tomorrow"
    cb_date.from_user = TgUser(id=cust_tg_id, is_bot=False, first_name="Cust")
    cb_date.message = AsyncMock(spec=Message)
    cb_date.message.edit_text = AsyncMock()
    cb_date.answer = AsyncMock()

    await handle_viewing_date_choice(cb_date, state)
    assert await state.get_state() == ViewingRequestStates.choosing_time

    # 3. Choose time 15:00
    cb_time = AsyncMock(spec=CallbackQuery)
    cb_time.data = "view_time:15:00"
    cb_time.from_user = TgUser(id=cust_tg_id, is_bot=False, first_name="Cust")
    cb_time.message = AsyncMock(spec=Message)
    cb_time.message.edit_text = AsyncMock()
    cb_time.answer = AsyncMock()

    await handle_viewing_time_choice(cb_time, state)
    assert await state.get_state() == ViewingRequestStates.waiting_comment

    # 4. Enter comment
    msg_comment = AsyncMock(spec=Message)
    msg_comment.text = "Iltimos, mulk egasi ham bo‘lsin"
    msg_comment.answer = AsyncMock()

    await handle_viewing_comment(msg_comment, state)
    assert await state.get_state() == ViewingRequestStates.confirming

    # 5. Confirm submission
    cb_confirm = AsyncMock(spec=CallbackQuery)
    cb_confirm.data = "view_confirm:yes"
    cb_confirm.from_user = TgUser(id=cust_tg_id, is_bot=False, first_name="Cust")
    cb_confirm.message = AsyncMock(spec=Message)
    cb_confirm.message.edit_text = AsyncMock()
    cb_confirm.answer = AsyncMock()

    await handle_viewing_confirm(cb_confirm, state, db_session)
    assert await state.get_state() is None

    # Verify request was created in DB
    viewing_repo = ViewingRequestRepository()
    reqs = await viewing_repo.list_by_customer(db_session, setup_users_and_prop["customer_id"])
    assert len(reqs) == 1
    req = reqs[0]
    assert req.property_id == prop_id
    assert req.request_type == "viewing"
    assert req.preferred_time == "15:00"
    assert req.customer_comment == "Iltimos, mulk egasi ham bo‘lsin"
    assert req.status == "pending"


@pytest.mark.asyncio
async def test_custom_date_input_validation(
    setup_users_and_prop: dict[str, int],
) -> None:
    """Test custom date input validation."""
    cust_tg_id = setup_users_and_prop["customer_tg_id"]
    storage = MemoryStorage()
    key = StorageKey(bot_id=123, chat_id=cust_tg_id, user_id=cust_tg_id)
    state = FSMContext(storage=storage, key=key)
    await state.set_state(ViewingRequestStates.waiting_custom_date)
    await state.update_data(language="uz")

    # 1. Malformed date
    msg_bad = AsyncMock(spec=Message)
    msg_bad.text = "not-a-date"
    msg_bad.answer = AsyncMock()
    await handle_custom_date_input(msg_bad, state)
    assert await state.get_state() == ViewingRequestStates.waiting_custom_date
    assert get_text("viewing_invalid_date", "uz") in msg_bad.answer.call_args[0][0]

    # 2. Past date
    msg_past = AsyncMock(spec=Message)
    msg_past.text = "01.01.2020"
    msg_past.answer = AsyncMock()
    await handle_custom_date_input(msg_past, state)
    assert await state.get_state() == ViewingRequestStates.waiting_custom_date

    # 3. Valid future date
    future_date = (datetime.now(UTC).date() + timedelta(days=5)).strftime("%d.%m.%Y")
    msg_valid = AsyncMock(spec=Message)
    msg_valid.text = future_date
    msg_valid.answer = AsyncMock()
    await handle_custom_date_input(msg_valid, state)
    assert await state.get_state() == ViewingRequestStates.choosing_time


@pytest.mark.asyncio
async def test_broker_contact_flow(
    db_session: AsyncSession, setup_users_and_prop: dict[str, int]
) -> None:
    """Test broker contact request creation."""
    prop_id = setup_users_and_prop["property_id"]
    cust_tg_id = setup_users_and_prop["customer_tg_id"]

    cb_confirm = AsyncMock(spec=CallbackQuery)
    cb_confirm.data = f"broker_contact:confirm:{prop_id}"
    cb_confirm.from_user = TgUser(id=cust_tg_id, is_bot=False, first_name="Cust")
    cb_confirm.message = AsyncMock(spec=Message)
    cb_confirm.message.edit_text = AsyncMock()
    cb_confirm.answer = AsyncMock()

    await handle_broker_contact_confirm(cb_confirm, db_session)

    # Verify created
    viewing_repo = ViewingRequestRepository()
    reqs = await viewing_repo.list_by_customer(db_session, setup_users_and_prop["customer_id"])
    assert any(r.request_type == "broker_contact" for r in reqs)


@pytest.mark.asyncio
async def test_my_appointments_and_cancellation(
    db_session: AsyncSession, setup_users_and_prop: dict[str, int]
) -> None:
    """Test viewing requests listing and cancellation from customer side."""
    prop_id = setup_users_and_prop["property_id"]
    cust_id = setup_users_and_prop["customer_id"]
    cust_tg_id = setup_users_and_prop["customer_tg_id"]

    service = ViewingRequestService()
    tomorrow = datetime.now(UTC).date() + timedelta(days=1)
    req = await service.create_viewing_request(
        db_session,
        customer_user_id=cust_id,
        property_id=prop_id,
        preferred_date=tomorrow,
        preferred_time="10:00",
    )

    # 1. List appointments
    msg = AsyncMock(spec=Message)
    msg.from_user = TgUser(id=cust_tg_id, is_bot=False, first_name="Cust")
    msg.answer = AsyncMock()

    await handle_my_appointments(msg, db_session)
    msg.answer.assert_awaited()
    # Check that appointment card was sent
    sent_card = msg.answer.call_args[0][0]
    assert f"So‘rov #{req.id}" in sent_card

    # 2. Cancellation prompt
    cb_cancel = AsyncMock(spec=CallbackQuery)
    cb_cancel.data = f"req:cancel:{req.id}"
    cb_cancel.from_user = TgUser(id=cust_tg_id, is_bot=False, first_name="Cust")
    cb_cancel.message = AsyncMock(spec=Message)
    cb_cancel.message.reply = AsyncMock()
    cb_cancel.answer = AsyncMock()

    await handle_cancel_appointment_prompt(cb_cancel, db_session)
    cb_cancel.message.reply.assert_awaited_once()

    # 3. Confirm cancellation
    cb_confirm = AsyncMock(spec=CallbackQuery)
    cb_confirm.data = f"req:cancel_confirm:{req.id}"
    cb_confirm.from_user = TgUser(id=cust_tg_id, is_bot=False, first_name="Cust")
    cb_confirm.message = AsyncMock(spec=Message)
    cb_confirm.message.edit_text = AsyncMock()
    cb_confirm.answer = AsyncMock()

    await handle_confirm_cancel_appointment(cb_confirm, db_session)
    cb_confirm.message.edit_text.assert_awaited_with(get_text("cancel_request_success", "uz"))


@pytest.mark.asyncio
async def test_broker_command_authorization_and_workflow(
    db_session: AsyncSession, setup_users_and_prop: dict[str, int]
) -> None:
    """Test broker /viewing_requests command, claim, accept, and complete."""
    prop_id = setup_users_and_prop["property_id"]
    cust_id = setup_users_and_prop["customer_id"]
    broker_tg_id = setup_users_and_prop["broker_tg_id"]
    buyer_tg_id = setup_users_and_prop["buyer_tg_id"]

    # 1. Unauthorized buyer denied
    msg_unauth = AsyncMock(spec=Message)
    msg_unauth.from_user = TgUser(id=buyer_tg_id, is_bot=False, first_name="Buyer")
    msg_unauth.answer = AsyncMock()

    await handle_viewing_requests_command(msg_unauth, db_session)
    assert get_text("broker_permission_denied", "uz") in msg_unauth.answer.call_args[0][0]

    # Create request
    service = ViewingRequestService()
    tomorrow = datetime.now(UTC).date() + timedelta(days=2)
    req = await service.create_viewing_request(
        db_session,
        customer_user_id=cust_id,
        property_id=prop_id,
        preferred_date=tomorrow,
        preferred_time="14:00",
    )

    # 2. Authorized sales_broker lists requests
    msg_broker = AsyncMock(spec=Message)
    msg_broker.from_user = TgUser(id=broker_tg_id, is_bot=False, first_name="Broker")
    msg_broker.answer = AsyncMock()

    await handle_viewing_requests_command(msg_broker, db_session)
    msg_broker.answer.assert_awaited()

    # 3. Claim request
    cb_claim = AsyncMock(spec=CallbackQuery)
    cb_claim.data = f"broker_req:claim:{req.id}"
    cb_claim.from_user = TgUser(id=broker_tg_id, is_bot=False, first_name="Broker")
    cb_claim.message = AsyncMock(spec=Message)
    cb_claim.message.edit_text = AsyncMock()
    cb_claim.answer = AsyncMock()

    await handle_broker_claim(cb_claim, db_session)
    cb_claim.message.edit_text.assert_awaited_once()

    # 4. Accept request
    mock_bot = AsyncMock(spec=Bot)
    mock_bot.send_message = AsyncMock()

    cb_accept = AsyncMock(spec=CallbackQuery)
    cb_accept.data = f"broker_req:accept:{req.id}"
    cb_accept.from_user = TgUser(id=broker_tg_id, is_bot=False, first_name="Broker")
    cb_accept.message = AsyncMock(spec=Message)
    cb_accept.message.edit_text = AsyncMock()
    cb_accept.answer = AsyncMock()
    cb_accept.bot = mock_bot

    await handle_broker_accept(cb_accept, db_session)
    cb_accept.message.edit_text.assert_awaited_once()
    # Verify customer received notification
    mock_bot.send_message.assert_awaited_once()
    assert "tasdiqlandi" in mock_bot.send_message.call_args.kwargs["text"]

    # 5. Complete request with outcome
    cb_outcome = AsyncMock(spec=CallbackQuery)
    cb_outcome.data = f"broker_out:interested:{req.id}"
    cb_outcome.from_user = TgUser(id=broker_tg_id, is_bot=False, first_name="Broker")
    cb_outcome.message = AsyncMock(spec=Message)
    cb_outcome.message.edit_text = AsyncMock()
    cb_outcome.answer = AsyncMock()
    cb_outcome.bot = mock_bot

    await handle_broker_outcome_selected(cb_outcome, db_session)
    cb_outcome.message.edit_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_broker_reject_with_reason_flow(
    db_session: AsyncSession, setup_users_and_prop: dict[str, int]
) -> None:
    """Test broker rejection flow with prompt, reason entry, and customer notification."""
    prop_id = setup_users_and_prop["property_id"]
    cust_id = setup_users_and_prop["customer_id"]
    broker_tg_id = setup_users_and_prop["broker_tg_id"]

    service = ViewingRequestService()
    tomorrow = datetime.now(UTC).date() + timedelta(days=2)
    req = await service.create_viewing_request(
        db_session,
        customer_user_id=cust_id,
        property_id=prop_id,
        preferred_date=tomorrow,
        preferred_time="16:00",
    )

    storage = MemoryStorage()
    key = StorageKey(bot_id=123, chat_id=broker_tg_id, user_id=broker_tg_id)
    state = FSMContext(storage=storage, key=key)

    # 1. Reject start prompt
    cb_reject = AsyncMock(spec=CallbackQuery)
    cb_reject.data = f"broker_req:reject:{req.id}"
    cb_reject.from_user = TgUser(id=broker_tg_id, is_bot=False, first_name="Broker")
    cb_reject.message = AsyncMock(spec=Message)
    cb_reject.message.reply = AsyncMock()
    cb_reject.answer = AsyncMock()

    await handle_broker_reject_start(cb_reject, state, db_session)
    assert await state.get_state() == BrokerViewingStates.waiting_rejection_reason

    # 2. Enter rejection reason
    mock_bot = AsyncMock(spec=Bot)
    mock_bot.send_message = AsyncMock()

    msg_reason = AsyncMock(spec=Message)
    msg_reason.text = "Ushbu vaqtda uy egasi shaharda bo‘lmaydi"
    msg_reason.from_user = TgUser(id=broker_tg_id, is_bot=False, first_name="Broker")
    msg_reason.answer = AsyncMock()
    msg_reason.bot = mock_bot

    await handle_broker_reject_reason(msg_reason, state, db_session)
    assert await state.get_state() is None
    msg_reason.answer.assert_awaited_with(get_text("broker_reject_success", "uz"))

    # Verify customer received notification with reason
    mock_bot.send_message.assert_awaited_once()
    assert "rad etildi" in mock_bot.send_message.call_args.kwargs["text"]
    assert "shaharda bo‘lmaydi" in mock_bot.send_message.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_dispatcher_appointments_routing(
    db_session: AsyncSession, setup_users_and_prop: dict[str, int]
) -> None:
    """Integration test verifying real dispatcher routing for '📅 Uchrashuvlarim'."""
    cust_tg_id = setup_users_and_prop["customer_tg_id"]
    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    update = make_message_update(cust_tg_id, "📅 Uchrashuvlarim", 201)
    await dp.feed_update(mock_bot, update, session=db_session)

    # Bot should have answered with appointments message
    assert len(mock_bot.mock_calls) > 0


@pytest.mark.asyncio
async def test_dispatcher_broker_contact_persistence_and_appointments(
    db_session: AsyncSession, setup_users_and_prop: dict[str, int]
) -> None:
    """Regression test: broker contact callback -> confirm -> DB row persisted -> Uchrashuvlarim."""
    cust_tg_id = setup_users_and_prop["customer_tg_id"]
    cust_id = setup_users_and_prop["customer_id"]
    prop_id = setup_users_and_prop["property_id"]

    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    # 1. User clicks confirm on broker contact prompt: broker_contact:confirm:<prop_id>
    update_confirm = make_callback_update(
        cust_tg_id, f"broker_contact:confirm:{prop_id}", update_id=301
    )
    await dp.feed_update(mock_bot, update_confirm, session=db_session)

    # 2. Verify row is actually persisted in database
    viewing_repo = ViewingRequestRepository()
    reqs = await viewing_repo.list_by_customer(db_session, cust_id)
    assert len(reqs) == 1
    req = reqs[0]
    assert req.request_type == "broker_contact"
    assert req.status == "pending"
    assert req.property_id == prop_id
    assert req.customer_user_id == cust_id
    assert req.preferred_date is None
    assert req.preferred_time is None
    assert req.id is not None
    assert req.id > 0

    # 3. User clicks "📅 Uchrashuvlarim" in main menu
    update_menu = make_message_update(cust_tg_id, "📅 Uchrashuvlarim", update_id=302)

    sent_texts: list[str] = []
    for call in mock_bot.mock_calls:
        if len(call.args) > 0 and call.args[0].__class__.__name__ == "SendMessage":
            sent_texts.append(str(call.args[0].text))

    await dp.feed_update(mock_bot, update_menu, session=db_session)

    new_sent_texts: list[str] = []
    for call in mock_bot.mock_calls:
        if len(call.args) > 0 and call.args[0].__class__.__name__ == "SendMessage":
            new_sent_texts.append(str(call.args[0].text))

    # Verify that the broker_contact request was rendered for customer
    rendered = " ".join(new_sent_texts)
    assert f"So‘rov #{req.id}" in rendered
    assert "Broker bilan bog‘lanish" in rendered
