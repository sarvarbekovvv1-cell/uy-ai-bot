"""Unit and integration tests for AmoCRMService, Transactional Outbox, and Crash Recovery."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.integrations.amocrm.constants import (
    EVENT_LEAD_CREATED,
    EVENT_STAGE_UPDATED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_PROCESSING,
)
from app.integrations.amocrm.provider import FakeAmoCRMProvider
from app.integrations.amocrm.service import AmoCRMService
from app.models.crm_sync import CRMSyncEvent
from app.models.lead import Lead
from app.models.property import Property
from app.models.user import User


@pytest.fixture
async def setup_test_entities(db_session: AsyncSession) -> tuple[User, Property, Lead]:
    """Create basic database entities for CRM testing."""
    customer = User(
        telegram_id=987654321,
        first_name="Akbar",
        last_name="Salimov",
        phone="+998901234567",
        language="uz",
        is_active=True,
    )
    db_session.add(customer)
    await db_session.flush()

    prop = Property(
        owner_user_id=customer.id,
        title="Yunusobod 3 xonali",
        description="Ajoyib joylashuv",
        property_type="apartment",
        listing_type="sale",
        region="Toshkent",
        district="Yunusobod",
        address="Yunusobod 4-mavze 15-uy",
        condition="renovated",
        rooms=3,
        total_area=Decimal("80.0"),
        price=Decimal("95000"),
        currency="USD",
        status="approved",
    )
    db_session.add(prop)
    await db_session.flush()

    lead = Lead(
        customer_user_id=customer.id,
        property_id=prop.id,
        source="broker_contact",
        stage="new",
    )
    db_session.add(lead)
    await db_session.commit()

    return customer, prop, lead


@pytest.mark.asyncio
async def test_outbox_transactional_enqueue(
    db_session: AsyncSession, setup_test_entities: tuple[User, Property, Lead]
) -> None:
    """Test outbox event enqueuing participates in database transaction."""
    _customer, _prop, lead = setup_test_entities
    settings = Settings(
        AMOCRM_ENABLED=True,
        AMOCRM_STAGE_MAPPING_JSON='{"new": 101, "contacted": 102}',
    )
    fake_provider = FakeAmoCRMProvider()
    service = AmoCRMService(settings=settings, provider=fake_provider)

    event = await service.enqueue_sync_event(
        db_session,
        event_type=EVENT_LEAD_CREATED,
        entity_type="lead",
        entity_id=lead.id,
    )
    await db_session.commit()

    assert event.id is not None
    assert event.status == STATUS_PENDING
    assert event.attempt_count == 0


@pytest.mark.asyncio
async def test_process_lead_created_outbox_event(
    db_session: AsyncSession, setup_test_entities: tuple[User, Property, Lead]
) -> None:
    """Test successful outbox processing creates Contact and Lead in amoCRM and links them."""
    customer, prop, lead = setup_test_entities
    settings = Settings(
        AMOCRM_ENABLED=True,
        AMOCRM_PIPELINE_ID=123,
        AMOCRM_STAGE_MAPPING_JSON='{"new": 101, "contacted": 102}',
    )
    fake_provider = FakeAmoCRMProvider()
    service = AmoCRMService(settings=settings, provider=fake_provider)

    # Enqueue and process
    await service.enqueue_sync_event(
        db_session,
        event_type=EVENT_LEAD_CREATED,
        entity_type="lead",
        entity_id=lead.id,
    )
    await db_session.commit()

    processed = await service.process_outbox_events(db_session, batch_size=10)
    assert processed == 1

    # Verify contact was created in fake amoCRM
    assert len(fake_provider.contacts) == 1
    contact = list(fake_provider.contacts.values())[0]
    assert contact["name"] == "Akbar Salimov"
    assert contact["phone"] == "+998901234567"

    # Verify lead was created in fake amoCRM
    assert len(fake_provider.leads) == 1
    remote_lead = list(fake_provider.leads.values())[0]
    assert "Yunusobod" in remote_lead["title"]
    assert remote_lead["price"] == 95000
    assert remote_lead["contact_id"] == contact["id"]

    # Verify entity links persisted
    user_link = await service.get_entity_link(
        db_session,
        local_entity_type="user",
        local_entity_id=customer.id,
        external_entity_type="contact",
    )
    assert user_link is not None
    assert user_link.external_entity_id == contact["id"]

    lead_link = await service.get_entity_link(
        db_session,
        local_entity_type="lead",
        local_entity_id=lead.id,
        external_entity_type="lead",
    )
    assert lead_link is not None
    assert lead_link.external_entity_id == remote_lead["id"]


@pytest.mark.asyncio
async def test_idempotent_duplicate_lead_creation_prevented(
    db_session: AsyncSession, setup_test_entities: tuple[User, Property, Lead]
) -> None:
    """Test re-processing lead_created event does NOT create duplicate amoCRM leads."""
    _customer, _prop, lead = setup_test_entities
    settings = Settings(
        AMOCRM_ENABLED=True,
        AMOCRM_STAGE_MAPPING_JSON='{"new": 101, "contacted": 102}',
    )
    fake_provider = FakeAmoCRMProvider()
    service = AmoCRMService(settings=settings, provider=fake_provider)

    # Enqueue first event and process
    await service.enqueue_sync_event(
        db_session, event_type=EVENT_LEAD_CREATED, entity_type="lead", entity_id=lead.id
    )
    await db_session.commit()
    await service.process_outbox_events(db_session)
    assert len(fake_provider.leads) == 1

    # Enqueue a second identical event for the same lead
    await service.enqueue_sync_event(
        db_session, event_type=EVENT_LEAD_CREATED, entity_type="lead", entity_id=lead.id
    )
    await db_session.commit()
    await service.process_outbox_events(db_session)

    # Must STILL be exactly 1 lead in amoCRM
    assert len(fake_provider.leads) == 1


@pytest.mark.asyncio
async def test_stage_updated_outbox_sync(
    db_session: AsyncSession, setup_test_entities: tuple[User, Property, Lead]
) -> None:
    """Test stage_updated event updates status on remote amoCRM lead."""
    _customer, _prop, lead = setup_test_entities
    settings = Settings(
        AMOCRM_ENABLED=True,
        AMOCRM_STAGE_MAPPING_JSON='{"new": 101, "contacted": 102, "negotiation": 105}',
    )
    fake_provider = FakeAmoCRMProvider()
    service = AmoCRMService(settings=settings, provider=fake_provider)

    # Initial sync
    await service.enqueue_sync_event(
        db_session, event_type=EVENT_LEAD_CREATED, entity_type="lead", entity_id=lead.id
    )
    await db_session.commit()
    await service.process_outbox_events(db_session)

    remote_lead = list(fake_provider.leads.values())[0]
    assert remote_lead["status_id"] == 101

    # Enqueue stage update to 'contacted'
    await service.enqueue_sync_event(
        db_session,
        event_type=EVENT_STAGE_UPDATED,
        entity_type="lead",
        entity_id=lead.id,
        payload={"target_stage": "contacted"},
    )
    await db_session.commit()
    await service.process_outbox_events(db_session)

    assert remote_lead["status_id"] == 102


@pytest.mark.asyncio
async def test_rate_limit_backoff(
    db_session: AsyncSession, setup_test_entities: tuple[User, Property, Lead]
) -> None:
    """Test 429 rate limit backs off next_attempt_at by retry_after."""
    _customer, _prop, lead = setup_test_entities
    settings = Settings(
        AMOCRM_ENABLED=True,
        AMOCRM_STAGE_MAPPING_JSON='{"new": 101, "contacted": 102}',
    )
    fake_provider = FakeAmoCRMProvider()
    fake_provider.simulate_429 = True
    fake_provider.simulate_429_retry_after = 75.0
    service = AmoCRMService(settings=settings, provider=fake_provider)

    event = await service.enqueue_sync_event(
        db_session, event_type=EVENT_LEAD_CREATED, entity_type="lead", entity_id=lead.id
    )
    await db_session.commit()

    processed = await service.process_outbox_events(db_session)
    assert processed == 0

    await db_session.refresh(event)
    assert event.status == STATUS_PENDING
    assert event.attempt_count == 1
    assert "RateLimit" in (event.last_error_safe or "")
    # Check backoff timestamp
    next_attempt = event.next_attempt_at
    now = (
        datetime.now(UTC)
        if next_attempt.tzinfo is not None
        else datetime.now(UTC).replace(tzinfo=None)
    )
    assert next_attempt > now + timedelta(seconds=60)


@pytest.mark.asyncio
async def test_transient_error_backoff_and_permanent_failure(
    db_session: AsyncSession, setup_test_entities: tuple[User, Property, Lead]
) -> None:
    """Test exponential retry for transient errors and permanent dead-letter after max attempts."""
    _customer, _prop, lead = setup_test_entities
    settings = Settings(
        AMOCRM_ENABLED=True,
        AMOCRM_MAX_RETRIES=2,
        AMOCRM_STAGE_MAPPING_JSON='{"new": 101}',
    )
    fake_provider = FakeAmoCRMProvider()
    fake_provider.simulate_500 = True
    service = AmoCRMService(settings=settings, provider=fake_provider)

    event = await service.enqueue_sync_event(
        db_session, event_type=EVENT_LEAD_CREATED, entity_type="lead", entity_id=lead.id
    )
    await db_session.commit()

    # Attempt 1: transient failure
    await service.process_outbox_events(db_session)
    await db_session.refresh(event)
    assert event.status == STATUS_PENDING
    assert event.attempt_count == 1

    # Force next attempt to be due
    event.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()

    # Attempt 2: hits max retries -> transitions to STATUS_FAILED
    await service.process_outbox_events(db_session)
    await db_session.refresh(event)
    assert event.status == STATUS_FAILED
    assert "PERMANENT_FAILURE" in (event.last_error_safe or "")


@pytest.mark.asyncio
async def test_stuck_event_recovery(
    db_session: AsyncSession, setup_test_entities: tuple[User, Property, Lead]
) -> None:
    """Test recovery of crashed worker events stuck in processing state."""
    _customer, _prop, lead = setup_test_entities
    settings = Settings(
        AMOCRM_ENABLED=True,
        AMOCRM_STAGE_MAPPING_JSON='{"new": 101, "contacted": 102}',
    )
    fake_provider = FakeAmoCRMProvider()
    service = AmoCRMService(settings=settings, provider=fake_provider)

    # Manually insert event stuck in 'processing' from 20 minutes ago
    event = CRMSyncEvent(
        provider="amocrm",
        event_type=EVENT_LEAD_CREATED,
        entity_type="lead",
        entity_id=lead.id,
        status=STATUS_PROCESSING,
        next_attempt_at=datetime.now(UTC) - timedelta(minutes=20),
    )
    db_session.add(event)
    await db_session.commit()

    recovered = await service.recover_stuck_events(db_session, timeout_minutes=10)
    assert recovered == 1

    await db_session.refresh(event)
    assert event.status == STATUS_PENDING
    assert "Recovered" in (event.last_error_safe or "")


@pytest.mark.asyncio
async def test_disabled_feature_flag_processes_zero(
    db_session: AsyncSession, setup_test_entities: tuple[User, Property, Lead]
) -> None:
    """Test AMOCRM_ENABLED=false does not process events or make requests."""
    _customer, _prop, lead = setup_test_entities
    settings = Settings(AMOCRM_ENABLED=False)
    fake_provider = FakeAmoCRMProvider()
    service = AmoCRMService(settings=settings, provider=fake_provider)

    event = CRMSyncEvent(
        provider="amocrm",
        event_type=EVENT_LEAD_CREATED,
        entity_type="lead",
        entity_id=lead.id,
        status=STATUS_PENDING,
        next_attempt_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    db_session.add(event)
    await db_session.commit()

    processed = await service.process_outbox_events(db_session)
    assert processed == 0
    assert len(fake_provider.leads) == 0


@pytest.mark.asyncio
async def test_unmapped_stage_fails_permanently_without_corrupting_lead(
    db_session: AsyncSession, setup_test_entities: tuple[User, Property, Lead]
) -> None:
    """Test unmapped intermediate stage triggers AmoCRMPermanentError and leaves Lead intact."""
    _customer, _prop, lead = setup_test_entities
    lead.stage = "qualified"  # Not mapped in settings
    await db_session.commit()

    # Settings only map 'new' and 'contacted'
    settings = Settings(
        AMOCRM_ENABLED=True,
        AMOCRM_STAGE_MAPPING_JSON='{"new": 101, "contacted": 102}',
    )
    fake_provider = FakeAmoCRMProvider()
    service = AmoCRMService(settings=settings, provider=fake_provider)

    event = await service.enqueue_sync_event(
        db_session,
        event_type=EVENT_LEAD_CREATED,
        entity_type="lead",
        entity_id=lead.id,
    )
    await db_session.commit()

    # Processing should permanently fail this event without retrying
    processed = await service.process_outbox_events(db_session)
    assert processed == 0

    await db_session.refresh(event)
    assert event.status == STATUS_FAILED
    expected_msg = "Missing amoCRM status_id mapping for stage: 'qualified'"
    assert expected_msg in (event.last_error_safe or "")

    # Crucial: local lead is completely intact and healthy
    await db_session.refresh(lead)
    assert lead.stage == "qualified"


@pytest.mark.asyncio
async def test_provider_reconciles_crash_window_idempotency(
    db_session: AsyncSession, setup_test_entities: tuple[User, Property, Lead]
) -> None:
    """Test crash recovery when remote lead exists in amoCRM but DB failed before link saved."""
    customer, prop, lead = setup_test_entities
    settings = Settings(
        AMOCRM_ENABLED=True,
        AMOCRM_STAGE_MAPPING_JSON='{"new": 101}',
    )
    fake_provider = FakeAmoCRMProvider()
    fake_provider.simulate_crash_on_lead_create = True
    service = AmoCRMService(settings=settings, provider=fake_provider)

    event = await service.enqueue_sync_event(
        db_session,
        event_type=EVENT_LEAD_CREATED,
        entity_type="lead",
        entity_id=lead.id,
    )
    await db_session.commit()

    # First attempt: crashes right after remote lead is registered in fake_provider.leads
    await service.process_outbox_events(db_session)
    await db_session.refresh(event)
    assert event.status == STATUS_PENDING
    assert event.attempt_count == 1
    assert len(fake_provider.leads) == 1

    # Local entity link does not exist yet due to simulated crash
    link = await service.get_entity_link(
        db_session,
        local_entity_type="lead",
        local_entity_id=lead.id,
        external_entity_type="lead",
    )
    assert link is None

    # Clear crash simulation and make event immediately due
    fake_provider.simulate_crash_on_lead_create = False
    event.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()

    # Second attempt: reconciles existing lead by title without creating a duplicate
    processed = await service.process_outbox_events(db_session)
    assert processed == 1

    await db_session.refresh(event)
    assert event.status == "succeeded"

    # Exactly 1 lead exists in amoCRM (no duplicate created!)
    assert len(fake_provider.leads) == 1

    # Entity link is now persisted properly
    link = await service.get_entity_link(
        db_session,
        local_entity_type="lead",
        local_entity_id=lead.id,
        external_entity_type="lead",
    )
    assert link is not None
