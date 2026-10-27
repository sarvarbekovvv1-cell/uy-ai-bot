"""Tests for restored 'Broker bilan bog‘lanish' menu flow and broker contact pipeline."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.types import Chat, Message, Update
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.dispatcher import create_dispatcher
from app.bot.locales import get_text
from app.models.property import Property
from app.models.user import User
from app.repositories.lead_repository import LeadRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.viewing_request_repository import ViewingRequestRepository


@pytest.fixture
async def setup_menu_data(db_session: AsyncSession) -> dict[str, int]:
    """Seed real customer, broker, and approved property for menu broker contact tests."""
    role_repo = RoleRepository()
    await role_repo.ensure_default_roles(db_session)

    customer = User(
        telegram_id=880001,
        language="uz",
        first_name="Ulugbek",
        phone="+998908800001",
        is_verified=True,
        consent_accepted_at=datetime.now(UTC),
    )
    broker = User(
        telegram_id=880002,
        language="uz",
        first_name="BrokerAkrom",
        phone="+998908800002",
        is_verified=True,
        consent_accepted_at=datetime.now(UTC),
    )
    unauthorized_user = User(
        telegram_id=880003,
        language="uz",
        first_name="OddiyMijoz",
        phone="+998908800003",
        is_verified=True,
        consent_accepted_at=datetime.now(UTC),
    )
    db_session.add_all([customer, broker, unauthorized_user])
    await db_session.flush()

    await role_repo.assign_role(db_session, customer.id, "buyer")
    await role_repo.assign_role(db_session, broker.id, "sales_broker")
    await role_repo.assign_role(db_session, unauthorized_user.id, "buyer")

    prop = Property(
        owner_user_id=customer.id,
        listing_type="sale",
        property_type="apartment",
        title="3 xonali apartment",
        region="Toshkent",
        district="Yunusobod",
        address="10-mavze 15-uy",
        rooms=3,
        total_area=50.0,
        condition="new",
        cadastre_status="available",
        price=50000,
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
        "unauth_id": unauthorized_user.id,
        "unauth_tg_id": unauthorized_user.telegram_id,
        "property_id": prop.id,
    }


def make_msg_update(user_id: int, text: str, update_id: int = 1) -> Update:
    chat = Chat(id=user_id, type="private")
    from_user = TgUser(id=user_id, is_bot=False, first_name="Ulugbek")
    msg = Message(
        message_id=update_id,
        date=datetime.now(UTC),
        chat=chat,
        from_user=from_user,
        text=text,
    )
    return Update(update_id=update_id, message=msg)


def make_cb_update(user_id: int, callback_data: str, update_id: int = 1) -> Update:
    from_user = TgUser(id=user_id, is_bot=False, first_name="Ulugbek")
    chat = Chat(id=user_id, type="private")
    msg = Message(
        message_id=update_id,
        date=datetime.now(UTC),
        chat=chat,
        from_user=from_user,
        text="inline action",
    )
    from aiogram.types import CallbackQuery

    cb = CallbackQuery(
        id=f"cb_{update_id}",
        from_user=from_user,
        chat_instance=f"ci_{update_id}",
        message=msg,
        data=callback_data,
    )
    return Update(update_id=update_id, callback_query=cb)


@pytest.mark.asyncio
async def test_menu_broker_contact_does_not_return_placeholder(
    db_session: AsyncSession, setup_menu_data: dict[str, int]
) -> None:
    """Ensure 'Broker bilan bog‘lanish' does NOT return 'keyingi bosqichda' placeholder."""
    cust_tg_id = setup_menu_data["customer_tg_id"]
    prop_id = setup_menu_data["property_id"]

    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    # User clicks '👨‍💼 Broker bilan bog‘lanish' in main menu
    update = make_msg_update(cust_tg_id, "👨‍💼 Broker bilan bog‘lanish", update_id=101)
    await dp.feed_update(mock_bot, update, session=db_session)

    # Collect answers from mock bot
    sent_texts: list[str] = []
    has_confirm_kb = False
    for call in mock_bot.mock_calls:
        if len(call.args) > 0 and call.args[0].__class__.__name__ == "SendMessage":
            sent_text = str(call.args[0].text)
            sent_texts.append(sent_text)
            reply_markup = getattr(call.args[0], "reply_markup", None)
            if reply_markup and hasattr(reply_markup, "inline_keyboard"):
                for row in reply_markup.inline_keyboard:
                    for btn in row:
                        if btn.callback_data == f"broker_contact:confirm:{prop_id}":
                            has_confirm_kb = True

    combined_text = " ".join(sent_texts)
    # MUST NOT be placeholder
    placeholder_text = get_text("feature_in_development", "uz")
    assert placeholder_text not in combined_text, "Returned placeholder instead of active flow!"
    # MUST contain property and broker contact prompt
    assert "broker bilan bog‘lanish so‘rovini yuborishni tasdiqlaysizmi" in combined_text.lower()
    assert has_confirm_kb, f"Missing confirmation inline keyboard for property #{prop_id}"


@pytest.mark.asyncio
async def test_full_broker_contact_persistence_and_crm_chain(
    db_session: AsyncSession, setup_menu_data: dict[str, int]
) -> None:
    """Menu button -> confirm -> ViewingRequest & Lead created -> appointments visible."""
    cust_tg_id = setup_menu_data["customer_tg_id"]
    cust_id = setup_menu_data["customer_id"]
    prop_id = setup_menu_data["property_id"]

    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    # 1. Menu click
    update_menu = make_msg_update(cust_tg_id, "👨‍💼 Broker bilan bog‘lanish", update_id=201)
    await dp.feed_update(mock_bot, update_menu, session=db_session)

    # 2. Confirm callback
    update_confirm = make_cb_update(cust_tg_id, f"broker_contact:confirm:{prop_id}", update_id=202)
    await dp.feed_update(mock_bot, update_confirm, session=db_session)

    # 3. Verify ViewingRequest persisted
    viewing_repo = ViewingRequestRepository()
    reqs = await viewing_repo.list_by_customer(db_session, cust_id)
    assert len(reqs) == 1
    req = reqs[0]
    assert req.request_type == "broker_contact"
    assert req.status == "pending"
    assert req.property_id == prop_id
    assert req.customer_user_id == cust_id

    # 4. Verify Lead persisted with source=broker_contact
    lead_repo = LeadRepository()
    lead = await lead_repo.get_active_by_customer_property(
        db_session, customer_user_id=cust_id, property_id=prop_id
    )
    assert lead is not None
    assert lead.source == "broker_contact"
    assert lead.stage == "new"
    assert lead.source_request_id == req.id

    # 5. Check '📅 Uchrashuvlarim'
    update_appts = make_msg_update(cust_tg_id, "📅 Uchrashuvlarim", update_id=203)
    await dp.feed_update(mock_bot, update_appts, session=db_session)

    sent_texts: list[str] = []
    for call in mock_bot.mock_calls:
        if len(call.args) > 0 and call.args[0].__class__.__name__ == "SendMessage":
            sent_texts.append(str(call.args[0].text))

    combined = " ".join(sent_texts)
    assert f"So‘rov #{req.id}" in combined
    assert "Broker bilan bog‘lanish" in combined
    assert "Kutilmoqda" in combined


@pytest.mark.asyncio
async def test_ai_broker_contact_callback_handled_seamlessly(
    db_session: AsyncSession, setup_menu_data: dict[str, int]
) -> None:
    """Verify callback from AI broker (contact_broker:<prop_id>) is handled by prompt."""
    cust_tg_id = setup_menu_data["customer_tg_id"]
    prop_id = setup_menu_data["property_id"]

    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    # AI broker callback: contact_broker:<prop_id>
    update = make_cb_update(cust_tg_id, f"contact_broker:{prop_id}", update_id=301)
    await dp.feed_update(mock_bot, update, session=db_session)

    # Check that confirmation prompt was sent
    sent_texts: list[str] = []
    for call in mock_bot.mock_calls:
        if len(call.args) > 0 and call.args[0].__class__.__name__ == "SendMessage":
            sent_texts.append(str(call.args[0].text))

    combined = " ".join(sent_texts)
    assert "broker bilan bog‘lanish so‘rovini yuborishni tasdiqlaysizmi" in combined.lower()


@pytest.mark.asyncio
async def test_duplicate_broker_contact_protection(
    db_session: AsyncSession, setup_menu_data: dict[str, int]
) -> None:
    """Duplicate active broker_contact requests for the same property must be prevented."""
    cust_tg_id = setup_menu_data["customer_tg_id"]
    cust_id = setup_menu_data["customer_id"]
    prop_id = setup_menu_data["property_id"]

    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    # First confirmation
    u1 = make_cb_update(cust_tg_id, f"broker_contact:confirm:{prop_id}", update_id=401)
    await dp.feed_update(mock_bot, u1, session=db_session)

    # Second confirmation attempt
    u2 = make_cb_update(cust_tg_id, f"broker_contact:confirm:{prop_id}", update_id=402)
    await dp.feed_update(mock_bot, u2, session=db_session)

    # Verify only 1 record created
    viewing_repo = ViewingRequestRepository()
    reqs = await viewing_repo.list_by_customer(db_session, cust_id)
    assert len(reqs) == 1


@pytest.mark.asyncio
async def test_rbac_unauthorized_customer_cannot_access_staff_broker_requests(
    db_session: AsyncSession, setup_menu_data: dict[str, int]
) -> None:
    """Unauthorized customer must be denied access to broker viewing/contact requests."""
    unauth_tg_id = setup_menu_data["unauth_tg_id"]

    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    update = make_msg_update(unauth_tg_id, "/viewing_requests", update_id=501)
    await dp.feed_update(mock_bot, update, session=db_session)

    sent_texts: list[str] = []
    for call in mock_bot.mock_calls:
        if len(call.args) > 0 and call.args[0].__class__.__name__ == "SendMessage":
            sent_texts.append(str(call.args[0].text))

    combined = " ".join(sent_texts)
    denied_msg = get_text("broker_permission_denied", "uz")
    assert denied_msg in combined
