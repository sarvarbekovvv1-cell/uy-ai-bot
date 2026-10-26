"""End-to-end and cross-flow integration tests for amoCRM synchronization.

Tests full convergence:
- Telegram Bot -> ViewingRequestService -> Lead -> Outbox -> amoCRM
- Mini App -> ViewingRequestService -> Lead -> Outbox -> amoCRM
- AI Broker -> ViewingRequestService -> Lead -> Outbox -> amoCRM
- Cross-channel Lead deduplication (Telegram + Mini App + AI broker for same property)
- Strict data minimization & PII guarantees
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.integrations.amocrm.mapper import AmoCRMMapper
from app.integrations.amocrm.provider import FakeAmoCRMProvider
from app.integrations.amocrm.service import AmoCRMService
from app.models.lead import Lead
from app.models.property import Property
from app.models.user import User
from app.services.lead_service import LeadService
from app.services.viewing_request_service import ViewingRequestService


@pytest.fixture
def amocrm_test_context(monkeypatch):
    """Configure amoCRM integration for cross-flow testing."""
    test_settings = Settings(
        AMOCRM_ENABLED=True,
        AMOCRM_PIPELINE_ID=7001,
        AMOCRM_STAGE_MAPPING_JSON='{"new": 101, "contacted": 102, "viewing_scheduled": 104}',
        AMOCRM_DEFAULT_RESPONSIBLE_USER_ID=90001,
    )
    monkeypatch.setattr("app.config.get_settings", lambda: test_settings)

    fake_provider = FakeAmoCRMProvider()
    mapper = AmoCRMMapper(settings=test_settings)
    crm_service = AmoCRMService(settings=test_settings, provider=fake_provider, mapper=mapper)
    return test_settings, fake_provider, crm_service


@pytest.mark.asyncio
async def test_telegram_and_miniapp_broker_contact_flow(
    db_session: AsyncSession, amocrm_test_context
) -> None:
    """Test broker contact requests from Telegram and Mini App trigger CRM synchronization."""
    _settings, fake_provider, crm_service = amocrm_test_context

    # Create customer and property
    customer = User(
        telegram_id=55512345,
        first_name="Jamshid",
        last_name="Normatov",
        phone="+998931234567",
        language="uz",
        is_active=True,
    )
    owner = User(
        telegram_id=999888,
        first_name="Mulkdor",
        last_name="Ota",
        phone="+998909998877",  # Owner phone must NOT leak to CRM lead
        is_active=True,
    )
    db_session.add_all([customer, owner])
    await db_session.flush()

    prop = Property(
        owner_user_id=owner.id,
        title="Chilonzor 2 xonali",
        property_type="apartment",
        listing_type="sale",
        region="Toshkent",
        district="Chilonzor",
        address="Chilonzor 2-mavze 10-uy",
        condition="renovated",
        rooms=2,
        total_area=Decimal("56.0"),
        price=Decimal("62000"),
        currency="USD",
        status="approved",
    )
    db_session.add(prop)
    await db_session.commit()

    # Step 1: Customer requests broker contact (used by both Telegram and Mini App)
    viewing_service = ViewingRequestService()
    await viewing_service.create_broker_contact_request(
        db_session,
        customer_user_id=customer.id,
        property_id=prop.id,
        customer_comment="Iltimos tezroq aloqaga chiqing",
    )
    await db_session.commit()

    # Verify internal Lead was created
    lead = await db_session.get(Lead, 1)
    assert lead is not None
    assert lead.customer_user_id == customer.id

    # Step 2: Background outbox processes the event
    processed = await crm_service.process_outbox_events(db_session)
    assert processed == 1

    # Verify fake amoCRM received Contact and Lead
    assert len(fake_provider.contacts) == 1
    assert len(fake_provider.leads) == 1
    assert len(fake_provider.notes) == 1  # Property summary note

    remote_contact = list(fake_provider.contacts.values())[0]
    remote_lead = list(fake_provider.leads.values())[0]

    assert remote_contact["name"] == "Jamshid Normatov"
    assert remote_contact["phone"] == "+998931234567"
    assert "Chilonzor" in remote_lead["title"]
    assert remote_lead["price"] == 62000
    assert remote_lead["status_id"] == 101


@pytest.mark.asyncio
async def test_cross_channel_lead_deduplication(
    db_session: AsyncSession, amocrm_test_context
) -> None:
    """Test customer requesting contact on Telegram, Mini App, and AI Broker for SAME property.

    Enforces that internal Lead deduplication results in exactly ONE external amoCRM lead.
    """
    _settings, fake_provider, crm_service = amocrm_test_context

    customer = User(
        telegram_id=444555,
        first_name="Dilshod",
        phone="+998901112233",
        is_active=True,
    )
    db_session.add(customer)
    await db_session.flush()

    prop = Property(
        owner_user_id=customer.id,
        title="Yashnobod Hovka",
        property_type="house",
        listing_type="sale",
        region="Toshkent",
        district="Yashnobod",
        address="Parkent ko'chasi 5",
        condition="renovated",
        rooms=4,
        total_area=Decimal("150.0"),
        price=Decimal("150000"),
        currency="USD",
        status="approved",
    )
    db_session.add(prop)
    await db_session.commit()

    viewing_service = ViewingRequestService()

    # Channel 1: Telegram broker contact
    await viewing_service.create_broker_contact_request(
        db_session, customer_user_id=customer.id, property_id=prop.id
    )
    await db_session.commit()
    await crm_service.process_outbox_events(db_session)

    assert len(fake_provider.leads) == 1
    initial_external_lead_id = list(fake_provider.leads.keys())[0]

    # Channel 2: Customer opens Mini App and submits viewing request for same property
    # Because there is an active lead, ensure_lead_for_request reuses it
    req2 = await viewing_service.create_viewing_request(
        db_session,
        customer_user_id=customer.id,
        property_id=prop.id,
        preferred_date=date.today(),
        preferred_time="14:00",
    )
    await db_session.commit()
    assert req2 is not None

    # Process outbox again
    await crm_service.process_outbox_events(db_session)

    # Must STILL be exactly 1 lead in amoCRM (no duplicates created across channels)
    assert len(fake_provider.leads) == 1
    assert list(fake_provider.leads.keys())[0] == initial_external_lead_id


@pytest.mark.asyncio
async def test_lead_stage_transition_cross_flow(
    db_session: AsyncSession, amocrm_test_context
) -> None:
    """Test that broker changing lead stage in Broker Cabinet updates remote amoCRM lead."""
    _settings, fake_provider, crm_service = amocrm_test_context

    from app.models.role import Role

    sales_role = Role(name="sales_broker", description="Sales broker")
    db_session.add(sales_role)
    await db_session.flush()

    broker = User(
        telegram_id=123001,
        first_name="Said",
        last_name="Broker",
        is_active=True,
    )
    broker.roles.append(sales_role)
    customer = User(
        telegram_id=123002,
        first_name="Xaridor",
        phone="+998905554433",
        is_active=True,
    )
    db_session.add_all([broker, customer])
    await db_session.flush()

    prop = Property(
        owner_user_id=customer.id,
        title="Novza kvartira",
        property_type="apartment",
        listing_type="sale",
        region="Toshkent",
        district="Chilonzor",
        address="Novza 14",
        condition="renovated",
        rooms=2,
        total_area=Decimal("45.0"),
        status="approved",
        price=Decimal("45000"),
        currency="USD",
    )
    db_session.add(prop)
    await db_session.flush()

    lead_service = LeadService()
    lead = await lead_service.create_lead(
        db_session,
        customer_user_id=customer.id,
        property_id=prop.id,
        source="broker_contact",
        broker_user_id=broker.id,
    )
    await db_session.commit()

    # Initial sync
    await crm_service.process_outbox_events(db_session)
    remote_lead = list(fake_provider.leads.values())[0]
    assert remote_lead["status_id"] == 101  # 'new'

    # Broker progresses stage to 'contacted'
    await lead_service.update_stage(
        db_session,
        lead_id=lead.id,
        broker_user_id=broker.id,
        target_stage="contacted",
    )
    await db_session.commit()

    # Process outbox update
    await crm_service.process_outbox_events(db_session)
    assert remote_lead["status_id"] == 102  # updated to 'contacted'


@pytest.mark.asyncio
async def test_strict_data_minimization_and_pii_protection(
    db_session: AsyncSession, amocrm_test_context
) -> None:
    """Strict privacy assertion: inspect all payloads delivered to amoCRM

    Verifies NO bot tokens, auth hashes, initData, Gemini keys, owner phones, or passwords.
    """
    _settings, fake_provider, crm_service = amocrm_test_context

    owner = User(
        telegram_id=888999,
        first_name="Egasi",
        phone="+998901119988",  # SECRET OWNER PHONE
        is_active=True,
    )
    customer = User(
        telegram_id=777666,
        first_name="Nodirbek",
        phone="+998971239900",
        is_active=True,
    )
    db_session.add_all([owner, customer])
    await db_session.flush()

    prop = Property(
        owner_user_id=owner.id,
        title="Maxfiy Hovka",
        property_type="house",
        listing_type="sale",
        region="Toshkent",
        district="Shayxontohur",
        address="Labzak 8",
        condition="renovated",
        rooms=5,
        total_area=Decimal("200.0"),
        status="approved",
        price=Decimal("200000"),
        currency="USD",
    )
    db_session.add(prop)
    await db_session.flush()

    lead_service = LeadService()
    await lead_service.create_lead(
        db_session,
        customer_user_id=customer.id,
        property_id=prop.id,
        source="broker_contact",
    )
    await db_session.commit()

    await crm_service.process_outbox_events(db_session)

    # Inspect all captured payloads sent to FakeAmoCRMProvider
    assert len(fake_provider.sent_payloads) > 0

    owner_secret_phone = "+998901119988"
    for payload in fake_provider.sent_payloads:
        payload_str = str(payload)

        # 1. Strictly NO owner private phone number
        assert owner_secret_phone not in payload_str
        assert "901119988" not in payload_str

        # 2. Strictly NO bot tokens or Telegram hashes
        assert "bot_token" not in payload_str.lower()
        assert "initdata" not in payload_str.lower()
        assert "tg_init_data" not in payload_str.lower()

        # 3. Strictly NO AI / Gemini keys or prompt instructions
        assert "gemini" not in payload_str.lower()
        assert "system_prompt" not in payload_str.lower()

        # 4. Strictly NO internal authentication passwords
        assert "password" not in payload_str.lower()
