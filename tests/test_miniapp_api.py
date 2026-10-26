"""Integration tests for Telegram Mini App REST API endpoints."""

import time
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.session import get_db_session
from app.main import app
from app.models.property import Property
from app.models.property_media import PropertyMedia
from app.models.user import User
from app.services.favorite_service import FavoriteService
from tests.test_miniapp_auth import make_init_data

TEST_BOT_TOKEN = "123456789:mock_telegram_bot_test_token"


@pytest_asyncio.fixture
async def miniapp_client(
    db_session: AsyncSession,
) -> AsyncGenerator[tuple[AsyncClient, dict[str, str], User], None]:
    """Provide AsyncClient with dependency override for in-memory db_session and valid initData."""
    settings = get_settings()
    settings.bot_token = TEST_BOT_TOKEN
    settings.telegram_init_data_max_age_seconds = 86400

    # Ensure get_db_session yields test db_session
    async def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    # Seed test user
    user = User(
        telegram_id=7770001,
        username="test_customer",
        first_name="Customer",
        language="uz",
        phone="+998901234567",
        consent_accepted_at=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    init_data = make_init_data(
        TEST_BOT_TOKEN,
        {
            "id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "language_code": "uz",
        },
    )
    headers = {"Authorization": f"tma {init_data}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, headers, user

    app.dependency_overrides.clear()


async def create_test_property(
    session: AsyncSession,
    owner_id: int,
    *,
    status: str = "approved",
    listing_type: str = "sale",
    price: Decimal = Decimal("90000"),
    currency: str = "USD",
    rooms: int = 2,
    total_area: Decimal = Decimal("55"),
    district: str = "Chilonzor",
    latitude: Decimal | None = Decimal("41.2825"),
    longitude: Decimal | None = Decimal("69.2045"),
) -> Property:
    """Helper to persist Property in test database."""
    prop = Property(
        owner_user_id=owner_id,
        listing_type=listing_type,
        property_type="apartment",
        title=f"{rooms} xonali {district}",
        region="Toshkent shahri",
        district=district,
        address=f"Street {district} 1",
        rooms=rooms,
        total_area=total_area,
        condition="renovated",
        price=price,
        currency=currency,
        status=status,
        latitude=latitude,
        longitude=longitude,
    )
    session.add(prop)
    await session.commit()
    await session.refresh(prop)
    return prop


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(
    miniapp_client: tuple[AsyncClient, dict[str, str], User],
) -> None:
    """Verify endpoint rejects requests without Telegram initData."""
    client, _, _ = miniapp_client
    res = await client.get("/api/miniapp/v1/me")
    assert res.status_code == 401
    assert res.json()["detail"]["error"]["code"] == "AUTH_REQUIRED"


@pytest.mark.asyncio
async def test_get_me_returns_user_profile(
    miniapp_client: tuple[AsyncClient, dict[str, str], User],
) -> None:
    """Verify /me returns authenticated user's profile."""
    client, headers, user = miniapp_client
    res = await client.get("/api/miniapp/v1/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["telegram_id"] == user.telegram_id
    assert data["username"] == "test_customer"


@pytest.mark.asyncio
async def test_properties_list_approved_only(
    miniapp_client: tuple[AsyncClient, dict[str, str], User],
    db_session: AsyncSession,
) -> None:
    """Verify /properties strictly returns only approved inventory."""
    client, headers, user = miniapp_client

    # 2 approved, 1 draft, 1 rejected
    await create_test_property(db_session, user.id, status="approved", price=Decimal("85000"))
    await create_test_property(db_session, user.id, status="approved", price=Decimal("95000"))
    await create_test_property(db_session, user.id, status="draft", price=Decimal("70000"))
    await create_test_property(db_session, user.id, status="rejected", price=Decimal("60000"))

    res = await client.get("/api/miniapp/v1/properties", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_count"] == 2
    assert len(data["items"]) == 2
    assert all(float(item["price"]) >= 85000 for item in data["items"])


@pytest.mark.asyncio
async def test_properties_filtering_and_sorting(
    miniapp_client: tuple[AsyncClient, dict[str, str], User],
    db_session: AsyncSession,
) -> None:
    """Verify filtering by rooms, price, and sorting by price_asc."""
    client, headers, user = miniapp_client

    p1 = await create_test_property(db_session, user.id, price=Decimal("80000"), rooms=2)
    p2 = await create_test_property(db_session, user.id, price=Decimal("120000"), rooms=2)
    await create_test_property(db_session, user.id, price=Decimal("90000"), rooms=3)

    # Filter rooms=2, sort=price_asc
    res = await client.get(
        "/api/miniapp/v1/properties?rooms=2&sort=price_asc",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_count"] == 2
    assert data["items"][0]["id"] == p1.id
    assert data["items"][1]["id"] == p2.id


@pytest.mark.asyncio
async def test_property_detail_approved_only(
    miniapp_client: tuple[AsyncClient, dict[str, str], User],
    db_session: AsyncSession,
) -> None:
    """Verify /properties/{id} returns 200 for approved and 404 for draft/rejected."""
    client, headers, user = miniapp_client

    approved_prop = await create_test_property(db_session, user.id, status="approved")
    draft_prop = await create_test_property(db_session, user.id, status="draft")

    # Approved property
    res_app = await client.get(f"/api/miniapp/v1/properties/{approved_prop.id}", headers=headers)
    assert res_app.status_code == 200
    assert res_app.json()["id"] == approved_prop.id

    # Draft property -> 404
    res_draft = await client.get(f"/api/miniapp/v1/properties/{draft_prop.id}", headers=headers)
    assert res_draft.status_code == 404
    assert res_draft.json()["detail"]["error"]["code"] == "PROPERTY_NOT_FOUND"


@pytest.mark.asyncio
async def test_favorites_cross_flow(
    miniapp_client: tuple[AsyncClient, dict[str, str], User],
    db_session: AsyncSession,
) -> None:
    """Verify favorites addition, listing, deletion and cross-interface DB consistency."""
    client, headers, user = miniapp_client
    prop = await create_test_property(db_session, user.id, status="approved")

    fav_service = FavoriteService()
    assert not await fav_service.is_favorite(db_session, user_id=user.id, property_id=prop.id)

    # Add favorite via Mini App
    res_add = await client.post(f"/api/miniapp/v1/favorites/{prop.id}", headers=headers)
    assert res_add.status_code == 200
    assert res_add.json()["is_favorite"] is True

    # Check via Telegram favorite service
    assert await fav_service.is_favorite(db_session, user_id=user.id, property_id=prop.id)

    # List favorites via Mini App
    res_list = await client.get("/api/miniapp/v1/favorites", headers=headers)
    assert res_list.status_code == 200
    items = res_list.json()
    assert len(items) == 1
    assert items[0]["id"] == prop.id

    # Delete favorite via Mini App
    res_del = await client.delete(f"/api/miniapp/v1/favorites/{prop.id}", headers=headers)
    assert res_del.status_code == 200
    assert res_del.json()["is_favorite"] is False

    # Check via Telegram favorite service
    assert not await fav_service.is_favorite(db_session, user_id=user.id, property_id=prop.id)


@pytest.mark.asyncio
async def test_map_properties_and_bounds_filtering(
    miniapp_client: tuple[AsyncClient, dict[str, str], User],
    db_session: AsyncSession,
) -> None:
    """Verify map marker coordinates endpoint and bounding box query."""
    client, headers, user = miniapp_client

    # Chilonzor: lat 41.28, lon 69.20
    p1 = await create_test_property(
        db_session, user.id, latitude=Decimal("41.2800"), longitude=Decimal("69.2000")
    )
    # Yunusobod: lat 41.36, lon 69.28
    p2 = await create_test_property(
        db_session, user.id, latitude=Decimal("41.3600"), longitude=Decimal("69.2800")
    )
    # No coordinates
    await create_test_property(db_session, user.id, latitude=None, longitude=None)

    # 1. All map properties
    res_all = await client.get("/api/miniapp/v1/map/properties", headers=headers)
    assert res_all.status_code == 200
    markers = res_all.json()
    assert len(markers) == 2  # Property without coordinates is excluded!

    # Assert exact required contract fields are present and valid
    first = markers[0]
    required_fields = {
        "id",
        "latitude",
        "longitude",
        "price",
        "currency",
        "rooms",
        "property_type",
        "listing_type",
        "title",
        "district",
    }
    assert required_fields.issubset(set(first.keys()))
    assert first["currency"] in ("USD", "UZS")
    assert first["price"] is not None

    # Assert unapproved properties with valid coordinates are strictly excluded
    await create_test_property(
        db_session,
        user.id,
        status="draft",
        latitude=Decimal("41.2900"),
        longitude=Decimal("69.2100"),
    )
    await create_test_property(
        db_session,
        user.id,
        status="under_review",
        latitude=Decimal("41.3100"),
        longitude=Decimal("69.2300"),
    )
    res_after_unapproved = await client.get("/api/miniapp/v1/map/properties", headers=headers)
    assert len(res_after_unapproved.json()) == 2  # Still 2! Only approved exposed.

    # Assert UZS currency property is also supported
    p_uzs = await create_test_property(
        db_session,
        user.id,
        status="approved",
        price=Decimal("850000000"),
        currency="UZS",
        latitude=Decimal("41.3200"),
        longitude=Decimal("69.2400"),
    )
    res_with_uzs = await client.get("/api/miniapp/v1/map/properties", headers=headers)
    assert len(res_with_uzs.json()) == 3
    uzs_marker = next(m for m in res_with_uzs.json() if m["id"] == p_uzs.id)
    assert uzs_marker["currency"] == "UZS"
    assert "850000000" in str(uzs_marker["price"])

    # 2. Viewport bounds query targeting only Chilonzor
    # north=41.30, south=41.25, east=69.25, west=69.15
    res_box = await client.get(
        "/api/miniapp/v1/map/properties?north=41.30&south=41.25&east=69.25&west=69.15",
        headers=headers,
    )
    assert res_box.status_code == 200
    box_markers = res_box.json()
    assert len(box_markers) == 1
    assert box_markers[0]["id"] == p1.id
    assert box_markers[0]["id"] != p2.id


@pytest.mark.asyncio
async def test_viewing_request_endpoint_and_dedup(
    miniapp_client: tuple[AsyncClient, dict[str, str], User],
    db_session: AsyncSession,
) -> None:
    """Verify creating a viewing request via Mini App routes into existing ViewingRequestService."""
    client, headers, user = miniapp_client
    prop = await create_test_property(db_session, user.id, status="approved")

    future_date = (datetime.now(UTC) + timedelta(days=2)).date().isoformat()
    payload = {
        "preferred_date": future_date,
        "preferred_time": "14:00 - 16:00",
        "customer_comment": "Testing viewing request from Mini App",
    }

    # 1. Create viewing request
    res = await client.post(
        f"/api/miniapp/v1/properties/{prop.id}/viewing-request",
        json=payload,
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["property_id"] == prop.id
    assert data["status"] == "pending"

    # 2. Duplicate viewing request on same date/time returns 409 conflict
    res_dup = await client.post(
        f"/api/miniapp/v1/properties/{prop.id}/viewing-request",
        json=payload,
        headers=headers,
    )
    assert res_dup.status_code == 409
    assert res_dup.json()["detail"]["error"]["code"] == "DUPLICATE_VIEWING_REQUEST"


@pytest.mark.asyncio
async def test_broker_contact_endpoint(
    miniapp_client: tuple[AsyncClient, dict[str, str], User],
    db_session: AsyncSession,
) -> None:
    """Verify broker contact request endpoint integration."""
    client, headers, user = miniapp_client
    prop = await create_test_property(db_session, user.id, status="approved")

    payload = {"customer_comment": "Interested in purchasing."}
    res = await client.post(
        f"/api/miniapp/v1/properties/{prop.id}/broker-contact",
        json=payload,
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["property_id"] == prop.id
    assert data["request_type"] == "broker_contact"


@pytest.mark.asyncio
async def test_media_streaming_security(
    miniapp_client: tuple[AsyncClient, dict[str, str], User],
    db_session: AsyncSession,
) -> None:
    """Verify media proxy endpoint serves placeholder/bytes safely and rejects invalid media."""
    client, headers, user = miniapp_client
    prop = await create_test_property(db_session, user.id, status="approved")

    # Add media item
    media = PropertyMedia(
        property_id=prop.id,
        telegram_file_id="tg_file_abc123",
        telegram_file_unique_id="unique_abc123",
        media_type="photo",
        sort_order=0,
    )
    db_session.add(media)
    await db_session.commit()
    await db_session.refresh(media)

    # Request media
    res = await client.get(
        f"/api/miniapp/v1/properties/{prop.id}/media/{media.id}",
        headers=headers,
    )
    assert res.status_code == 200
    assert "image/" in res.headers["content-type"]
    assert "public, max-age=" in res.headers["cache-control"]

    # Invalid media ID -> 404
    res_bad = await client.get(f"/api/miniapp/v1/properties/{prop.id}/media/99999", headers=headers)
    assert res_bad.status_code == 404


@pytest.mark.asyncio
async def test_unapproved_property_statuses_matrix_rejected(
    miniapp_client: tuple[AsyncClient, dict[str, str], User],
    db_session: AsyncSession,
) -> None:
    """Verify that all non-approved property statuses are completely inaccessible."""
    client, headers, user = miniapp_client
    non_approved_statuses = [
        "draft",
        "submitted",
        "under_review",
        "rejected",
        "archived",
        "sold",
        "rented",
    ]

    future_date = (datetime.now(UTC) + timedelta(days=3)).date().isoformat()

    for status_val in non_approved_statuses:
        prop = await create_test_property(
            db_session,
            user.id,
            status=status_val,
            latitude=Decimal("41.2850"),
            longitude=Decimal("69.2150"),
        )

        # 1. Direct GET details -> 404
        res_detail = await client.get(
            f"/api/miniapp/v1/properties/{prop.id}",
            headers=headers,
        )
        assert res_detail.status_code == 404, (
            f"Status {status_val} was accessible via GET /properties/{prop.id}"
        )

        # 2. Map properties -> not present
        res_map = await client.get("/api/miniapp/v1/map/properties", headers=headers)
        assert res_map.status_code == 200
        map_ids = [m["id"] for m in res_map.json()]
        assert prop.id not in map_ids, f"Status {status_val} leaked into /map/properties"

        # 3. Favorite -> 404
        res_fav = await client.post(f"/api/miniapp/v1/favorites/{prop.id}", headers=headers)
        assert res_fav.status_code == 404, f"Status {status_val} allowed favorite"

        # 4. Viewing request -> 404
        res_view = await client.post(
            f"/api/miniapp/v1/properties/{prop.id}/viewing-request",
            json={"preferred_date": future_date, "preferred_time": "10:00 - 12:00"},
            headers=headers,
        )
        assert res_view.status_code == 404, f"Status {status_val} allowed viewing request"

        # 5. Broker contact -> 404
        res_broker = await client.post(
            f"/api/miniapp/v1/properties/{prop.id}/broker-contact",
            json={"customer_comment": "Hello"},
            headers=headers,
        )
        assert res_broker.status_code == 404, f"Status {status_val} allowed broker contact"


@pytest.mark.asyncio
async def test_media_idor_cross_property_rejected(
    miniapp_client: tuple[AsyncClient, dict[str, str], User],
    db_session: AsyncSession,
) -> None:
    """Verify that requesting Property A with Media B (belonging to Property B) fails with 404."""
    client, headers, user = miniapp_client
    prop_a = await create_test_property(db_session, user.id, status="approved")
    prop_b = await create_test_property(db_session, user.id, status="approved")

    media_b = PropertyMedia(
        property_id=prop_b.id,
        telegram_file_id="tg_file_prop_b",
        telegram_file_unique_id="unique_prop_b",
        media_type="photo",
        sort_order=0,
    )
    db_session.add(media_b)
    await db_session.commit()
    await db_session.refresh(media_b)

    # Cross-property media access must fail with 404
    res_idor = await client.get(
        f"/api/miniapp/v1/properties/{prop_a.id}/media/{media_b.id}",
        headers=headers,
    )
    assert res_idor.status_code == 404


@pytest.mark.asyncio
async def test_favorites_user_isolation_and_idempotency(
    miniapp_client: tuple[AsyncClient, dict[str, str], User],
    db_session: AsyncSession,
) -> None:
    """Verify that User A cannot view User B favorites, and favorite toggles are idempotent."""
    client, headers_a, user_a = miniapp_client
    prop = await create_test_property(db_session, user_a.id, status="approved")

    # User B
    user_b_tg = {"id": 99887766, "first_name": "UserB", "username": "user_b"}
    init_data_b = make_init_data(TEST_BOT_TOKEN, user_b_tg)
    headers_b = {"Authorization": f"tma {init_data_b}"}

    # User A favorites property
    res_add1 = await client.post(f"/api/miniapp/v1/favorites/{prop.id}", headers=headers_a)
    assert res_add1.status_code == 200
    assert res_add1.json()["is_favorite"] is True

    # User A favorites same property again (idempotent)
    res_add2 = await client.post(f"/api/miniapp/v1/favorites/{prop.id}", headers=headers_a)
    assert res_add2.status_code == 200
    assert res_add2.json()["is_favorite"] is True

    # User B list favorites -> must be empty
    res_b_favs = await client.get("/api/miniapp/v1/favorites", headers=headers_b)
    assert res_b_favs.status_code == 200
    assert len(res_b_favs.json()) == 0

    # User A list favorites -> has 1 item
    res_a_favs = await client.get("/api/miniapp/v1/favorites", headers=headers_a)
    assert res_a_favs.status_code == 200
    assert len(res_a_favs.json()) == 1

    # User A deletes favorite
    res_del1 = await client.delete(f"/api/miniapp/v1/favorites/{prop.id}", headers=headers_a)
    assert res_del1.status_code == 200
    assert res_del1.json()["is_favorite"] is False

    # User A deletes again (idempotent)
    res_del2 = await client.delete(f"/api/miniapp/v1/favorites/{prop.id}", headers=headers_a)
    assert res_del2.status_code == 200
    assert res_del2.json()["is_favorite"] is False


@pytest.mark.asyncio
async def test_viewing_request_input_validation(
    miniapp_client: tuple[AsyncClient, dict[str, str], User],
    db_session: AsyncSession,
) -> None:
    """Verify input validation for viewing requests (past date, oversized comments)."""
    client, headers, user = miniapp_client
    prop = await create_test_property(db_session, user.id, status="approved")

    # Past date rejected
    past_date = (datetime.now(UTC) - timedelta(days=2)).date().isoformat()
    res_past = await client.post(
        f"/api/miniapp/v1/properties/{prop.id}/viewing-request",
        json={"preferred_date": past_date, "preferred_time": "10:00 - 12:00"},
        headers=headers,
    )
    assert res_past.status_code in (400, 422)

    # Oversized customer_comment (> 500 chars) rejected by Pydantic
    future_date = (datetime.now(UTC) + timedelta(days=2)).date().isoformat()
    res_long = await client.post(
        f"/api/miniapp/v1/properties/{prop.id}/viewing-request",
        json={
            "preferred_date": future_date,
            "preferred_time": "10:00 - 12:00",
            "customer_comment": "A" * 600,
        },
        headers=headers,
    )
    assert res_long.status_code == 422


@pytest.mark.asyncio
async def test_rate_limiter_exceeded_returns_429(
    miniapp_client: tuple[AsyncClient, dict[str, str], User],
    db_session: AsyncSession,
) -> None:
    """Verify rate limiter blocks abusive repeated calls with 429 Too Many Requests."""
    from app.api.routes.miniapp import _RATE_LIMIT_BUCKETS

    client, headers, user = miniapp_client
    prop = await create_test_property(db_session, user.id, status="approved")

    # Fill rate limit bucket directly for test
    _RATE_LIMIT_BUCKETS[f"broker_{user.id}"] = [time.time()] * 15

    res = await client.post(
        f"/api/miniapp/v1/properties/{prop.id}/broker-contact",
        json={"customer_comment": "Flood"},
        headers=headers,
    )
    assert res.status_code == 429
    assert res.json()["detail"]["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    # Clean up bucket
    _RATE_LIMIT_BUCKETS.pop(f"broker_{user.id}", None)
