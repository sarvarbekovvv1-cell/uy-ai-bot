"""Tests for Admin Property Creation, Media Upload, Auto-Approval, and Searchability."""

import base64
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.config import get_settings
from app.main import app
from app.models.role import Role
from app.models.user import User
from app.services.admin_auth_service import AdminAuthService
from app.services.property_search_service import PropertySearchService


@pytest.fixture(autouse=True)
def setup_admin_db_dependencies(db_session: AsyncSession):
    async def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def setup_prop_creation_context(db_session: AsyncSession):
    # Superadmin
    super_role = Role(name="superadmin", description="Superadmin")
    db_session.add(super_role)
    await db_session.flush()

    super_user = User(
        telegram_id=90001,
        first_name="Admin",
        last_name="Boss",
        is_active=True,
    )
    super_user.roles.append(super_role)
    db_session.add(super_user)
    await db_session.flush()

    auth_service = AdminAuthService(get_settings())
    await auth_service.create_or_update_staff_credential(
        db_session, user_id=super_user.id, username="super_prop", password="Password123!"
    )

    # Sales Broker (has properties.create, but NOT properties.moderate)
    broker_role = Role(name="sales_broker", description="Sales Broker")
    db_session.add(broker_role)
    await db_session.flush()

    broker_user = User(
        telegram_id=90002,
        first_name="Broker",
        last_name="Sales",
        is_active=True,
    )
    broker_user.roles.append(broker_role)
    db_session.add(broker_user)
    await db_session.flush()

    await auth_service.create_or_update_staff_credential(
        db_session, user_id=broker_user.id, username="broker_prop", password="Password123!"
    )

    await db_session.commit()
    return super_user, broker_user


@pytest.mark.asyncio
async def test_admin_upload_media_valid_and_invalid(
    async_client: AsyncClient, setup_prop_creation_context
) -> None:
    """Test photo upload with magic byte inspection and JSON base64 support."""
    _super, _broker = setup_prop_creation_context

    login_resp = await async_client.post(
        "/api/admin/v1/auth/login", json={"username": "super_prop", "password": "Password123!"}
    )
    csrf_token = login_resp.json()["csrf_token"]

    # 1. Valid JPEG with magic bytes (\xff\xd8\xff) via raw binary
    valid_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100
    upload_resp = await async_client.post(
        "/api/admin/v1/properties/upload-media",
        headers={"X-CSRF-Token": csrf_token, "Content-Type": "image/jpeg"},
        content=valid_jpeg,
    )
    assert upload_resp.status_code == 201
    media_data = upload_resp.json()
    assert "media_unique_id" in media_data
    assert media_data["media_unique_id"].startswith("admin_media_")

    # 2. Valid Base64 PNG via JSON payload
    valid_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    png_b64 = base64.b64encode(valid_png).decode()
    json_upload_resp = await async_client.post(
        "/api/admin/v1/properties/upload-media",
        headers={"X-CSRF-Token": csrf_token},
        json={"content_type": "image/png", "data_base64": png_b64},
    )
    assert json_upload_resp.status_code == 201
    assert "media_unique_id" in json_upload_resp.json()

    # 3. Spoofed content type (claims to be image/jpeg but content is plain text)
    spoofed_resp = await async_client.post(
        "/api/admin/v1/properties/upload-media",
        headers={"X-CSRF-Token": csrf_token, "Content-Type": "image/jpeg"},
        content=b"MALICIOUS_NON_IMAGE_PAYLOAD",
    )
    assert spoofed_resp.status_code == 400
    assert "magic bytes" in spoofed_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_property_creation_auto_approve(
    async_client: AsyncClient, setup_prop_creation_context, db_session: AsyncSession
) -> None:
    """Superadmin creates property with auto_approve=True -> status approved immediately."""
    _super, _broker = setup_prop_creation_context

    login_resp = await async_client.post(
        "/api/admin/v1/auth/login", json={"username": "super_prop", "password": "Password123!"}
    )
    csrf_token = login_resp.json()["csrf_token"]

    prop_payload = {
        "listing_type": "sale",
        "property_type": "apartment",
        "title": "Chilonzor 3 xonali kvartira, yangi ta'mir",
        "description": "Metrogacha 5 daqiqa, barcha qulayliklar mavjud.",
        "region": "Toshkent",
        "district": "Chilonzor",
        "address": "Chilonzor 16-mavze, 4-uy",
        "rooms": 3,
        "total_area": "82.5",
        "condition": "renovated",
        "price": "78000",
        "currency": "USD",
        "auto_approve": True,
    }

    create_resp = await async_client.post(
        "/api/admin/v1/properties",
        headers={"X-CSRF-Token": csrf_token},
        json=prop_payload,
    )
    assert create_resp.status_code == 201
    prop_data = create_resp.json()
    assert prop_data["status"] == "approved"
    assert prop_data["district"] == "Chilonzor"
    assert Decimal(str(prop_data["price"])) == Decimal("78000")

    # Verify single source of truth: PropertySearchService finds the new approved listing!
    from app.schemas.property_search import PropertySearchFilters

    search_service = PropertySearchService()
    items, total, _ = await search_service.search(
        db_session,
        filters=PropertySearchFilters(listing_type="sale", district="Chilonzor"),
    )
    found_ids = [p.id for p in items]
    assert prop_data["id"] in found_ids


@pytest.mark.asyncio
async def test_admin_property_creation_submitted_review(
    async_client: AsyncClient, setup_prop_creation_context
) -> None:
    """Creation with auto_approve=False places property in 'submitted' moderation queue."""
    _super, _broker = setup_prop_creation_context

    login_resp = await async_client.post(
        "/api/admin/v1/auth/login", json={"username": "super_prop", "password": "Password123!"}
    )
    csrf_token = login_resp.json()["csrf_token"]

    prop_payload = {
        "listing_type": "rent",
        "property_type": "apartment",
        "title": "Yunusobod 2 xonali ijara",
        "region": "Toshkent",
        "district": "Yunusobod",
        "address": "Yunusobod 12",
        "rooms": 2,
        "total_area": "55.0",
        "condition": "new",
        "price": "450",
        "currency": "USD",
        "auto_approve": False,
    }

    create_resp = await async_client.post(
        "/api/admin/v1/properties",
        headers={"X-CSRF-Token": csrf_token},
        json=prop_payload,
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["status"] == "submitted"


@pytest.mark.asyncio
async def test_admin_property_creation_auto_approve_forbidden_for_broker(
    async_client: AsyncClient, setup_prop_creation_context
) -> None:
    """Sales broker without properties.moderate permission is denied from auto-approving."""
    _super, _broker = setup_prop_creation_context

    login_resp = await async_client.post(
        "/api/admin/v1/auth/login", json={"username": "broker_prop", "password": "Password123!"}
    )
    csrf_token = login_resp.json()["csrf_token"]

    prop_payload = {
        "listing_type": "sale",
        "property_type": "apartment",
        "region": "Toshkent",
        "district": "Mirobod",
        "address": "Oybek 12",
        "rooms": 2,
        "total_area": "60.0",
        "condition": "new",
        "price": "90000",
        "currency": "USD",
        "auto_approve": True,  # unauthorized auto_approve!
    }

    create_resp = await async_client.post(
        "/api/admin/v1/properties",
        headers={"X-CSRF-Token": csrf_token},
        json=prop_payload,
    )
    assert create_resp.status_code == 403
    assert "permission to auto-approve" in create_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_property_creation_validation_rules(
    async_client: AsyncClient, setup_prop_creation_context
) -> None:
    """Verify strict validation: negative price, zero area, and extra forbidden fields."""
    _super, _broker = setup_prop_creation_context

    login_resp = await async_client.post(
        "/api/admin/v1/auth/login", json={"username": "super_prop", "password": "Password123!"}
    )
    csrf_token = login_resp.json()["csrf_token"]

    # Negative price
    bad_price_resp = await async_client.post(
        "/api/admin/v1/properties",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "listing_type": "sale",
            "property_type": "apartment",
            "region": "Toshkent",
            "district": "Chilonzor",
            "address": "Chilonzor 1",
            "rooms": 2,
            "total_area": "50.0",
            "condition": "new",
            "price": "-5000",
        },
    )
    assert bad_price_resp.status_code == 422

    # Extra unknown field (forbidden)
    extra_field_resp = await async_client.post(
        "/api/admin/v1/properties",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "listing_type": "sale",
            "property_type": "apartment",
            "region": "Toshkent",
            "district": "Chilonzor",
            "address": "Chilonzor 1",
            "rooms": 2,
            "total_area": "50.0",
            "condition": "new",
            "price": "50000",
            "unknown_injected_field": "hack",
        },
    )
    assert extra_field_resp.status_code == 422
