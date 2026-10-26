"""Tests for Admin Settings: Staff Username and Password Modification."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.config import get_settings
from app.models.admin_auth import AdminAuditEvent, AdminSession, StaffCredential
from app.models.role import Role
from app.models.user import User
from app.services.admin_auth_service import AdminAuthService


@pytest.fixture(autouse=True)
def setup_admin_db_dependencies(db_session: AsyncSession):
    async def override_get_db_session():
        yield db_session

    from app.main import app

    app.dependency_overrides[get_db_session] = override_get_db_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def settings_test_context(db_session: AsyncSession):
    # Create roles
    super_role = Role(name="superadmin", description="Super administrator")
    head_role = Role(name="head_broker", description="Head broker")
    db_session.add_all([super_role, head_role])
    await db_session.flush()

    # User 1: superadmin
    admin_user = User(
        telegram_id=990001,
        first_name="Super",
        last_name="Boss",
        is_active=True,
    )
    admin_user.roles.append(super_role)

    # User 2: head broker
    broker_user = User(
        telegram_id=990002,
        first_name="Broker",
        last_name="Alice",
        is_active=True,
    )
    broker_user.roles.append(head_role)

    db_session.add_all([admin_user, broker_user])
    await db_session.flush()

    auth_service = AdminAuthService(get_settings())
    await auth_service.create_or_update_staff_credential(
        db_session,
        user_id=admin_user.id,
        username="admin_boss",
        password="SuperPassword123!",
    )
    await auth_service.create_or_update_staff_credential(
        db_session,
        user_id=broker_user.id,
        username="broker_alice",
        password="AlicePassword123!",
    )

    return {
        "admin_user": admin_user,
        "broker_user": broker_user,
    }


async def _login_helper(client: AsyncClient, username: str, password: str) -> str:
    resp = await client.post(
        "/api/admin/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["csrf_token"]


@pytest.mark.asyncio
async def test_update_username_success(
    async_client: AsyncClient, settings_test_context, db_session: AsyncSession
):
    """Test successful username update by current staff user."""
    csrf_token = await _login_helper(async_client, "admin_boss", "SuperPassword123!")

    resp = await async_client.patch(
        "/api/admin/v1/auth/username",
        headers={"x-csrf-token": csrf_token},
        json={"new_username": "admin_chief"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "admin_chief"

    # Verify DB updated
    admin_user = settings_test_context["admin_user"]
    cred = (
        await db_session.execute(
            select(StaffCredential).where(StaffCredential.user_id == admin_user.id)
        )
    ).scalar_one()
    assert cred.username == "admin_chief"

    # Verify GET /me reflects updated username
    me_resp = await async_client.get("/api/admin/v1/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "admin_chief"

    # Verify audit event recorded
    audit = (
        await db_session.execute(
            select(AdminAuditEvent).where(
                AdminAuditEvent.action == "staff.username_change",
                AdminAuditEvent.actor_user_id == admin_user.id,
            )
        )
    ).scalar_one()
    assert "old_username" in str(audit.safe_metadata_json)
    assert "admin_boss" in str(audit.safe_metadata_json)
    assert "admin_chief" in str(audit.safe_metadata_json)


@pytest.mark.asyncio
@pytest.mark.usefixtures("settings_test_context")
async def test_update_username_duplicate_rejected(
    async_client: AsyncClient,
):
    """Test that choosing an already-existing username is rejected."""
    csrf_token = await _login_helper(async_client, "admin_boss", "SuperPassword123!")

    # Try duplicate of broker_alice (case-insensitive)
    resp = await async_client.patch(
        "/api/admin/v1/auth/username",
        headers={"x-csrf-token": csrf_token},
        json={"new_username": "Broker_Alice"},
    )
    assert resp.status_code == 400
    assert "band" in resp.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.usefixtures("settings_test_context")
async def test_update_username_security_guards(
    async_client: AsyncClient,
):
    """Test unauthenticated, CSRF missing, and extra field rejection on username update."""
    # 1. Unauthenticated -> 401
    resp_unauth = await async_client.patch(
        "/api/admin/v1/auth/username",
        json={"new_username": "hacker_name"},
    )
    assert resp_unauth.status_code == 401

    # Login
    csrf_token = await _login_helper(async_client, "admin_boss", "SuperPassword123!")

    # 2. Missing CSRF -> 403
    resp_no_csrf = await async_client.patch(
        "/api/admin/v1/auth/username",
        json={"new_username": "hacker_name"},
    )
    assert resp_no_csrf.status_code == 403

    # 3. Extra fields -> 422
    resp_extra = await async_client.patch(
        "/api/admin/v1/auth/username",
        headers={"x-csrf-token": csrf_token},
        json={"new_username": "valid_name", "is_admin": True},
    )
    assert resp_extra.status_code == 422


@pytest.mark.asyncio
async def test_update_password_success_and_revocation(
    async_client: AsyncClient, settings_test_context, db_session: AsyncSession
):
    """Test password update hashes with scrypt, revokes all sessions, and deletes cookie."""
    csrf_token = await _login_helper(async_client, "admin_boss", "SuperPassword123!")
    admin_user = settings_test_context["admin_user"]

    new_password = "BrandNewPassword123!"
    resp = await async_client.post(
        "/api/admin/v1/auth/password",
        headers={"x-csrf-token": csrf_token},
        json={
            "current_password": "SuperPassword123!",
            "new_password": new_password,
            "new_password_confirm": new_password,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert "password" not in resp.json()
    assert "hash" not in str(resp.json())

    # Verify all sessions revoked in database
    sessions = (
        (
            await db_session.execute(
                select(AdminSession).where(AdminSession.user_id == admin_user.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(sessions) > 0
    assert all(s.is_revoked is True for s in sessions)

    # Verify previous session cannot access /me
    me_resp = await async_client.get("/api/admin/v1/auth/me")
    assert me_resp.status_code == 401

    # Verify old password no longer works
    old_login = await async_client.post(
        "/api/admin/v1/auth/login",
        json={"username": "admin_boss", "password": "SuperPassword123!"},
    )
    assert old_login.status_code == 401

    # Verify new password works
    new_login = await async_client.post(
        "/api/admin/v1/auth/login",
        json={"username": "admin_boss", "password": new_password},
    )
    assert new_login.status_code == 200

    # Verify audit log does not leak password or hash
    audit = (
        await db_session.execute(
            select(AdminAuditEvent).where(
                AdminAuditEvent.action == "staff.password_change",
                AdminAuditEvent.actor_user_id == admin_user.id,
            )
        )
    ).scalar_one()
    assert new_password not in str(audit.safe_metadata_json)
    assert "SuperPassword123!" not in str(audit.safe_metadata_json)


@pytest.mark.asyncio
@pytest.mark.usefixtures("settings_test_context")
async def test_update_password_validation_and_guards(
    async_client: AsyncClient,
):
    """Test wrong current password, mismatch, weak password, and extra fields."""
    csrf_token = await _login_helper(async_client, "admin_boss", "SuperPassword123!")

    # 1. Wrong current password -> 400
    resp_wrong = await async_client.post(
        "/api/admin/v1/auth/password",
        headers={"x-csrf-token": csrf_token},
        json={
            "current_password": "WrongPassword!",
            "new_password": "ValidNewPassword123!",
            "new_password_confirm": "ValidNewPassword123!",
        },
    )
    assert resp_wrong.status_code == 400
    assert "noto'g'ri" in resp_wrong.json()["detail"].lower()

    # 2. Confirmation mismatch -> 400
    resp_mismatch = await async_client.post(
        "/api/admin/v1/auth/password",
        headers={"x-csrf-token": csrf_token},
        json={
            "current_password": "SuperPassword123!",
            "new_password": "ValidNewPassword123!",
            "new_password_confirm": "MismatchedPassword123!",
        },
    )
    assert resp_mismatch.status_code == 400
    assert "mos kelmadi" in resp_mismatch.json()["detail"].lower()

    # 3. Too short password (< 8 chars) -> 422
    resp_short = await async_client.post(
        "/api/admin/v1/auth/password",
        headers={"x-csrf-token": csrf_token},
        json={
            "current_password": "SuperPassword123!",
            "new_password": "short",
            "new_password_confirm": "short",
        },
    )
    assert resp_short.status_code == 422

    # 4. Extra fields -> 422
    resp_extra = await async_client.post(
        "/api/admin/v1/auth/password",
        headers={"x-csrf-token": csrf_token},
        json={
            "current_password": "SuperPassword123!",
            "new_password": "ValidNewPassword123!",
            "new_password_confirm": "ValidNewPassword123!",
            "admin_override": True,
        },
    )
    assert resp_extra.status_code == 422
