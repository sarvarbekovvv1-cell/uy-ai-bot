"""Comprehensive tests for Kaizen / PDCA Intelligence System and Analytics Engine."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.config import get_settings
from app.main import app
from app.models.crm_sync import CRMSyncEvent
from app.models.lead import Lead, LeadFollowUp
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
async def setup_kaizen_context(db_session: AsyncSession):
    # Superadmin User
    super_role = Role(name="superadmin", description="Super Admin")
    db_session.add(super_role)
    await db_session.flush()

    admin_user = User(
        telegram_id=80001,
        first_name="Kaizen",
        last_name="Super",
        is_active=True,
    )
    admin_user.roles.append(super_role)
    db_session.add(admin_user)
    await db_session.flush()

    auth_service = AdminAuthService(get_settings())
    await auth_service.create_or_update_staff_credential(
        db_session, user_id=admin_user.id, username="admin_kaizen", password="Password123!"
    )

    # Customer User
    customer = User(telegram_id=80002, first_name="Client", last_name="Buyer", is_active=True)
    db_session.add(customer)
    await db_session.flush()

    # Sales Broker User
    broker_role = Role(name="sales_broker", description="Sales Broker")
    db_session.add(broker_role)
    await db_session.flush()

    broker = User(telegram_id=80003, first_name="Agent", last_name="Broker", is_active=True)
    broker.roles.append(broker_role)
    db_session.add(broker)
    await db_session.flush()

    # Sample Property
    prop = Property(
        owner_user_id=customer.id,
        title="Yunusobod 3 xonali",
        property_type="apartment",
        listing_type="sale",
        region="Toshkent",
        district="Yunusobod",
        address="Amir Temur 45",
        rooms=3,
        total_area=Decimal("75.0"),
        condition="renovated",
        price=Decimal("80000"),
        currency="USD",
        status="approved",
    )
    db_session.add(prop)
    await db_session.flush()

    await db_session.commit()
    return admin_user, customer, broker, prop


@pytest.mark.asyncio
async def test_kaizen_overview_empty_database(
    async_client: AsyncClient, setup_kaizen_context
) -> None:
    """Ensure KPI engine handles zero data without division by zero errors."""
    _admin, _cust, _broker, _prop = setup_kaizen_context

    login_resp = await async_client.post(
        "/api/admin/v1/auth/login", json={"username": "admin_kaizen", "password": "Password123!"}
    )
    assert login_resp.status_code == 200

    resp = await async_client.get("/api/admin/v1/kaizen/overview?days=30")
    assert resp.status_code == 200
    data = resp.json()

    assert data["lead_funnel"]["total_leads"] == 0
    assert data["lead_funnel"]["conversion_rates"]["overall_win_rate"] is None
    assert data["response_time"]["sample_size"] == 0
    assert data["response_time"]["median_seconds"] is None
    assert data["response_time"]["insufficient_data"] is True
    assert data["viewings"]["total_viewings"] == 0
    assert data["viewings"]["completion_rate"] is None


@pytest.mark.asyncio
async def test_kaizen_overview_with_operational_data(
    async_client: AsyncClient, setup_kaizen_context, db_session: AsyncSession
) -> None:
    """Populate leads, viewings, and CRM sync to verify deterministic calculations."""
    _admin, customer, broker, prop = setup_kaizen_context

    now = datetime.now(UTC)
    c_at = now - timedelta(hours=2)
    cont_at = c_at + timedelta(minutes=20)  # 20 min response time

    # Create 3 leads
    lead1 = Lead(
        customer_user_id=customer.id,
        property_id=prop.id,
        broker_user_id=broker.id,
        source="manual",
        stage="won",
        created_at=c_at,
        contacted_at=cont_at,
    )
    lead2 = Lead(
        customer_user_id=customer.id,
        property_id=prop.id,
        broker_user_id=broker.id,
        source="manual",
        stage="lost",
        created_at=c_at,
        contacted_at=cont_at + timedelta(minutes=10),
    )
    lead3 = Lead(
        customer_user_id=customer.id,
        property_id=prop.id,
        broker_user_id=broker.id,
        source="manual",
        stage="new",
        created_at=c_at,
    )
    db_session.add_all([lead1, lead2, lead3])

    # Overdue followup task
    followup = LeadFollowUp(
        lead_id=1,  # will bind after flush
        broker_user_id=broker.id,
        task_type="call",
        due_at=now - timedelta(hours=1),
        status="pending",
    )
    db_session.add(followup)

    # CRM Outbox event
    crm_ev = CRMSyncEvent(
        provider="amocrm",
        event_type="lead_create",
        entity_type="lead",
        entity_id=1,
        status="failed",
        attempt_count=2,
    )
    db_session.add(crm_ev)
    await db_session.flush()
    followup.lead_id = lead1.id
    await db_session.commit()

    await async_client.post(
        "/api/admin/v1/auth/login", json={"username": "admin_kaizen", "password": "Password123!"}
    )

    resp = await async_client.get("/api/admin/v1/kaizen/overview?days=30")
    assert resp.status_code == 200
    data = resp.json()

    assert data["lead_funnel"]["total_leads"] == 3
    assert data["lead_funnel"]["won_leads"] == 1
    assert data["lead_funnel"]["lost_leads"] == 1
    # Win rate: 1 won out of 2 closed = 50.0%
    assert data["lead_funnel"]["conversion_rates"]["overall_win_rate"] == 50.0

    assert data["response_time"]["sample_size"] == 2
    assert data["response_time"]["median_minutes"] is not None

    assert data["brokers"]["total_overdue_followups"] >= 1
    assert data["crm_health"]["failed_events"] >= 1


@pytest.mark.asyncio
async def test_kaizen_date_range_validation(
    async_client: AsyncClient, setup_kaizen_context
) -> None:
    """Ensure invalid date_from > date_to returns HTTP 400."""
    _admin, _cust, _broker, _prop = setup_kaizen_context

    await async_client.post(
        "/api/admin/v1/auth/login", json={"username": "admin_kaizen", "password": "Password123!"}
    )

    resp = await async_client.get(
        "/api/admin/v1/kaizen/overview?date_from=2026-10-20&date_to=2026-10-10"
    )
    assert resp.status_code == 400
    assert "cannot be after date_to" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_pdca_cycle_full_lifecycle(async_client: AsyncClient, setup_kaizen_context) -> None:
    """Test full PDCA finite state machine: draft -> planned -> active -> checking -> completed."""
    _admin, _cust, _broker, _prop = setup_kaizen_context

    login_resp = await async_client.post(
        "/api/admin/v1/auth/login", json={"username": "admin_kaizen", "password": "Password123!"}
    )
    csrf_token = login_resp.json()["csrf_token"]

    # 1. CREATE CYCLE (draft)
    create_resp = await async_client.post(
        "/api/admin/v1/kaizen/cycles",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "title": "Lidlar konversiyasini oshirish",
            "metric_key": "overall_win_rate",
            "target_value": "25.0",
            "description": "Yangi broker skriptlari orqali win rateni 25% ga yetkazish",
            "plan_text": "Barcha brokerlarga yangi skriptlarni o'rgatish",
        },
    )
    assert create_resp.status_code == 201
    cycle = create_resp.json()
    assert cycle["status"] == "draft"
    assert cycle["metric_key"] == "overall_win_rate"
    cycle_id = cycle["id"]

    # 2. PLAN (draft -> planned)
    plan_resp = await async_client.post(
        f"/api/admin/v1/kaizen/cycles/{cycle_id}/plan",
        headers={"X-CSRF-Token": csrf_token},
        json={"plan_text": "Skriptlar tasdiqlandi, haftalik monitoring belgilandi."},
    )
    assert plan_resp.status_code == 200
    assert plan_resp.json()["status"] == "planned"

    # 3. START / DO (planned -> active)
    start_resp = await async_client.post(
        f"/api/admin/v1/kaizen/cycles/{cycle_id}/start",
        headers={"X-CSRF-Token": csrf_token},
        json={"do_text": "Yangi skript amaliyotga kiritildi."},
    )
    assert start_resp.status_code == 200
    assert start_resp.json()["status"] == "active"
    assert start_resp.json()["started_at"] is not None

    # 4. CHECK (active -> checking)
    check_resp = await async_client.post(
        f"/api/admin/v1/kaizen/cycles/{cycle_id}/check",
        headers={"X-CSRF-Token": csrf_token},
        json={"check_text": "Oraliq natijalar ko'rib chiqildi."},
    )
    assert check_resp.status_code == 200
    check_data = check_resp.json()
    assert check_data["cycle"]["status"] == "checking"
    assert check_data["cycle"]["checking_at"] is not None
    assert "delta" in check_data

    # 5. COMPLETE / ACT (checking -> completed)
    complete_resp = await async_client.post(
        f"/api/admin/v1/kaizen/cycles/{cycle_id}/complete",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "outcome": "successful",
            "act_text": "Skriptlar muvaffaqiyatli deb topildi va standart qilib belgilandi.",
        },
    )
    assert complete_resp.status_code == 200
    final_cycle = complete_resp.json()
    assert final_cycle["status"] == "completed"
    assert final_cycle["outcome"] == "successful"
    assert final_cycle["completed_at"] is not None


@pytest.mark.asyncio
async def test_pdca_cycle_invalid_transition(
    async_client: AsyncClient, setup_kaizen_context
) -> None:
    """Ensure jumping states or restarting completed cycles is rejected with HTTP 400."""
    _admin, _cust, _broker, _prop = setup_kaizen_context

    login_resp = await async_client.post(
        "/api/admin/v1/auth/login", json={"username": "admin_kaizen", "password": "Password123!"}
    )
    csrf_token = login_resp.json()["csrf_token"]

    create_resp = await async_client.post(
        "/api/admin/v1/kaizen/cycles",
        headers={"X-CSRF-Token": csrf_token},
        json={"title": "Test Cycle", "metric_key": "overall_win_rate"},
    )
    cycle_id = create_resp.json()["id"]

    # Attempting to check a cycle directly from draft (illegal) -> 400
    illegal_resp = await async_client.post(
        f"/api/admin/v1/kaizen/cycles/{cycle_id}/check",
        headers={"X-CSRF-Token": csrf_token},
        json={"check_text": "Premature check"},
    )
    assert illegal_resp.status_code == 400
    assert "invalid pdca state transition" in illegal_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_recommendations_generation_and_review(
    async_client: AsyncClient, setup_kaizen_context, db_session: AsyncSession
) -> None:
    """Test deterministic recommendation generation and accept/dismiss flow."""
    _admin, customer, _broker, prop = setup_kaizen_context

    # Create a failed CRM event and an overdue followup to trigger deterministic rules
    crm_ev = CRMSyncEvent(
        provider="amocrm",
        event_type="lead_create",
        entity_type="lead",
        entity_id=1,
        status="failed",
        attempt_count=5,  # permanent fail
    )
    db_session.add(crm_ev)
    await db_session.commit()

    login_resp = await async_client.post(
        "/api/admin/v1/auth/login", json={"username": "admin_kaizen", "password": "Password123!"}
    )
    csrf_token = login_resp.json()["csrf_token"]

    # Generate recommendations (use_ai=False to test pure deterministic engine)
    gen_resp = await async_client.post(
        "/api/admin/v1/kaizen/recommendations/generate",
        headers={"X-CSRF-Token": csrf_token},
        json={"use_ai": False},
    )
    assert gen_resp.status_code == 201
    recs = gen_resp.json()
    assert len(recs) >= 1

    rec_id = recs[0]["id"]

    # Review: Accept
    rev_resp = await async_client.post(
        f"/api/admin/v1/kaizen/recommendations/{rec_id}/review",
        headers={"X-CSRF-Token": csrf_token},
        json={"action": "accept"},
    )
    assert rev_resp.status_code == 200
    assert rev_resp.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_kaizen_rbac_denial_for_broker_without_manage_permission(
    async_client: AsyncClient, setup_kaizen_context, db_session: AsyncSession
) -> None:
    """Ensure sales broker without kaizen.manage permission is denied (HTTP 403)."""
    _admin, _customer, broker, _prop = setup_kaizen_context

    auth_service = AdminAuthService(get_settings())
    await auth_service.create_or_update_staff_credential(
        db_session, user_id=broker.id, username="broker_sales", password="Password123!"
    )
    await db_session.commit()

    login_resp = await async_client.post(
        "/api/admin/v1/auth/login", json={"username": "broker_sales", "password": "Password123!"}
    )
    assert login_resp.status_code == 200
    csrf_token = login_resp.json()["csrf_token"]

    # Attempt to create cycle -> 403 Forbidden!
    resp = await async_client.post(
        "/api/admin/v1/kaizen/cycles",
        headers={"X-CSRF-Token": csrf_token},
        json={"title": "Unauthorized Cycle", "metric_key": "overall_win_rate"},
    )
    assert resp.status_code == 403
