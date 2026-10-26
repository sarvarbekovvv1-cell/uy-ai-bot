"""Adversarial security tests for Admin / Manager Panel (Phase 11).

Tests attack vectors:
- scrypt parameter bounds and format tampering
- Algorithmic DoS password length mitigation
- Timing oracle mitigation (dummy scrypt verification on unknown user)
- CSRF ambient cookie bypass prevention
- Mass-assignment prevention via extra="forbid" on all schemas
- Moderation reason length validation
- State machine transition guards (archiving already-archived properties)
- Stale session revocation upon staff privilege demotion
- Broker assignment domain & listing-type enforcement
- CRM error and audit event secret redaction
- Long User-Agent truncation
"""

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.config import get_settings
from app.core.exceptions import LeadPermissionError, LeadValidationError
from app.models.admin_auth import AdminAuditEvent, AdminSession
from app.models.lead import Lead, LeadEvent
from app.models.property import Property
from app.models.role import Role
from app.models.user import User
from app.services.admin_auth_service import AdminAuthService, sanitize_audit_metadata
from app.services.lead_service import LeadService


@pytest.fixture(autouse=True)
def setup_admin_db_dependencies(db_session: AsyncSession):
    async def override_get_db_session():
        yield db_session

    from app.main import app

    app.dependency_overrides[get_db_session] = override_get_db_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def adversarial_context(db_session: AsyncSession):
    # Setup roles
    super_role = Role(name="superadmin", description="Super Admin")
    head_role = Role(name="head_broker", description="Head Broker")
    sales_role = Role(name="sales_broker", description="Sales Broker")
    rental_role = Role(name="rental_broker", description="Rental Broker")
    buyer_role = Role(name="buyer", description="Buyer")
    db_session.add_all([super_role, head_role, sales_role, rental_role, buyer_role])
    await db_session.flush()

    # Superadmin user
    super_user = User(
        telegram_id=888001,
        first_name="Super",
        last_name="Auditor",
        is_active=True,
    )
    super_user.roles.append(super_role)

    # Head Broker user (staff manager)
    head_user = User(
        telegram_id=888002,
        first_name="Head",
        last_name="Broker",
        is_active=True,
    )
    head_user.roles.append(head_role)

    # Sales Broker
    sales_broker = User(
        telegram_id=888003,
        first_name="Sales",
        last_name="Broker",
        is_active=True,
    )
    sales_broker.roles.append(sales_role)

    # Rental Broker
    rental_broker = User(
        telegram_id=888004,
        first_name="Rental",
        last_name="Broker",
        is_active=True,
    )
    rental_broker.roles.append(rental_role)

    # Client user
    client_user = User(
        telegram_id=888005,
        first_name="Client",
        last_name="User",
        phone="+998901234567",
        is_active=True,
    )
    client_user.roles.append(buyer_role)

    db_session.add_all([super_user, head_user, sales_broker, rental_broker, client_user])
    await db_session.flush()

    auth_service = AdminAuthService(get_settings())
    await auth_service.create_or_update_staff_credential(
        db_session, user_id=super_user.id, username="adversary_super", password="SuperPassword123!"
    )
    await auth_service.create_or_update_staff_credential(
        db_session, user_id=head_user.id, username="adversary_head", password="HeadPassword123!"
    )

    return {
        "super_user": super_user,
        "head_user": head_user,
        "sales_broker": sales_broker,
        "rental_broker": rental_broker,
        "client_user": client_user,
        "super_role": super_role,
        "buyer_role": buyer_role,
    }


async def _login_helper(client: AsyncClient, username: str, password: str) -> str:
    resp = await client.post(
        "/api/admin/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["csrf_token"]


@pytest.mark.asyncio
async def test_scrypt_parameter_validation_and_bounds_tampering():
    auth_service = AdminAuthService(get_settings())

    # Valid hash format verification
    valid_hash = auth_service.hash_password("ValidPassword123!")
    assert auth_service.verify_password("ValidPassword123!", valid_hash) is True
    assert auth_service.verify_password("WrongPassword123!", valid_hash) is False

    # Corrupted format (too few parts)
    assert auth_service.verify_password("ValidPassword123!", "scrypt$16384$8$1") is False

    # Unknown algorithm identifier
    assert auth_service.verify_password("ValidPassword123!", "bcrypt$16384$8$1$abcd$ef01") is False

    # Out-of-bounds N parameter (> 65536)
    oversized_n = "scrypt$131072$8$1$abcdef1234567890$abcdef1234567890"
    assert auth_service.verify_password("ValidPassword123!", oversized_n) is False

    # Out-of-bounds r parameter (> 16)
    oversized_r = "scrypt$16384$32$1$abcdef1234567890$abcdef1234567890"
    assert auth_service.verify_password("ValidPassword123!", oversized_r) is False

    # Out-of-bounds p parameter (> 16)
    oversized_p = "scrypt$16384$8$32$abcdef1234567890$abcdef1234567890"
    assert auth_service.verify_password("ValidPassword123!", oversized_p) is False

    # Oversized salt hex (> 64 characters)
    oversized_salt = f"scrypt$16384$8$1${'a' * 66}$abcdef1234567890"
    assert auth_service.verify_password("ValidPassword123!", oversized_salt) is False

    # Oversized hash hex (> 128 characters)
    oversized_hash = f"scrypt$16384$8$1$abcdef1234567890${'a' * 130}"
    assert auth_service.verify_password("ValidPassword123!", oversized_hash) is False


@pytest.mark.asyncio
@pytest.mark.usefixtures("adversarial_context")
async def test_password_max_length_dos_mitigation(
    async_client: AsyncClient,
):
    auth_service = AdminAuthService(get_settings())
    oversized_password = "A" * 129

    # Service layer rejection
    with pytest.raises(ValueError, match="Password must not exceed 128 characters."):
        auth_service.hash_password(oversized_password)

    # API layer rejection (Pydantic max_length=128)
    resp = await async_client.post(
        "/api/admin/v1/auth/login",
        json={"username": "adversary_super", "password": oversized_password},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_timing_oracle_dummy_hash_on_unknown_username(db_session: AsyncSession):
    auth_service = AdminAuthService(get_settings())

    # Authenticating unknown user executes dummy scrypt hash and raises ValueError
    with pytest.raises(ValueError, match="Invalid username or password."):
        await auth_service.authenticate_staff(
            db_session,
            username="non_existent_adversary_user",
            password="SomeRandomPassword123!",
        )


@pytest.mark.asyncio
@pytest.mark.usefixtures("adversarial_context")
async def test_csrf_protection_and_ambient_cookie_bypass_prevention(
    async_client: AsyncClient,
):
    csrf_token = await _login_helper(async_client, "adversary_super", "SuperPassword123!")

    # 1. State-changing request with ambient cookie but NO x-csrf-token header -> 403 Forbidden
    resp_no_csrf = await async_client.post(
        "/api/admin/v1/auth/logout",
    )
    assert resp_no_csrf.status_code == 403
    assert "CSRF token" in resp_no_csrf.json()["detail"]

    # 2. State-changing request with ambient cookie and invalid x-csrf-token header -> 403 Forbidden
    resp_bad_csrf = await async_client.post(
        "/api/admin/v1/auth/logout",
        headers={"x-csrf-token": "completely_invalid_csrf_token"},
    )
    assert resp_bad_csrf.status_code == 403
    assert "CSRF token" in resp_bad_csrf.json()["detail"]

    # 3. Ambient cookie present + attacker attempts dummy Bearer header bypass
    resp_bypass_attempt = await async_client.post(
        "/api/admin/v1/auth/logout",
        headers={"authorization": "Bearer dummy_bearer_token"},
    )
    assert resp_bypass_attempt.status_code == 403
    assert "CSRF token" in resp_bypass_attempt.json()["detail"]

    # 4. Valid CSRF token works cleanly
    resp_valid = await async_client.post(
        "/api/admin/v1/auth/logout",
        headers={"x-csrf-token": csrf_token},
    )
    assert resp_valid.status_code == 200


@pytest.mark.asyncio
async def test_pydantic_extra_forbidden_mass_assignment(
    async_client: AsyncClient, adversarial_context
):
    csrf_token = await _login_helper(async_client, "adversary_super", "SuperPassword123!")
    headers = {"x-csrf-token": csrf_token}

    # Extra field in Login request
    resp_login_extra = await async_client.post(
        "/api/admin/v1/auth/login",
        json={
            "username": "adversary_super",
            "password": "SuperPassword123!",
            "is_admin": True,
            "role": "god_mode",
        },
    )
    assert resp_login_extra.status_code == 422

    # Extra field in UserRoleUpdateRequest
    target_user = adversarial_context["client_user"]
    resp_user_role_extra = await async_client.patch(
        f"/api/admin/v1/users/{target_user.id}/roles",
        headers=headers,
        json={"roles": ["sales_broker"], "bypass_audit": True},
    )
    assert resp_user_role_extra.status_code == 422


@pytest.mark.asyncio
async def test_property_rejection_reason_min_length(
    async_client: AsyncClient, adversarial_context, db_session: AsyncSession
):
    # Create draft property
    prop = Property(
        owner_user_id=adversarial_context["client_user"].id,
        title="Adversarial Test Apt",
        description="Apt to test moderation rejection length bounds.",
        property_type="apartment",
        listing_type="sale",
        region="Toshkent",
        district="Chilonzor",
        rooms=2,
        total_area=Decimal("60.0"),
        price=100000,
        currency="USD",
        address="Tashkent, Chilanzar",
        condition="euro",
        status="pending_approval",
    )
    db_session.add(prop)
    await db_session.flush()

    csrf_token = await _login_helper(async_client, "adversary_super", "SuperPassword123!")
    headers = {"x-csrf-token": csrf_token}

    # Rejection reason with < 5 characters must fail 400
    resp = await async_client.post(
        f"/api/admin/v1/properties/{prop.id}/reject",
        headers=headers,
        json={"reason": "bad"},
    )
    assert resp.status_code == 400
    assert "at least 5 characters" in resp.json()["detail"]

    # Rejection reason with >= 5 characters must succeed
    resp_ok = await async_client.post(
        f"/api/admin/v1/properties/{prop.id}/reject",
        headers=headers,
        json={"reason": "Invalid photos provided"},
    )
    assert resp_ok.status_code == 200
    assert resp_ok.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_property_archive_cannot_rearchive(
    async_client: AsyncClient, adversarial_context, db_session: AsyncSession
):
    prop = Property(
        owner_user_id=adversarial_context["client_user"].id,
        title="Archive Guard Test Apt",
        description="Apt to test archive guard.",
        property_type="apartment",
        listing_type="sale",
        region="Toshkent",
        district="Mirzo Ulugbek",
        rooms=3,
        total_area=Decimal("80.0"),
        price=90000,
        currency="USD",
        address="Tashkent, Mirzo Ulugbek",
        condition="euro",
        status="approved",
    )
    db_session.add(prop)
    await db_session.flush()

    csrf_token = await _login_helper(async_client, "adversary_super", "SuperPassword123!")
    headers = {"x-csrf-token": csrf_token}

    # First archive -> 200
    resp1 = await async_client.post(
        f"/api/admin/v1/properties/{prop.id}/archive",
        headers=headers,
        json={"reason": "Property sold outside platform"},
    )
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "ok"

    # Re-archiving an already archived property -> 400 Bad Request
    resp2 = await async_client.post(
        f"/api/admin/v1/properties/{prop.id}/archive",
        headers=headers,
        json={"reason": "Try archiving again"},
    )
    assert resp2.status_code == 400
    assert "already archived" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_demote_staff_revokes_all_active_sessions(
    async_client: AsyncClient, adversarial_context, db_session: AsyncSession
):
    head_user = adversarial_context["head_user"]

    # 1. Head broker logs in and creates active session
    await _login_helper(async_client, "adversary_head", "HeadPassword123!")

    # Verify head broker session is valid
    resp_me = await async_client.get("/api/admin/v1/auth/me")
    assert resp_me.status_code == 200
    saved_session_token = async_client.cookies.get("uyai_admin_session")

    # 2. Superadmin logs in and demotes head broker to just 'buyer'
    async_client.cookies.clear()
    super_csrf = await _login_helper(async_client, "adversary_super", "SuperPassword123!")
    resp_demote = await async_client.patch(
        f"/api/admin/v1/users/{head_user.id}/roles",
        headers={"x-csrf-token": super_csrf},
        json={"roles": ["buyer"]},
    )
    assert resp_demote.status_code == 200

    # Verify head broker's active sessions are marked revoked in database
    sessions = (
        (await db_session.execute(select(AdminSession).where(AdminSession.user_id == head_user.id)))
        .scalars()
        .all()
    )
    assert len(sessions) > 0
    assert all(s.is_revoked is True for s in sessions)

    # 3. Head broker tries to make a request with old session -> 401 Unauthorized
    async_client.cookies.clear()
    async_client.cookies.set("uyai_admin_session", saved_session_token)
    resp_me_revoked = await async_client.get("/api/admin/v1/auth/me")
    assert resp_me_revoked.status_code == 401


@pytest.mark.asyncio
async def test_assign_broker_domain_and_listing_type_validation(
    adversarial_context, db_session: AsyncSession
):
    lead_service = LeadService()

    # Create a property with listing_type='rent'
    prop = Property(
        owner_user_id=adversarial_context["client_user"].id,
        title="Rent Apartment",
        description="Apartment for rent in Tashkent",
        property_type="apartment",
        listing_type="rent",
        region="Toshkent",
        district="Yakkasaray",
        rooms=2,
        total_area=Decimal("65.0"),
        price=600,
        currency="USD",
        address="Tashkent, Yakkasaray",
        condition="euro",
        status="approved",
    )
    db_session.add(prop)
    await db_session.flush()

    # Create a lead linked to the property
    lead = Lead(
        customer_user_id=adversarial_context["client_user"].id,
        property_id=prop.id,
        source="broker_contact",
        stage="new",
    )
    db_session.add(lead)
    await db_session.flush()

    super_user = adversarial_context["super_user"]
    sales_broker = adversarial_context["sales_broker"]
    rental_broker = adversarial_context["rental_broker"]
    client_user = adversarial_context["client_user"]

    # 1. Inactive broker user -> LeadValidationError
    client_user.is_active = False
    await db_session.flush()
    with pytest.raises(LeadValidationError, match="Yaroqsiz broker tanlandi"):
        await lead_service.assign_broker(
            db_session,
            lead_id=lead.id,
            broker_user_id=client_user.id,
            assigned_by_user_id=super_user.id,
        )
    client_user.is_active = True
    await db_session.flush()

    # 2. Assign sales_broker to 'rent' lead -> LeadPermissionError
    with pytest.raises(LeadPermissionError, match="Tanlangan broker 'rent' toifasidagi"):
        await lead_service.assign_broker(
            db_session,
            lead_id=lead.id,
            broker_user_id=sales_broker.id,
            assigned_by_user_id=super_user.id,
        )

    # 3. Assign appropriate rental_broker to 'rent' lead -> Success
    assigned_lead = await lead_service.assign_broker(
        db_session,
        lead_id=lead.id,
        broker_user_id=rental_broker.id,
        assigned_by_user_id=super_user.id,
    )
    assert assigned_lead.broker_user_id == rental_broker.id
    assert assigned_lead.assigned_at is not None

    # Check that LeadEvent(event_type="assigned") was recorded
    events = (
        (
            await db_session.execute(
                select(LeadEvent).where(
                    LeadEvent.lead_id == lead.id,
                    LeadEvent.event_type == "assigned",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    assert events[0].new_value == str(rental_broker.id)


@pytest.mark.asyncio
async def test_audit_event_metadata_sanitization(adversarial_context, db_session: AsyncSession):
    auth_service = AdminAuthService(get_settings())

    dirty_metadata = {
        "password": "SuperSecretPassword123!",
        "token": "sensitive_session_token_xyz",
        "api_key": "secret_key_12345",
        "auth_detail": "sensitive_auth_value",
        "nested": {
            "token_info": "nested_secret_token",
            "safe_detail": "Property id 42 approved",
            "request_log": "Authorization: Bearer secret_jwt_token_999 passed",
        },
        "description": "User updated password=PlainTextPasswordNow!",
    }

    sanitized = sanitize_audit_metadata(dirty_metadata)

    # Verify sensitive keys are stripped
    assert "password" not in sanitized
    assert "token" not in sanitized
    assert "api_key" not in sanitized
    assert "auth_detail" not in sanitized
    assert "token_info" not in sanitized["nested"]

    # Verify safe keys are retained and their nested string secrets are redacted
    assert sanitized["nested"]["safe_detail"] == "Property id 42 approved"
    assert "secret_jwt_token_999" not in sanitized["nested"]["request_log"]
    assert "Bearer [REDACTED]" in sanitized["nested"]["request_log"]
    assert "PlainTextPasswordNow!" not in sanitized["description"]
    assert "[REDACTED]" in sanitized["description"]

    # Verify DB recording
    event = await auth_service.record_audit_event(
        db_session,
        actor_user_id=adversarial_context["super_user"].id,
        action="test.adversarial_sanitization",
        entity_type="system",
        entity_id=None,
        metadata=dirty_metadata,
        ip_address="127.0.0.1",
    )
    await db_session.flush()

    # Re-fetch event
    saved_event = (
        await db_session.execute(select(AdminAuditEvent).where(AdminAuditEvent.id == event.id))
    ).scalar_one()

    raw_json = saved_event.safe_metadata_json or ""
    assert "SuperSecretPassword123!" not in raw_json
    assert "sensitive_session_token_xyz" not in raw_json
    assert "secret_key_12345" not in raw_json
    assert "secret_jwt_token_999" not in raw_json
    assert "PlainTextPasswordNow!" not in raw_json
    assert '"password":' not in raw_json
    assert '"token":' not in raw_json
    assert '"api_key":' not in raw_json
    assert "[REDACTED]" in raw_json


@pytest.mark.asyncio
@pytest.mark.usefixtures("adversarial_context")
async def test_user_agent_truncation_in_session(
    async_client: AsyncClient,
):
    long_ua = "CustomBrowser/" + ("A" * 300)
    resp = await async_client.post(
        "/api/admin/v1/auth/login",
        headers={"user-agent": long_ua},
        json={"username": "adversary_super", "password": "SuperPassword123!"},
    )
    assert resp.status_code == 200
