"""Tests for Admin Brokers Workload and Leads Horizontal Authorization & Pipeline."""

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.config import get_settings
from app.main import app
from app.models.lead import Lead
from app.models.property import Property
from app.models.role import Role
from app.models.user import User
from app.services.admin_auth_service import AdminAuthService


@pytest.fixture(autouse=True)
def setup_admin_db_dependencies(db_session: AsyncSession):
    async def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def setup_leads_context(db_session: AsyncSession):
    # Roles
    head_role = Role(name="head_broker", description="Head Broker")
    sales_role = Role(name="sales_broker", description="Sales Broker")
    db_session.add_all([head_role, sales_role])
    await db_session.flush()

    # Head broker user
    head_user = User(
        telegram_id=40001,
        first_name="Head",
        last_name="Chief",
        is_active=True,
    )
    head_user.roles.append(head_role)

    # Broker A
    broker_a = User(
        telegram_id=40002,
        first_name="Broker",
        last_name="Alpha",
        is_active=True,
    )
    broker_a.roles.append(sales_role)

    # Broker B
    broker_b = User(
        telegram_id=40003,
        first_name="Broker",
        last_name="Beta",
        is_active=True,
    )
    broker_b.roles.append(sales_role)

    # Customer
    customer = User(
        telegram_id=40004,
        first_name="Customer",
        last_name="Ali",
        is_active=True,
    )

    db_session.add_all([head_user, broker_a, broker_b, customer])
    await db_session.flush()

    # Property
    prop = Property(
        owner_user_id=customer.id,
        title="Yashnobod Dom",
        property_type="apartment",
        listing_type="sale",
        region="Toshkent",
        district="Yashnobod",
        address="Yashnobod 12",
        condition="renovated",
        rooms=2,
        total_area=Decimal("60.0"),
        price=Decimal("60000"),
        currency="USD",
        status="approved",
    )
    db_session.add(prop)
    await db_session.flush()

    # Lead 1 assigned to Broker A
    lead_a = Lead(
        customer_user_id=customer.id,
        property_id=prop.id,
        broker_user_id=broker_a.id,
        stage="new",
        source="broker_contact",
    )
    # Lead 2 assigned to Broker B
    lead_b = Lead(
        customer_user_id=customer.id,
        property_id=prop.id,
        broker_user_id=broker_b.id,
        stage="contacted",
        source="viewing_request",
    )
    db_session.add_all([lead_a, lead_b])
    await db_session.flush()

    auth_service = AdminAuthService(get_settings())
    await auth_service.create_or_update_staff_credential(
        db_session, user_id=head_user.id, username="head_boss", password="Password123!"
    )
    await auth_service.create_or_update_staff_credential(
        db_session, user_id=broker_a.id, username="broker_a", password="Password123!"
    )
    await auth_service.create_or_update_staff_credential(
        db_session, user_id=broker_b.id, username="broker_b", password="Password123!"
    )

    await db_session.commit()
    return head_user, broker_a, broker_b, lead_a, lead_b


@pytest.mark.asyncio
async def test_horizontal_broker_isolation(
    async_client: AsyncClient, setup_leads_context
) -> None:
    """Test Broker A only sees their own leads, while Head Broker sees all leads."""
    head_user, broker_a, broker_b, lead_a, lead_b = setup_leads_context

    # Login as Broker A
    login_a = await async_client.post(
        "/api/admin/v1/auth/login", json={"username": "broker_a", "password": "Password123!"}
    )
    assert login_a.status_code == 200

    # Broker A lists leads -> only lead_a returned!
    resp_leads_a = await async_client.get("/api/admin/v1/leads")
    assert resp_leads_a.status_code == 200
    leads_a_data = resp_leads_a.json()
    assert leads_a_data["total"] == 1
    assert leads_a_data["items"][0]["id"] == lead_a.id

    # Broker A attempts to access Lead B -> 403 Forbidden!
    resp_lead_b_access = await async_client.get(f"/api/admin/v1/leads/{lead_b.id}")
    assert resp_lead_b_access.status_code == 403

    # Logout Broker A
    csrf_a = login_a.json()["csrf_token"]
    await async_client.post("/api/admin/v1/auth/logout", headers={"X-CSRF-Token": csrf_a})

    # Login as Head Broker
    login_head = await async_client.post(
        "/api/admin/v1/auth/login", json={"username": "head_boss", "password": "Password123!"}
    )
    assert login_head.status_code == 200

    # Head broker sees both leads
    resp_leads_head = await async_client.get("/api/admin/v1/leads")
    assert resp_leads_head.status_code == 200
    assert resp_leads_head.json()["total"] == 2


@pytest.mark.asyncio
async def test_lead_stage_transition_and_notes(
    async_client: AsyncClient, setup_leads_context
) -> None:
    """Test transitioning lead stage and attaching internal notes."""
    _head, _broker_a, _broker_b, lead_a, _lead_b = setup_leads_context

    login_a = await async_client.post(
        "/api/admin/v1/auth/login", json={"username": "broker_a", "password": "Password123!"}
    )
    csrf_token = login_a.json()["csrf_token"]

    # 1. Update stage from 'new' to 'contacted'
    resp_stage = await async_client.patch(
        f"/api/admin/v1/leads/{lead_a.id}/stage",
        headers={"X-CSRF-Token": csrf_token},
        json={"target_stage": "contacted"},
    )
    assert resp_stage.status_code == 200
    assert resp_stage.json()["stage"] == "contacted"

    # 2. Add note
    resp_note = await async_client.post(
        f"/api/admin/v1/leads/{lead_a.id}/notes",
        headers={"X-CSRF-Token": csrf_token},
        json={"note_text": "Mijoz bilan telefon orqali gaplashildi, narx qiziqtirdi."},
    )
    assert resp_note.status_code == 201

    # Detail view reflects updated stage and note
    detail = (await async_client.get(f"/api/admin/v1/leads/{lead_a.id}")).json()
    assert detail["stage"] == "contacted"
    assert len(detail["notes"]) == 1
    assert "telefon orqali" in detail["notes"][0]["note_text"]
