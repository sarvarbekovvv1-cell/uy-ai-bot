"""Tests for Admin Property Management, Moderation, Sort Allowlist, and PII Protection."""

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.config import get_settings
from app.main import app
from app.models.property import Property
from app.models.property_media import PropertyMedia
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
async def setup_properties_context(db_session: AsyncSession):
    # Superadmin staff user
    admin_role = Role(name="superadmin", description="Super Admin")
    db_session.add(admin_role)
    await db_session.flush()

    admin_user = User(
        telegram_id=60001,
        first_name="Admin",
        last_name="Super",
        is_active=True,
    )
    admin_user.roles.append(admin_role)
    db_session.add(admin_user)
    await db_session.flush()

    auth_service = AdminAuthService(get_settings())
    await auth_service.create_or_update_staff_credential(
        db_session, user_id=admin_user.id, username="admin_prop", password="Password123!"
    )

    # Owner customer user
    owner = User(
        telegram_id=60002,
        first_name="Mulkdor",
        last_name="Aka",
        phone="+998901112233",
        is_active=True,
    )
    db_session.add(owner)
    await db_session.flush()

    # Property pending moderation
    prop1 = Property(
        owner_user_id=owner.id,
        title="Chilonzor 3 xonali kvartira",
        property_type="apartment",
        listing_type="sale",
        region="Toshkent",
        district="Chilonzor",
        address="Chilonzor 9-mavze",
        condition="renovated",
        rooms=3,
        total_area=Decimal("75.0"),
        price=Decimal("70000"),
        currency="USD",
        status="pending_approval",
    )
    # Approved property
    prop2 = Property(
        owner_user_id=owner.id,
        title="Yunusobod hovli",
        property_type="house",
        listing_type="sale",
        region="Toshkent",
        district="Yunusobod",
        address="Yunusobod 15",
        condition="new",
        rooms=5,
        total_area=Decimal("200.0"),
        price=Decimal("150000"),
        currency="USD",
        status="approved",
    )
    db_session.add_all([prop1, prop2])
    await db_session.flush()

    media = PropertyMedia(
        property_id=prop1.id,
        telegram_file_id="telegram_file_id_123",
        telegram_file_unique_id="uniq_123",
        media_type="photo",
        sort_order=0,
    )
    db_session.add(media)
    await db_session.commit()

    return admin_user, "admin_prop", "Password123!", prop1, prop2


@pytest.mark.asyncio
async def test_list_properties_and_sort_allowlist(
    async_client: AsyncClient, setup_properties_context
) -> None:
    """Test listing properties with filters and strict sort allowlist."""
    _admin, username, password, prop1, prop2 = setup_properties_context

    login_resp = await async_client.post(
        "/api/admin/v1/auth/login", json={"username": username, "password": password}
    )
    assert login_resp.status_code == 200

    # 1. Filter by status=pending_approval
    resp_pending = await async_client.get("/api/admin/v1/properties?status=pending_approval")
    assert resp_pending.status_code == 200
    data = resp_pending.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == prop1.id

    # 2. Valid sort allowlist (price desc)
    resp_sort = await async_client.get("/api/admin/v1/properties?sort_by=price&sort_order=desc")
    assert resp_sort.status_code == 200
    assert float(resp_sort.json()["items"][0]["price"]) == 150000.0

    # 3. Invalid malicious sort value rejected by validation (422)
    resp_bad_sort = await async_client.get(
        "/api/admin/v1/properties?sort_by=price;DROP+TABLE+users;--"
    )
    assert resp_bad_sort.status_code == 422


@pytest.mark.asyncio
async def test_property_approval_and_rejection_lifecycle(
    async_client: AsyncClient, setup_properties_context
) -> None:
    """Test approving and rejecting properties records audit trail."""
    _admin, username, password, prop1, _prop2 = setup_properties_context

    login_resp = await async_client.post(
        "/api/admin/v1/auth/login", json={"username": username, "password": password}
    )
    csrf_token = login_resp.json()["csrf_token"]

    # 1. Approve prop1
    resp_approve = await async_client.post(
        f"/api/admin/v1/properties/{prop1.id}/approve",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp_approve.status_code == 200

    # Verify status changed to approved
    detail = (await async_client.get(f"/api/admin/v1/properties/{prop1.id}")).json()
    assert detail["status"] == "approved"
    assert len(detail["media"]) == 1
    media_id = detail["media"][0]["id"]
    assert detail["media"][0]["safe_url"] == f"/api/miniapp/v1/properties/media/{media_id}"

    # 2. Reject with reason and XSS safety check
    xss_reason = "<script>alert('xss')</script> Invalid cadastral document"
    resp_reject = await async_client.post(
        f"/api/admin/v1/properties/{prop1.id}/reject",
        headers={"X-CSRF-Token": csrf_token},
        json={"reason": xss_reason},
    )
    assert resp_reject.status_code == 200

    detail2 = (await async_client.get(f"/api/admin/v1/properties/{prop1.id}")).json()
    assert detail2["status"] == "rejected"
    assert xss_reason in detail2["rejection_reason"]


@pytest.mark.asyncio
async def test_property_archive(async_client: AsyncClient, setup_properties_context) -> None:
    """Test archiving a property."""
    _admin, username, password, prop1, _prop2 = setup_properties_context

    login_resp = await async_client.post(
        "/api/admin/v1/auth/login", json={"username": username, "password": password}
    )
    csrf_token = login_resp.json()["csrf_token"]

    resp = await async_client.post(
        f"/api/admin/v1/properties/{prop1.id}/archive",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == 200

    detail = (await async_client.get(f"/api/admin/v1/properties/{prop1.id}")).json()
    assert detail["status"] == "archived"


@pytest.mark.asyncio
async def test_property_list_with_null_title(
    async_client: AsyncClient, setup_properties_context, db_session: AsyncSession
) -> None:
    """Ensure properties with title=None serialize successfully without Pydantic ValidationError."""
    _admin, username, password, _prop1, _prop2 = setup_properties_context

    # Create a property with title=None (common when bot draft is created)
    null_title_prop = Property(
        owner_user_id=_admin.id,
        title=None,
        property_type="apartment",
        listing_type="sale",
        region="Toshkent",
        district="Mirzo Ulugbek",
        address="Mustaqillik shoh ko'chasi 1",
        rooms=2,
        total_area=Decimal("60.0"),
        condition="renovated",
        price=Decimal("65000"),
        currency="USD",
        status="approved",
    )
    db_session.add(null_title_prop)
    await db_session.flush()

    await async_client.post(
        "/api/admin/v1/auth/login", json={"username": username, "password": password}
    )

    resp = await async_client.get("/api/admin/v1/properties")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 3
    found_null_title = any(
        item["id"] == null_title_prop.id and item["title"] is None for item in data["items"]
    )
    assert found_null_title is True


@pytest.mark.asyncio
async def test_property_list_status_filter_pending_approval(
    async_client: AsyncClient, setup_properties_context, db_session: AsyncSession
) -> None:
    """Ensure status filter 'pending_approval' matches submitted and under_review items."""
    _admin, username, password, _prop1, _prop2 = setup_properties_context

    submitted_prop = Property(
        owner_user_id=_admin.id,
        title="Yangi yuborilgan e'lon",
        property_type="apartment",
        listing_type="sale",
        region="Toshkent",
        district="Chilonzor",
        address="Chilonzor 1-mavze 10",
        rooms=3,
        total_area=Decimal("80.0"),
        condition="new",
        price=Decimal("85000"),
        currency="USD",
        status="submitted",
    )
    db_session.add(submitted_prop)
    await db_session.flush()

    await async_client.post(
        "/api/admin/v1/auth/login", json={"username": username, "password": password}
    )

    resp = await async_client.get("/api/admin/v1/properties?status=pending_approval")
    assert resp.status_code == 200
    data = resp.json()
    ids = [item["id"] for item in data["items"]]
    assert submitted_prop.id in ids


@pytest.mark.asyncio
async def test_dashboard_kpis_endpoint(async_client: AsyncClient, setup_properties_context) -> None:
    """Test dashboard KPIs endpoint returns all required metrics for both /kpis and root."""
    _admin, username, password, _prop1, _prop2 = setup_properties_context

    await async_client.post(
        "/api/admin/v1/auth/login", json={"username": username, "password": password}
    )

    resp_kpis = await async_client.get("/api/admin/v1/dashboard/kpis")
    assert resp_kpis.status_code == 200
    kpis = resp_kpis.json()
    assert "total_properties" in kpis
    assert "approved_properties" in kpis
    assert "pending_moderation_properties" in kpis
    assert "total_leads" in kpis
    assert "active_leads" in kpis
    assert "won_leads" in kpis
    assert "pending_viewings" in kpis
    assert "crm_failed_events" in kpis
    assert "crm_pending_events" in kpis

    resp_root = await async_client.get("/api/admin/v1/dashboard")
    assert resp_root.status_code == 200
    root_data = resp_root.json()
    assert root_data["total_properties"] == kpis["total_properties"]
