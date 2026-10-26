"""Integration tests for amoCRM incoming webhooks and loop prevention."""

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.config import Settings, get_settings
from app.main import app
from app.models.crm_sync import CRMEntityLink, CRMSyncEvent
from app.models.lead import Lead
from app.models.property import Property
from app.models.role import Role
from app.models.user import User


@pytest.fixture(autouse=True)
def setup_webhook_dependencies(db_session: AsyncSession):
    """Ensure FastAPI dependency injection uses test DB session."""
    async def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_webhook_secret_authentication(async_client: AsyncClient) -> None:
    """Test webhook requires configured secret token exclusively via X-AmoCRM-Secret header."""
    test_settings = Settings(AMOCRM_ENABLED=True, AMOCRM_WEBHOOK_SECRET="secret_token_123")
    app.dependency_overrides[get_settings] = lambda: test_settings

    # 1. Missing secret header -> 401
    resp1 = await async_client.post("/api/integrations/amocrm/webhook", json={})
    assert resp1.status_code == 401

    # 2. Invalid secret header -> 401
    resp2 = await async_client.post(
        "/api/integrations/amocrm/webhook",
        headers={"X-AmoCRM-Secret": "wrong_secret"},
        json={},
    )
    assert resp2.status_code == 401

    # 3. Query param secret is STRICTLY REJECTED to prevent log leakage -> 401
    resp3 = await async_client.post(
        "/api/integrations/amocrm/webhook?secret=secret_token_123", json={}
    )
    assert resp3.status_code == 401

    # 4. Valid secret via Header -> 200
    resp4 = await async_client.post(
        "/api/integrations/amocrm/webhook",
        headers={"X-AmoCRM-Secret": "secret_token_123"},
        json={},
    )
    assert resp4.status_code == 200

    # 5. Oversized payload (> 1MB) -> 413
    huge_header = {"X-AmoCRM-Secret": "secret_token_123", "Content-Length": str(1_048_577)}
    resp5 = await async_client.post(
        "/api/integrations/amocrm/webhook",
        headers=huge_header,
        content=b"x" * 10,
    )
    assert resp5.status_code == 413


@pytest.mark.asyncio
async def test_webhook_pipeline_mismatch_ignored(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test webhook for lead in a different amoCRM pipeline is ignored."""
    test_settings = Settings(
        AMOCRM_ENABLED=True,
        AMOCRM_PIPELINE_ID=5555,
        AMOCRM_WEBHOOK_SECRET="wh_secret_999",
        AMOCRM_STAGE_MAPPING_JSON='{"new": 101, "contacted": 102}',
    )
    app.dependency_overrides[get_settings] = lambda: test_settings

    user = User(telegram_id=888999, first_name="PipUser", is_active=True)
    db_session.add(user)
    await db_session.flush()

    prop = Property(
        owner_user_id=user.id,
        title="Test Pip Dom",
        property_type="apartment",
        listing_type="sale",
        region="Toshkent",
        district="Chilonzor",
        address="Chilonzor 1",
        condition="renovated",
        rooms=2,
        total_area=Decimal("50.0"),
        price=Decimal("50000"),
        currency="USD",
        status="approved",
    )
    db_session.add(prop)
    await db_session.flush()

    lead = Lead(customer_user_id=user.id, property_id=prop.id, source="broker_contact", stage="new")
    db_session.add(lead)
    await db_session.flush()

    link = CRMEntityLink(
        provider="amocrm",
        local_entity_type="lead",
        local_entity_id=lead.id,
        external_entity_type="lead",
        external_entity_id="666222",
    )
    db_session.add(link)
    await db_session.commit()

    # Webhook contains mismatched pipeline_id=9999 (expected 5555)
    payload = {
        "leads": {
            "status": [
                {
                    "id": 666222,
                    "status_id": 102,
                    "pipeline_id": 9999,
                }
            ]
        }
    }
    response = await async_client.post(
        "/api/integrations/amocrm/webhook",
        headers={"X-AmoCRM-Secret": "wh_secret_999"},
        json=payload,
    )
    assert response.status_code == 200
    assert response.json()["processed"] == 0

    await db_session.refresh(lead)
    assert lead.stage == "new"  # Unchanged


@pytest.mark.asyncio
async def test_webhook_updates_lead_stage_with_loop_prevention(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test webhook updates internal Lead stage and strictly prevents outbox loop."""
    test_settings = Settings(
        AMOCRM_ENABLED=True,
        AMOCRM_WEBHOOK_SECRET="wh_secret_999",
        AMOCRM_STAGE_MAPPING_JSON='{"new": 101, "contacted": 102}',
    )
    app.dependency_overrides[get_settings] = lambda: test_settings

    # Roles and broker
    sales_role = Role(name="sales_broker", description="Sales broker")
    db_session.add(sales_role)
    await db_session.flush()

    broker = User(
        telegram_id=99001,
        first_name="Broker",
        last_name="Test",
        is_active=True,
    )
    broker.roles.append(sales_role)

    # Customer
    user = User(telegram_id=111222, first_name="Bekzod", is_active=True)
    db_session.add_all([broker, user])
    await db_session.flush()

    prop = Property(
        owner_user_id=user.id,
        title="Test Dom",
        property_type="apartment",
        listing_type="sale",
        region="Toshkent",
        district="Mirzo Ulug‘bek",
        address="Buyuk Ipak Yo'li 10",
        condition="renovated",
        rooms=2,
        total_area=Decimal("60.0"),
        status="approved",
        price=Decimal("120000"),
        currency="USD",
    )
    db_session.add(prop)
    await db_session.flush()

    lead = Lead(
        customer_user_id=user.id,
        property_id=prop.id,
        broker_user_id=broker.id,
        source="broker_contact",
        stage="new",
    )
    db_session.add(lead)
    await db_session.flush()

    # Link lead to external amoCRM ID '778899'
    link = CRMEntityLink(
        provider="amocrm",
        local_entity_type="lead",
        local_entity_id=lead.id,
        external_entity_type="lead",
        external_entity_id="778899",
    )
    db_session.add(link)
    await db_session.commit()

    # Deliver amoCRM webhook moving status to 102 ('contacted')
    webhook_payload = {
        "leads": {
            "status": [
                {
                    "id": 778899,
                    "status_id": 102,
                }
            ]
        }
    }

    response = await async_client.post(
        "/api/integrations/amocrm/webhook",
        headers={"X-AmoCRM-Secret": "wh_secret_999"},
        json=webhook_payload,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["processed"] == 1

    # Verify internal Lead stage changed to 'contacted'
    await db_session.refresh(lead)
    assert lead.stage == "contacted"

    # CRITICAL LOOP PREVENTION CHECK:
    # Applying stage from webhook must NOT create a new outbound CRM event
    new_events = list(
        (
            await db_session.scalars(
                select(CRMSyncEvent).where(
                    CRMSyncEvent.entity_id == lead.id,
                    CRMSyncEvent.event_type == "stage_updated",
                )
            )
        ).all()
    )
    assert len(new_events) == 0  # Zero loop events!


@pytest.mark.asyncio
async def test_webhook_unknown_entity_ignored(async_client: AsyncClient) -> None:
    """Test webhook with unknown external ID is safely ignored without creating phantom leads."""
    test_settings = Settings(
        AMOCRM_ENABLED=True,
        AMOCRM_WEBHOOK_SECRET="wh_secret_999",
        AMOCRM_STAGE_MAPPING_JSON='{"new": 101, "contacted": 102}',
    )
    app.dependency_overrides[get_settings] = lambda: test_settings

    payload = {
        "leads": {
            "status": [
                {
                    "id": 999999999,  # Unknown external lead
                    "status_id": 102,
                }
            ]
        }
    }

    response = await async_client.post(
        "/api/integrations/amocrm/webhook",
        headers={"X-AmoCRM-Secret": "wh_secret_999"},
        json=payload,
    )
    assert response.status_code == 200
    assert response.json()["processed"] == 0


@pytest.mark.asyncio
async def test_webhook_unmapped_status_ignored(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test webhook with unmapped external status does not corrupt internal state."""
    test_settings = Settings(
        AMOCRM_ENABLED=True,
        AMOCRM_WEBHOOK_SECRET="wh_secret_999",
        AMOCRM_STAGE_MAPPING_JSON='{"new": 101}',
    )
    app.dependency_overrides[get_settings] = lambda: test_settings

    user = User(telegram_id=333444, first_name="Sardor", is_active=True)
    db_session.add(user)
    await db_session.flush()

    prop = Property(
        owner_user_id=user.id,
        title="Test Kvartira",
        property_type="apartment",
        listing_type="sale",
        region="Toshkent",
        district="Yunusobod",
        address="Yunusobod 12",
        condition="renovated",
        rooms=2,
        total_area=Decimal("50.0"),
        status="approved",
        price=Decimal("50000"),
        currency="USD",
    )
    db_session.add(prop)
    await db_session.flush()

    lead = Lead(
        customer_user_id=user.id,
        property_id=prop.id,
        source="broker_contact",
        stage="new",
    )
    db_session.add(lead)
    await db_session.flush()

    link = CRMEntityLink(
        provider="amocrm",
        local_entity_type="lead",
        local_entity_id=lead.id,
        external_entity_type="lead",
        external_entity_id="888111",
    )
    db_session.add(link)
    await db_session.commit()

    # Webhook sends random unmapped status 999999
    payload = {"leads": {"status": [{"id": 888111, "status_id": 999999}]}}

    response = await async_client.post(
        "/api/integrations/amocrm/webhook",
        headers={"X-AmoCRM-Secret": "wh_secret_999"},
        json=payload,
    )
    assert response.status_code == 200
    assert response.json()["processed"] == 0

    await db_session.refresh(lead)
    assert lead.stage == "new"  # Still unchanged
