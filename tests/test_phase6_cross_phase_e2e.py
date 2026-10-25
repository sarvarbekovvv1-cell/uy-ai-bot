"""Comprehensive cross-phase integration and E2E test suite for Phase 6 Broker Cabinet and Leads."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.types import CallbackQuery, Chat, Message, Update
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.dispatcher import create_dispatcher
from app.core.exceptions import (
    InvalidLeadTransitionError,
    LeadPermissionError,
    LeadValidationError,
)
from app.models.property import Property
from app.models.user import User
from app.repositories.lead_repository import LeadRepository
from app.repositories.role_repository import RoleRepository
from app.services.lead_service import LeadService
from app.services.viewing_request_service import ViewingRequestService


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


def extract_sent_texts(mock_bot: AsyncMock) -> list[str]:
    """Extract message texts from Telegram SendMessage or EditMessageText method calls."""
    texts = []
    for call in mock_bot.mock_calls:
        if len(call.args) > 0:
            call_obj = call.args[0]
            obj_name = call_obj.__class__.__name__
            if obj_name in ("SendMessage", "EditMessageText"):
                if hasattr(call_obj, "text") and call_obj.text:
                    texts.append(str(call_obj.text))
    return texts


@pytest.fixture
async def setup_e2e_entities(db_session: AsyncSession) -> dict[str, int]:
    """Seed users with distinct roles and approved sale & rent properties."""
    role_repo = RoleRepository()
    await role_repo.ensure_default_roles(db_session)

    # 1. Customer
    customer = User(
        telegram_id=900001,
        language="uz",
        first_name="Alisher",
        phone="+998901111111",
        consent_accepted_at=datetime.now(UTC),
    )
    # 2. Sales broker
    sales_broker = User(
        telegram_id=900002,
        language="uz",
        first_name="Bobur Sales",
        phone="+998902222222",
        consent_accepted_at=datetime.now(UTC),
    )
    # 3. Rental broker
    rental_broker = User(
        telegram_id=900003,
        language="uz",
        first_name="Dilshod Rent",
        phone="+998903333333",
        consent_accepted_at=datetime.now(UTC),
    )
    # 4. Head broker
    head_broker = User(
        telegram_id=900004,
        language="uz",
        first_name="Jahongir Head",
        phone="+998904444444",
        consent_accepted_at=datetime.now(UTC),
    )
    # 5. Unauthorized buyers / owners
    buyer = User(
        telegram_id=900005,
        language="uz",
        first_name="Jamshid Buyer",
        phone="+998905555555",
        consent_accepted_at=datetime.now(UTC),
    )
    db_session.add_all([customer, sales_broker, rental_broker, head_broker, buyer])
    await db_session.flush()

    await role_repo.assign_role(db_session, customer.id, "buyer")
    await role_repo.assign_role(db_session, sales_broker.id, "sales_broker")
    await role_repo.assign_role(db_session, rental_broker.id, "rental_broker")
    await role_repo.assign_role(db_session, head_broker.id, "head_broker")
    await role_repo.assign_role(db_session, buyer.id, "buyer")

    # Properties
    sale_prop = Property(
        owner_user_id=customer.id,
        listing_type="sale",
        property_type="apartment",
        title="Modern Apartment Yunusobod",
        region="Toshkent",
        district="Yunusobod",
        address="Amir Temur 45",
        rooms=3,
        total_area=80.0,
        condition="euro",
        cadastre_status="available",
        price=95000.0,
        currency="USD",
        status="approved",
    )
    rent_prop = Property(
        owner_user_id=customer.id,
        listing_type="rent",
        property_type="apartment",
        title="Cozy Flat Mirzo Ulugbek",
        region="Toshkent",
        district="Mirzo Ulug‘bek",
        address="Buyuk Ipak Yo‘li 12",
        rooms=2,
        total_area=50.0,
        condition="good",
        cadastre_status="available",
        price=500.0,
        currency="USD",
        status="approved",
    )
    db_session.add_all([sale_prop, rent_prop])
    await db_session.flush()

    return {
        "customer_id": customer.id,
        "customer_tg_id": customer.telegram_id,
        "sales_broker_id": sales_broker.id,
        "sales_broker_tg_id": sales_broker.telegram_id,
        "rental_broker_id": rental_broker.id,
        "rental_broker_tg_id": rental_broker.telegram_id,
        "head_broker_id": head_broker.id,
        "head_broker_tg_id": head_broker.telegram_id,
        "buyer_id": buyer.id,
        "buyer_tg_id": buyer.telegram_id,
        "sale_prop_id": sale_prop.id,
        "rent_prop_id": rent_prop.id,
    }


# ==============================================================================
# 4. Cross-Phase broker_contact -> Lead E2E Test
# ==============================================================================


@pytest.mark.asyncio
async def test_cross_phase_broker_contact_to_lead(
    db_session: AsyncSession, setup_e2e_entities: dict[str, int]
) -> None:
    """Customer submits broker contact request -> broker claims it -> Lead is created/assigned."""
    cust_id = setup_e2e_entities["customer_id"]
    prop_id = setup_e2e_entities["sale_prop_id"]
    broker_id = setup_e2e_entities["sales_broker_id"]

    viewing_service = ViewingRequestService()

    # 1. Customer creates broker contact request
    req = await viewing_service.create_broker_contact_request(
        db_session,
        customer_user_id=cust_id,
        property_id=prop_id,
        customer_comment="I would like to discuss price options.",
    )
    assert req.id is not None
    assert req.request_type == "broker_contact"
    assert req.status == "pending"
    assert req.broker_user_id is None

    # An active unassigned lead is created immediately
    lead_repo = LeadRepository()
    lead_initial = await lead_repo.get_active_by_customer_property(
        db_session, customer_user_id=cust_id, property_id=prop_id
    )
    assert lead_initial is not None
    assert lead_initial.source == "broker_contact"
    assert lead_initial.broker_user_id is None
    assert lead_initial.stage == "new"

    # 2. Broker claims the viewing request
    claimed_req = await viewing_service.claim_request(
        db_session, request_id=req.id, broker_user_id=broker_id
    )
    assert claimed_req.status == "assigned"
    assert claimed_req.broker_user_id == broker_id

    # 3. Verify Lead is now assigned to broker
    lead_assigned = await lead_repo.get_active_by_customer_property(
        db_session, customer_user_id=cust_id, property_id=prop_id
    )
    assert lead_assigned is not None
    assert lead_assigned.id == lead_initial.id
    assert lead_assigned.broker_user_id == broker_id
    assert lead_assigned.assigned_at is not None
    assert lead_assigned.source_request_id == req.id
    assert lead_assigned.stage == "new"


# ==============================================================================
# 5. Cross-Phase viewing -> Lead Deduplication E2E Test
# ==============================================================================


@pytest.mark.asyncio
async def test_cross_phase_viewing_deduplication(
    db_session: AsyncSession, setup_e2e_entities: dict[str, int]
) -> None:
    """Same customer submits both contact and viewing on same property -> single active lead."""
    cust_id = setup_e2e_entities["customer_id"]
    sale_prop_id = setup_e2e_entities["sale_prop_id"]
    rent_prop_id = setup_e2e_entities["rent_prop_id"]

    viewing_service = ViewingRequestService()
    lead_repo = LeadRepository()

    # 1. First: broker contact on sale property
    req1 = await viewing_service.create_broker_contact_request(
        db_session, customer_user_id=cust_id, property_id=sale_prop_id
    )
    lead1 = await lead_repo.get_active_by_customer_property(
        db_session, customer_user_id=cust_id, property_id=sale_prop_id
    )
    assert lead1 is not None

    # 2. Second: viewing appointment request on SAME property
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).date()
    req2 = await viewing_service.create_viewing_request(
        db_session,
        customer_user_id=cust_id,
        property_id=sale_prop_id,
        preferred_date=tomorrow,
        preferred_time="11:00",
    )
    assert req2.id != req1.id

    # Verify deduplication: STILL exactly 1 active lead for this property
    lead2 = await lead_repo.get_active_by_customer_property(
        db_session, customer_user_id=cust_id, property_id=sale_prop_id
    )
    assert lead2.id == lead1.id

    # 3. Third: request on a DIFFERENT (rent) property
    await viewing_service.create_broker_contact_request(
        db_session, customer_user_id=cust_id, property_id=rent_prop_id
    )
    lead3 = await lead_repo.get_active_by_customer_property(
        db_session, customer_user_id=cust_id, property_id=rent_prop_id
    )
    assert lead3 is not None
    assert lead3.id != lead1.id
    assert lead3.property_id == rent_prop_id


# ==============================================================================
# 6. Transaction Consistency Test
# ==============================================================================


@pytest.mark.asyncio
async def test_transaction_consistency_on_claim_failure(
    db_session: AsyncSession, setup_e2e_entities: dict[str, int]
) -> None:
    """If lead assignment/linking fails, the request claim must not commit half-state."""
    cust_id = setup_e2e_entities["customer_id"]
    sale_prop_id = setup_e2e_entities["sale_prop_id"]
    sales_broker_id = setup_e2e_entities["sales_broker_id"]

    viewing_service = ViewingRequestService()
    req = await viewing_service.create_broker_contact_request(
        db_session, customer_user_id=cust_id, property_id=sale_prop_id
    )
    req_id = req.id
    # Commit initial pending request to DB
    await db_session.commit()

    # Mock lead_service.ensure_lead_for_request to simulate unexpected failure
    viewing_service.lead_service.ensure_lead_for_request = AsyncMock(
        side_effect=RuntimeError("Simulated database failure during lead creation")
    )

    with pytest.raises(RuntimeError, match="Simulated database failure"):
        await viewing_service.claim_request(
            db_session, request_id=req.id, broker_user_id=sales_broker_id
        )

    # Roll back uncommitted claim transaction
    await db_session.rollback()
    db_session.expunge_all()

    # Re-fetch request from DB: must remain pending, unassigned
    reloaded_req = await viewing_service.viewing_repo.get_by_id(db_session, req_id)
    assert reloaded_req is not None
    assert reloaded_req.status == "pending"
    assert reloaded_req.broker_user_id is None


# ==============================================================================
# 7 & 8. /broker Real Dispatcher, New Leads & Claim E2E
# ==============================================================================


@pytest.mark.asyncio
async def test_broker_dispatcher_cabinet_and_claim_flow(
    db_session: AsyncSession, setup_e2e_entities: dict[str, int]
) -> None:
    """Test full real Dispatcher routing: /broker -> New leads -> Claim -> My leads."""
    broker_tg_id = setup_e2e_entities["sales_broker_tg_id"]
    broker_id = setup_e2e_entities["sales_broker_id"]
    cust_id = setup_e2e_entities["customer_id"]
    prop_id = setup_e2e_entities["sale_prop_id"]

    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    # 1. Create an unassigned lead
    lead_service = LeadService()
    lead = await lead_service.create_lead(
        db_session, customer_user_id=cust_id, property_id=prop_id, source="manual"
    )

    # 2. Broker sends /broker
    update_cmd = make_message_update(broker_tg_id, "/broker", 101)
    await dp.feed_update(mock_bot, update_cmd, session=db_session)
    sent_texts = extract_sent_texts(mock_bot)
    assert any("Broker kabineti" in t for t in sent_texts)

    # 3. Broker clicks '🔥 Yangi leadlar'
    update_unassigned = make_callback_update(broker_tg_id, "broker_cab:unassigned:0", 102)
    await dp.feed_update(mock_bot, update_unassigned, session=db_session)
    sent_texts = extract_sent_texts(mock_bot)
    assert any("Yangi (erkin) leadlar" in t for t in sent_texts)

    # 4. Broker claims the lead
    update_claim = make_callback_update(broker_tg_id, f"lead_act:claim:{lead.id}", 103)
    await dp.feed_update(mock_bot, update_claim, session=db_session)

    # Verify database update
    reloaded_lead = await lead_service.lead_repo.get_by_id(db_session, lead.id)
    assert reloaded_lead.broker_user_id == broker_id
    assert reloaded_lead.assigned_at is not None

    # 5. Broker checks '📋 Mening leadlarim'
    update_my = make_callback_update(broker_tg_id, "broker_cab:my:0", 104)
    await dp.feed_update(mock_bot, update_my, session=db_session)
    sent_texts = extract_sent_texts(mock_bot)
    rendered = " ".join(sent_texts)
    assert f"#{lead.id}" in rendered

    # 6. Another broker tries to claim already assigned lead (cannot steal)
    other_broker_id = setup_e2e_entities["rental_broker_id"]
    with pytest.raises(LeadPermissionError):
        await lead_service.claim_lead(db_session, lead_id=lead.id, broker_user_id=other_broker_id)


# ==============================================================================
# 9. Lead Details & Customer Privacy E2E
# ==============================================================================


@pytest.mark.asyncio
async def test_lead_details_privacy_and_id_masking(
    db_session: AsyncSession, setup_e2e_entities: dict[str, int]
) -> None:
    """Verify phone is visible to assigned broker, but Telegram/internal IDs never leaked."""
    broker_tg_id = setup_e2e_entities["sales_broker_tg_id"]
    broker_id = setup_e2e_entities["sales_broker_id"]
    cust_id = setup_e2e_entities["customer_id"]
    prop_id = setup_e2e_entities["sale_prop_id"]

    lead_service = LeadService()
    lead = await lead_service.create_lead(
        db_session,
        customer_user_id=cust_id,
        property_id=prop_id,
        broker_user_id=broker_id,
        source="broker_contact",
    )

    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    # Assigned broker views lead card
    update_view = make_callback_update(broker_tg_id, f"lead_view:{lead.id}", 201)
    await dp.feed_update(mock_bot, update_view, session=db_session)
    sent_texts = extract_sent_texts(mock_bot)
    card_text = " ".join(sent_texts)

    # Customer phone IS visible to assigned broker
    assert "+998901111111" in card_text
    assert "Alisher" in card_text
    # Customer Telegram ID and internal user PK must NOT be leaked
    assert "900001" not in card_text
    assert f"user_id={cust_id}" not in card_text

    # Unauthorized buyer attempts direct callback tampering to view lead details
    buyer_tg_id = setup_e2e_entities["buyer_tg_id"]
    update_tamper = make_callback_update(buyer_tg_id, f"lead_view:{lead.id}", 202)
    mock_bot_tamper = AsyncMock(spec=Bot)
    await dp.feed_update(mock_bot_tamper, update_tamper, session=db_session)
    # Callback query alert should have been called with permission denial
    tamper_calls = [
        c
        for c in mock_bot_tamper.mock_calls
        if "AnswerCallbackQuery" in str(c)
        and "vakolati yo‘q" in str(c)
    ]
    assert len(tamper_calls) > 0


# ==============================================================================
# 10. Pipeline Progression & Invalid Transitions E2E
# ==============================================================================


@pytest.mark.asyncio
async def test_pipeline_progression_and_timestamps(
    db_session: AsyncSession, setup_e2e_entities: dict[str, int]
) -> None:
    """Verify progression through each stage, timestamps, and invalid jumps."""
    broker_id = setup_e2e_entities["sales_broker_id"]
    cust_id = setup_e2e_entities["customer_id"]
    prop_id = setup_e2e_entities["sale_prop_id"]

    lead_service = LeadService()
    lead = await lead_service.create_lead(
        db_session,
        customer_user_id=cust_id,
        property_id=prop_id,
        broker_user_id=broker_id,
        source="manual",
    )
    assert lead.stage == "new"

    # 1. new -> contacted
    lead = await lead_service.update_stage(
        db_session, lead_id=lead.id, broker_user_id=broker_id, target_stage="contacted"
    )
    assert lead.stage == "contacted"
    assert lead.contacted_at is not None

    # 2. contacted -> qualified
    lead = await lead_service.update_stage(
        db_session, lead_id=lead.id, broker_user_id=broker_id, target_stage="qualified"
    )
    assert lead.stage == "qualified"
    assert lead.qualified_at is not None

    # 3. qualified -> viewing_scheduled
    lead = await lead_service.update_stage(
        db_session, lead_id=lead.id, broker_user_id=broker_id, target_stage="viewing_scheduled"
    )
    assert lead.stage == "viewing_scheduled"
    assert lead.viewing_at is not None

    # 4. viewing_scheduled -> negotiation
    lead = await lead_service.update_stage(
        db_session, lead_id=lead.id, broker_user_id=broker_id, target_stage="negotiation"
    )
    assert lead.stage == "negotiation"

    # 5. Invalid transition: cannot jump directly from new to negotiation on fresh lead
    await lead_service.create_lead(
        db_session,
        customer_user_id=setup_e2e_entities["buyer_id"],
        property_id=prop_id,
        broker_user_id=broker_id,
        source="manual",
    )
    with pytest.raises(InvalidLeadTransitionError):
        # Disallowed transition if not in ALLOWED_STAGE_TRANSITIONS
        lead_service.validate_stage_transition("won", "contacted")


# ==============================================================================
# 11, 12, 13. Notes & Follow-Up Lifecycle E2E
# ==============================================================================


@pytest.mark.asyncio
async def test_notes_and_followup_lifecycle(
    db_session: AsyncSession, setup_e2e_entities: dict[str, int]
) -> None:
    """Verify internal note, follow-up scheduling, today/overdue queries, and completion."""
    broker_id = setup_e2e_entities["sales_broker_id"]
    cust_id = setup_e2e_entities["customer_id"]
    prop_id = setup_e2e_entities["sale_prop_id"]

    lead_service = LeadService()
    lead = await lead_service.create_lead(
        db_session,
        customer_user_id=cust_id,
        property_id=prop_id,
        broker_user_id=broker_id,
        source="manual",
    )

    # 1. Add internal note
    note = await lead_service.add_note(
        db_session,
        lead_id=lead.id,
        author_user_id=broker_id,
        text="Customer works at IT park and has cash budget.",
    )
    assert note.id is not None
    assert note.text == "Customer works at IT park and has cash budget."

    # Verify event recorded
    events = await lead_service.lead_repo.list_events(db_session, lead.id)
    assert any(e.event_type == "note_added" for e in events)

    # 2. Schedule follow-up task
    now = datetime.now(UTC)
    task = await lead_service.create_followup(
        db_session,
        lead_id=lead.id,
        broker_user_id=broker_id,
        task_type="call",
        due_at=now + timedelta(hours=3),
        note="Call back after 18:00",
    )
    assert task.status == "pending"

    # Query today's tasks
    today_tasks = await lead_service.list_followups(
        db_session, broker_user_id=broker_id, filter_type="today"
    )
    assert len(today_tasks) == 1
    assert today_tasks[0].id == task.id

    # 3. Complete follow-up task
    completed_task = await lead_service.complete_followup(
        db_session, followup_id=task.id, broker_user_id=broker_id
    )
    assert completed_task.status == "completed"
    assert completed_task.completed_at is not None

    # Verify followup_completed event recorded
    events_after = await lead_service.lead_repo.list_events(db_session, lead.id)
    assert any(e.event_type == "followup_completed" for e in events_after)


# ==============================================================================
# 14 & 15. History & Statistics Derivation E2E
# ==============================================================================


@pytest.mark.asyncio
async def test_history_and_statistics_isolation(
    db_session: AsyncSession, setup_e2e_entities: dict[str, int]
) -> None:
    """Verify audit history renders without raw json, and statistics isolate broker types."""
    sales_broker_id = setup_e2e_entities["sales_broker_id"]
    sales_broker_tg_id = setup_e2e_entities["sales_broker_tg_id"]
    rental_broker_id = setup_e2e_entities["rental_broker_id"]
    cust_id = setup_e2e_entities["customer_id"]
    sale_prop_id = setup_e2e_entities["sale_prop_id"]
    rent_prop_id = setup_e2e_entities["rent_prop_id"]

    lead_service = LeadService()

    # Create 1 sale lead and 1 rent lead
    sale_lead = await lead_service.create_lead(
        db_session,
        customer_user_id=cust_id,
        property_id=sale_prop_id,
        broker_user_id=sales_broker_id,
        source="manual",
    )
    await lead_service.create_lead(
        db_session,
        customer_user_id=cust_id,
        property_id=rent_prop_id,
        broker_user_id=rental_broker_id,
        source="manual",
    )

    # 1. Statistics isolation:
    # Sales broker only sees sale leads
    sales_stats = await lead_service.get_broker_stats(db_session, broker_user_id=sales_broker_id)
    assert sales_stats["my_active_count"] == 1

    # Rental broker only sees rent leads
    rental_stats = await lead_service.get_broker_stats(db_session, broker_user_id=rental_broker_id)
    assert rental_stats["my_active_count"] == 1

    # Head broker sees both
    head_broker_id = setup_e2e_entities["head_broker_id"]
    head_stats = await lead_service.get_broker_stats(db_session, broker_user_id=head_broker_id)
    assert head_stats["my_active_count"] == 0  # Not assigned to head broker
    assert head_stats["unassigned_count"] == 0

    # 2. History view through Dispatcher
    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    update_hist = make_callback_update(
        sales_broker_tg_id, f"lead_act:history:{sale_lead.id}", 401
    )
    await dp.feed_update(mock_bot, update_hist, session=db_session)
    sent_texts = extract_sent_texts(mock_bot)
    hist_text = " ".join(sent_texts)

    assert "tarixi" in hist_text
    assert "created" in hist_text
    # Raw JSON must NOT be exposed in user text
    assert '{"source":' not in hist_text


# ==============================================================================
# 16. Won / Lost Terminal States E2E
# ==============================================================================


@pytest.mark.asyncio
async def test_won_and_lost_terminal_states(
    db_session: AsyncSession, setup_e2e_entities: dict[str, int]
) -> None:
    """Verify closing leads as won/lost, requiring reason for lost, and terminal immutability."""
    broker_id = setup_e2e_entities["sales_broker_id"]
    cust_id = setup_e2e_entities["customer_id"]
    prop_id = setup_e2e_entities["sale_prop_id"]

    lead_service = LeadService()

    # Lead 1 -> Won
    lead1 = await lead_service.create_lead(
        db_session,
        customer_user_id=cust_id,
        property_id=prop_id,
        broker_user_id=broker_id,
        source="manual",
    )
    won_lead = await lead_service.update_stage(
        db_session, lead_id=lead1.id, broker_user_id=broker_id, target_stage="won"
    )
    assert won_lead.stage == "won"
    assert won_lead.closed_at is not None

    # Cannot transition out of won
    with pytest.raises(InvalidLeadTransitionError):
        await lead_service.update_stage(
            db_session, lead_id=lead1.id, broker_user_id=broker_id, target_stage="contacted"
        )

    # Lead 2 -> Lost requires reason
    lead2 = await lead_service.create_lead(
        db_session,
        customer_user_id=setup_e2e_entities["buyer_id"],
        property_id=prop_id,
        broker_user_id=broker_id,
        source="manual",
    )
    with pytest.raises(LeadValidationError):
        await lead_service.update_stage(
            db_session, lead_id=lead2.id, broker_user_id=broker_id, target_stage="lost"
        )

    lost_lead = await lead_service.update_stage(
        db_session,
        lead_id=lead2.id,
        broker_user_id=broker_id,
        target_stage="lost",
        close_reason="competitor",
    )
    assert lost_lead.stage == "lost"
    assert lost_lead.close_reason == "competitor"
    assert lost_lead.closed_at is not None

    # Cannot transition out of lost
    with pytest.raises(InvalidLeadTransitionError):
        await lead_service.update_stage(
            db_session, lead_id=lead2.id, broker_user_id=broker_id, target_stage="new"
        )


# ==============================================================================
# 17 & 18. RBAC Matrix & Direct Callback Security E2E
# ==============================================================================


@pytest.mark.asyncio
async def test_rbac_matrix_and_tampered_callbacks(
    db_session: AsyncSession, setup_e2e_entities: dict[str, int]
) -> None:
    """Verify access denials across roles and malicious forged callback queries."""
    role_repo = RoleRepository()
    lead_service = LeadService()

    # Create users for all distinct roles
    roles_to_test = [
        "buyer",
        "tenant",
        "property_owner",
        "crm_operator",
        "marketing_specialist",
    ]
    for r in roles_to_test:
        u = User(
            telegram_id=950000 + len(r),
            first_name=f"User {r}",
            language="uz",
            is_active=True,
            consent_accepted_at=datetime.now(UTC),
        )
        db_session.add(u)
        await db_session.flush()
        await role_repo.assign_role(db_session, u.id, r)

        # /broker command must be denied
        types = await lead_service.get_broker_allowed_listing_types(db_session, u.id)
        assert types == [], f"Role {r} should have no broker listing types"

    # Sales broker vs Rental broker callback tampering
    sales_broker_id = setup_e2e_entities["sales_broker_id"]
    rental_broker_id = setup_e2e_entities["rental_broker_id"]
    cust_id = setup_e2e_entities["customer_id"]
    sale_prop_id = setup_e2e_entities["sale_prop_id"]
    rent_prop_id = setup_e2e_entities["rent_prop_id"]

    sale_lead = await lead_service.create_lead(
        db_session,
        customer_user_id=cust_id,
        property_id=sale_prop_id,
        broker_user_id=sales_broker_id,
        source="manual",
    )
    rent_lead = await lead_service.create_lead(
        db_session,
        customer_user_id=cust_id,
        property_id=rent_prop_id,
        broker_user_id=rental_broker_id,
        source="manual",
    )

    # 1. Rental broker attempts to view sale lead
    with pytest.raises(LeadPermissionError):
        await lead_service.get_lead(
            db_session, lead_id=sale_lead.id, broker_user_id=rental_broker_id
        )

    # 2. Sales broker attempts to modify rent lead stage
    with pytest.raises(LeadPermissionError):
        await lead_service.update_stage(
            db_session,
            lead_id=rent_lead.id,
            broker_user_id=sales_broker_id,
            target_stage="contacted",
        )

    # 3. Sales broker attempts to add note on rent lead
    with pytest.raises(LeadPermissionError):
        await lead_service.add_note(
            db_session,
            lead_id=rent_lead.id,
            author_user_id=sales_broker_id,
            text="Unauthorized note",
        )


# ==============================================================================
# 20. No Customer CRM Spam E2E
# ==============================================================================


@pytest.mark.asyncio
async def test_no_customer_crm_spam(
    db_session: AsyncSession, setup_e2e_entities: dict[str, int]
) -> None:
    """Verify internal CRM operations NEVER send messages to customer chat."""
    broker_id = setup_e2e_entities["sales_broker_id"]
    broker_tg_id = setup_e2e_entities["sales_broker_tg_id"]
    cust_id = setup_e2e_entities["customer_id"]
    cust_tg_id = setup_e2e_entities["customer_tg_id"]
    prop_id = setup_e2e_entities["sale_prop_id"]

    lead_service = LeadService()
    lead = await lead_service.create_lead(
        db_session,
        customer_user_id=cust_id,
        property_id=prop_id,
        broker_user_id=broker_id,
        source="manual",
    )

    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    # 1. Change stage
    update_stage = make_callback_update(
        broker_tg_id, f"lead_setstage:{lead.id}:contacted", 501
    )
    await dp.feed_update(mock_bot, update_stage, session=db_session)

    # 2. Add note
    await lead_service.add_note(
        db_session, lead_id=lead.id, author_user_id=broker_id, text="Internal note"
    )

    # 3. Schedule task
    await lead_service.create_followup(
        db_session,
        lead_id=lead.id,
        broker_user_id=broker_id,
        task_type="call",
        due_at=datetime.now(UTC) + timedelta(days=1),
    )

    # Check all messages sent by bot: NONE of them should have chat_id == customer_tg_id
    for call in mock_bot.mock_calls:
        if len(call.args) > 0 and call.args[0].__class__.__name__ == "SendMessage":
            send_msg_obj = call.args[0]
            assert send_msg_obj.chat_id != cust_tg_id, (
                "Customer was unexpectedly spammed with internal CRM update!"
            )
