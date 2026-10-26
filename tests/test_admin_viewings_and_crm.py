"""Tests for Admin Viewing Requests, CRM Outbox Monitoring/Retry, and Immutable Audit Log."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.config import get_settings
from app.main import app
from app.models.crm_sync import CRMSyncEvent
from app.models.property import Property
from app.models.role import Role
from app.models.user import User
from app.models.viewing_request import ViewingRequest
from app.services.admin_auth_service import AdminAuthService


@pytest.fixture(autouse=True)
def setup_admin_db_dependencies(db_session: AsyncSession):
    async def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def setup_viewings_and_crm_context(db_session: AsyncSession):
    # Staff Superadmin
    super_role = Role(name="superadmin", description="Superadmin")
    db_session.add(super_role)
    await db_session.flush()

    staff_user = User(telegram_id=30001, first_name="Staff", last_name="Admin", is_active=True)
    staff_user.roles.append(super_role)
    db_session.add(staff_user)
    await db_session.flush()

    customer = User(telegram_id=30002, first_name="Client", last_name="User", is_active=True)
    db_session.add(customer)
    await db_session.flush()

    prop = Property(
        owner_user_id=customer.id,
        title="Uchtepa bino",
        property_type="commercial",
        listing_type="sale",
        region="Toshkent",
        district="Uchtepa",
        address="Uchtepa 14",
        condition="new",
        rooms=4,
        total_area=Decimal("120.0"),
        price=Decimal("110000"),
        currency="USD",
        status="approved",
    )
    db_session.add(prop)
    await db_session.flush()

    viewing = ViewingRequest(
        customer_user_id=customer.id,
        property_id=prop.id,
        broker_user_id=staff_user.id,
        request_type="in_person",
        preferred_date=date.today() + timedelta(days=2),
        preferred_time="15:00",
        status="pending",
    )
    db_session.add(viewing)
    await db_session.flush()

    crm_failed = CRMSyncEvent(
        provider="amocrm",
        event_type="lead_created",
        entity_type="lead",
        entity_id=99,
        status="failed",
        attempt_count=5,
        last_error_safe="HTTP 500: Server temporary failure",
    )
    crm_succeeded = CRMSyncEvent(
        provider="amocrm",
        event_type="stage_updated",
        entity_type="lead",
        entity_id=100,
        status="succeeded",
        attempt_count=1,
    )
    db_session.add_all([crm_failed, crm_succeeded])
    await db_session.flush()

    auth_service = AdminAuthService(get_settings())
    await auth_service.create_or_update_staff_credential(
        db_session, user_id=staff_user.id, username="admin_crm", password="Password123!"
    )

    await db_session.commit()
    return staff_user, viewing, crm_failed, crm_succeeded


@pytest.mark.asyncio
async def test_viewing_request_actions(
    async_client: AsyncClient, setup_viewings_and_crm_context
) -> None:
    """Test viewing acceptance and completion lifecycle actions."""
    staff_user, viewing, _crm_failed, _crm_succ = setup_viewings_and_crm_context

    login_resp = await async_client.post(
        "/api/admin/v1/auth/login", json={"username": "admin_crm", "password": "Password123!"}
    )
    csrf_token = login_resp.json()["csrf_token"]

    # 1. Accept viewing
    resp_accept = await async_client.post(
        f"/api/admin/v1/viewings/{viewing.id}/accept",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp_accept.status_code == 200

    # 2. Complete viewing with outcome
    resp_complete = await async_client.post(
        f"/api/admin/v1/viewings/{viewing.id}/complete",
        headers={"X-CSRF-Token": csrf_token},
        json={"outcome": "interested", "notes": "Mijozga yoqdi, bron qilindi"},
    )
    assert resp_complete.status_code == 200


@pytest.mark.asyncio
async def test_crm_outbox_monitoring_and_retry(
    async_client: AsyncClient, setup_viewings_and_crm_context
) -> None:
    """Test CRM outbox monitoring, error sanitization, and retry flow."""
    _staff, _viewing, crm_failed, crm_succeeded = setup_viewings_and_crm_context

    login_resp = await async_client.post(
        "/api/admin/v1/auth/login", json={"username": "admin_crm", "password": "Password123!"}
    )
    csrf_token = login_resp.json()["csrf_token"]

    # 1. List CRM events
    resp_events = await async_client.get("/api/admin/v1/crm/events")
    assert resp_events.status_code == 200
    events_data = resp_events.json()
    assert events_data["total"] >= 2

    # Zero secrets in response
    for item in events_data["items"]:
        err = item.get("last_error_safe") or ""
        assert "Bearer" not in err
        assert "token" not in err.lower()

    # 2. Retry failed event -> 200 (status reset to pending)
    resp_retry = await async_client.post(
        f"/api/admin/v1/crm/events/{crm_failed.id}/retry",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp_retry.status_code == 200

    # 3. Cannot retry already succeeded event -> 400
    resp_retry_succ = await async_client.post(
        f"/api/admin/v1/crm/events/{crm_succeeded.id}/retry",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp_retry_succ.status_code == 400


@pytest.mark.asyncio
async def test_audit_log_visibility_and_immutability(
    async_client: AsyncClient, setup_viewings_and_crm_context
) -> None:
    """Test administrative audit log entries are generated and immutable."""
    _staff, _viewing, _crm_failed, _crm_succ = setup_viewings_and_crm_context

    login_resp = await async_client.post(
        "/api/admin/v1/auth/login", json={"username": "admin_crm", "password": "Password123!"}
    )
    assert login_resp.status_code == 200

    # Audit events list
    resp_audit = await async_client.get("/api/admin/v1/audit")
    assert resp_audit.status_code == 200
    audit_data = resp_audit.json()
    assert audit_data["total"] >= 1
    # Verify auth.login action was recorded
    actions = [item["action"] for item in audit_data["items"]]
    assert "auth.login" in actions

    # Prove immutability: attempting to delete or edit audit trail returns 404/405
    del_resp = await async_client.delete(f"/api/admin/v1/audit/{audit_data['items'][0]['id']}")
    assert del_resp.status_code in (404, 405)
