"""Comprehensive End-to-End Acceptance Test Suite for UyAI (Phase 13)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.config import get_settings
from app.main import app
from app.models.crm_sync import CRMSyncEvent
from app.models.favorite import Favorite
from app.models.lead import LeadFollowUp, LeadNote
from app.models.property import Property
from app.models.role import Role
from app.models.user import User
from app.models.viewing_request import ViewingRequest
from app.services.admin_auth_service import AdminAuthService
from app.services.kaizen_analytics_service import KaizenAnalyticsService, KaizenDateRange
from app.services.kaizen_service import KaizenService
from app.services.lead_service import LeadService


@pytest.fixture(autouse=True)
def setup_admin_db_dependencies(db_session: AsyncSession):
    async def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def setup_e2e_acceptance_context(db_session: AsyncSession):
    # 1. Setup Roles
    roles = {
        name: Role(name=name, description=f"{name.replace('_', ' ').capitalize()} Role")
        for name in (
            "superadmin",
            "head_broker",
            "sales_broker",
            "rental_broker",
            "moderator",
            "buyer",
            "seller",
        )
    }
    for r in roles.values():
        db_session.add(r)
    await db_session.flush()

    # 2. Superadmin User
    admin = User(
        telegram_id=111001,
        first_name="Alisher",
        last_name="SuperAdmin",
        is_active=True,
        is_verified=True,
    )
    admin.roles.append(roles["superadmin"])
    db_session.add(admin)
    await db_session.flush()

    auth_service = AdminAuthService(get_settings())
    await auth_service.create_or_update_staff_credential(
        db_session,
        user_id=admin.id,
        username="e2e_admin",
        password="ProductionPassword123!",
    )

    # 3. Broker User
    broker = User(
        telegram_id=111002,
        first_name="Bobur",
        last_name="Broker",
        phone="+998901112233",
        is_active=True,
        is_verified=True,
    )
    broker.roles.append(roles["sales_broker"])
    db_session.add(broker)

    # 4. Customer User (Buyer)
    customer = User(
        telegram_id=111003,
        first_name="Jasur",
        last_name="Buyer",
        phone="+998909998877",
        is_active=True,
        is_verified=True,
    )
    customer.roles.append(roles["buyer"])
    db_session.add(customer)

    # 5. Property Owner User (Seller)
    seller = User(
        telegram_id=111004,
        first_name="Sanjar",
        last_name="Owner",
        phone="+998905554433",
        is_active=True,
        is_verified=True,
    )
    seller.roles.append(roles["seller"])
    db_session.add(seller)

    await db_session.commit()
    return admin, broker, customer, seller


async def _login_admin(async_client: AsyncClient) -> dict[str, str]:
    login_resp = await async_client.post(
        "/api/admin/v1/auth/login",
        json={"username": "e2e_admin", "password": "ProductionPassword123!"},
    )
    assert login_resp.status_code == 200
    csrf_token = login_resp.json()["csrf_token"]
    return {"x-csrf-token": csrf_token}


# -----------------------------------------------------------------------------
# FLOW 1: Customer -> Search -> Favorite -> Viewing -> Lead -> Won -> Kaizen
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_acceptance_flow_customer_to_kaizen(
    setup_e2e_acceptance_context, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(get_settings(), "amocrm_enabled", True)
    admin, broker, customer, seller = setup_e2e_acceptance_context

    # 1. Seller creates listing
    prop = Property(
        owner_user_id=seller.id,
        title="Tashkent City 2-room Apartment",
        description="Luxury apartment with modern renovation",
        property_type="apartment",
        listing_type="sale",
        region="Toshkent",
        district="Shayxontohur",
        address="Navoi 1A",
        rooms=2,
        total_area=Decimal("68.5"),
        condition="renovated",
        price=Decimal("95000"),
        currency="USD",
        status="approved",
    )
    db_session.add(prop)
    await db_session.commit()

    # 2. Customer adds to favorites
    fav = Favorite(user_id=customer.id, property_id=prop.id)
    db_session.add(fav)
    await db_session.commit()

    # 3. Customer submits viewing request
    viewing = ViewingRequest(
        customer_user_id=customer.id,
        property_id=prop.id,
        broker_user_id=broker.id,
        request_type="viewing",
        preferred_date=datetime.now(UTC).date(),
        preferred_time="15:00",
        status="completed",
        outcome="interested",
        customer_comment="Ready to inspect today",
    )
    db_session.add(viewing)
    await db_session.commit()

    # 4. Lead generated from viewing request and assigned to broker
    lead_service = LeadService()
    lead = await lead_service.ensure_lead_for_request(
        db_session,
        request=viewing,
        broker_user_id=broker.id,
    )
    await db_session.commit()
    assert lead is not None
    assert lead.customer_user_id == customer.id
    assert lead.stage == "new"

    # 5. Broker logs note, schedules followup, and contacts lead
    await lead_service.update_stage(
        db_session,
        lead_id=lead.id,
        broker_user_id=broker.id,
        target_stage="contacted",
    )
    await db_session.commit()

    note = LeadNote(
        lead_id=lead.id,
        author_user_id=broker.id,
        text="Discussed financing terms with customer. Scheduled viewing.",
    )
    db_session.add(note)

    fu = LeadFollowUp(
        lead_id=lead.id,
        broker_user_id=broker.id,
        task_type="call",
        due_at=datetime.now(UTC) + timedelta(days=1),
        status="completed",
        completed_at=datetime.now(UTC),
    )
    db_session.add(fu)

    # Progress lead: qualified -> viewing_scheduled -> negotiation -> won
    for stage in ("qualified", "viewing_scheduled", "negotiation", "won"):
        await lead_service.update_stage(
            db_session,
            lead_id=lead.id,
            broker_user_id=broker.id,
            target_stage=stage,
        )
    await db_session.commit()

    # 6. Verify Outbox CRM Sync Event generated
    crm_events = (
        (await db_session.execute(select(CRMSyncEvent).where(CRMSyncEvent.entity_id == lead.id)))
        .scalars()
        .all()
    )
    assert len(crm_events) >= 1
    assert crm_events[0].provider == "amocrm"

    # 7. Verify Kaizen KPI engine incorporates this won lead deterministically
    date_range = KaizenDateRange(days=30)
    overview = await KaizenAnalyticsService.get_kpi_overview(db_session, date_range)
    assert overview["lead_funnel"]["won_leads"] >= 1
    assert overview["lead_funnel"]["reached_contacted"] >= 1
    assert overview["viewings"]["completed"] >= 1
    assert overview["response_time"]["sample_size"] >= 1


# -----------------------------------------------------------------------------
# FLOW 2: Property Owner -> Listing -> Admin Moderation -> Approved
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_acceptance_flow_property_moderation(
    async_client: AsyncClient, setup_e2e_acceptance_context, db_session: AsyncSession
):
    _admin, _broker, _customer, seller = setup_e2e_acceptance_context
    headers = await _login_admin(async_client)

    # 1. Create property submitted by seller
    prop = Property(
        owner_user_id=seller.id,
        title="Chilonzor 3-room Apartment",
        property_type="apartment",
        listing_type="sale",
        region="Toshkent",
        district="Chilonzor",
        address="Qatortol 12",
        rooms=3,
        total_area=Decimal("78.0"),
        condition="euro",
        price=Decimal("72000"),
        currency="USD",
        status="submitted",
    )
    db_session.add(prop)
    await db_session.commit()

    # 2. Admin inspects pending properties list
    list_resp = await async_client.get(
        "/api/admin/v1/properties?status=submitted",
        headers=headers,
    )
    assert list_resp.status_code == 200
    props = list_resp.json()["items"]
    assert any(p["id"] == prop.id for p in props)

    # 3. Admin approves property
    approve_resp = await async_client.post(
        f"/api/admin/v1/properties/{prop.id}/approve",
        headers=headers,
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "ok"

    # 4. Verify property is now approved
    await db_session.refresh(prop)
    assert prop.status == "approved"
    assert prop.approved_at is not None


# -----------------------------------------------------------------------------
# FLOW 3: Admin -> Property Creation -> RBAC -> Kaizen PDCA Execution
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_acceptance_flow_admin_kaizen_pdca(
    async_client: AsyncClient, setup_e2e_acceptance_context, db_session: AsyncSession
):
    admin, _broker, customer, _seller = setup_e2e_acceptance_context
    headers = await _login_admin(async_client)

    # 1. Admin directly creates property listing
    create_prop_resp = await async_client.post(
        "/api/admin/v1/properties",
        json={
            "title": "Admin Created Listing",
            "property_type": "apartment",
            "listing_type": "sale",
            "region": "Toshkent",
            "district": "Yakkasaroy",
            "address": "Shota Rustaveli 25",
            "rooms": 2,
            "total_area": 55.0,
            "condition": "renovated",
            "price": 65000.0,
            "currency": "USD",
            "auto_approve": True,
            "owner_user_id": customer.id,
        },
        headers=headers,
    )
    assert create_prop_resp.status_code == 201
    created_prop = create_prop_resp.json()
    assert created_prop["owner"]["id"] == customer.id
    assert created_prop["status"] == "approved"

    # 2. Admin creates Kaizen PDCA cycle
    cycle = await KaizenService.create_cycle(
        db_session,
        title="Q4 Conversion Acceleration",
        metric_key="overall_win_rate",
        target_value=Decimal("35.0"),
        created_by_user_id=admin.id,
        plan_text="Introduce fast-track broker callback within 15 minutes.",
    )
    assert cycle.status == "draft"

    # 3. Transition: plan -> start (DO) -> check -> complete (ACT)
    planned = await KaizenService.plan_cycle(
        db_session,
        cycle_id=cycle.id,
        staff_user_id=admin.id,
        plan_text="Targeting 35% win rate across sales brokers.",
    )
    assert planned.status == "planned"

    active = await KaizenService.start_cycle(
        db_session,
        cycle_id=cycle.id,
        staff_user_id=admin.id,
        do_text="Active execution started across brokers.",
    )
    assert active.status == "active"

    checked = await KaizenService.check_cycle(
        db_session,
        cycle_id=cycle.id,
        staff_user_id=admin.id,
        check_text="Mid-term metrics reviewed.",
    )
    assert checked["cycle"].status == "checking"

    completed = await KaizenService.complete_cycle(
        db_session,
        cycle_id=cycle.id,
        staff_user_id=admin.id,
        outcome="successful",
        act_text="Standardized 15-minute response protocol.",
    )
    assert completed.status == "completed"
    assert completed.outcome == "successful"
