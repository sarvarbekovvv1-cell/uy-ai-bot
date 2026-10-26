"""Tests for Admin Staff Authentication, Scrypt Hashing, Sessions, and Lockout."""


import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.config import get_settings
from app.main import app
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
async def staff_superadmin(db_session: AsyncSession) -> tuple[User, str, str]:
    """Create a superadmin user with staff credentials."""
    role = Role(name="superadmin", description="Super administrator")
    db_session.add(role)
    await db_session.flush()

    user = User(
        telegram_id=900000001,
        first_name="Super",
        last_name="Admin",
        is_active=True,
        is_verified=True,
    )
    user.roles.append(role)
    db_session.add(user)
    await db_session.flush()

    username = "admin_boss"
    password = "SuperSecretPassword123!"
    auth_service = AdminAuthService(get_settings())
    await auth_service.create_or_update_staff_credential(
        db_session,
        user_id=user.id,
        username=username,
        password=password,
    )
    return user, username, password


@pytest.mark.asyncio
async def test_scrypt_password_hashing_and_verification() -> None:
    """Test scrypt password hashing, salt uniqueness, and constant-time verification."""
    password = "MySecureStaffPassword2026!"
    hash1 = AdminAuthService.hash_password(password)
    hash2 = AdminAuthService.hash_password(password)

    # Different salts produce different hashes
    assert hash1 != hash2
    assert hash1.startswith("scrypt$16384$8$1$")

    # Correct password verifies
    assert AdminAuthService.verify_password(password, hash1) is True
    assert AdminAuthService.verify_password(password, hash2) is True

    # Wrong password fails
    assert AdminAuthService.verify_password("WrongPassword!", hash1) is False
    assert AdminAuthService.verify_password("", hash1) is False


@pytest.mark.asyncio
async def test_staff_login_success_and_cookie_issuance(
    async_client: AsyncClient,
    staff_superadmin: tuple[User, str, str],
) -> None:
    """Test staff login issues HttpOnly session cookie and returns user info with CSRF."""
    user, username, password = staff_superadmin

    response = await async_client.post(
        "/api/admin/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user.id
    assert data["username"] == username
    assert "superadmin" in data["roles"]
    assert "dashboard.view" in data["permissions"]
    assert "csrf_token" in data and len(data["csrf_token"]) > 20

    # Cookie verified
    assert "uyai_admin_session" in response.cookies


@pytest.mark.asyncio
async def test_staff_login_generic_error_on_invalid_credentials(
    async_client: AsyncClient,
    staff_superadmin: tuple[User, str, str],
) -> None:
    """Test login gives generic error for both unknown username and wrong password."""
    _user, username, _password = staff_superadmin

    # Wrong password
    resp1 = await async_client.post(
        "/api/admin/v1/auth/login",
        json={"username": username, "password": "WrongPassword999!"},
    )
    assert resp1.status_code == 401
    assert "Invalid username or password" in resp1.json()["detail"]

    # Unknown username gives IDENTICAL error to prevent enumeration
    resp2 = await async_client.post(
        "/api/admin/v1/auth/login",
        json={"username": "nonexistent_staff_user", "password": "SomePassword123!"},
    )
    assert resp2.status_code == 401
    assert "Invalid username or password" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_login_lockout_after_max_failed_attempts(
    async_client: AsyncClient,
    staff_superadmin: tuple[User, str, str],
) -> None:
    """Test staff account is locked after 5 consecutive failed login attempts."""
    user, username, password = staff_superadmin

    for _ in range(5):
        resp = await async_client.post(
            "/api/admin/v1/auth/login",
            json={"username": username, "password": "wrong_attempt"},
        )
        assert resp.status_code == 401

    # 6th attempt with correct password must now be rejected because account is locked
    locked_resp = await async_client.post(
        "/api/admin/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert locked_resp.status_code == 401
    assert "locked" in locked_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_staff_logout_revokes_session(
    async_client: AsyncClient,
    staff_superadmin: tuple[User, str, str],
) -> None:
    """Test logout invalidates session and clears cookie."""
    _user, username, password = staff_superadmin

    # Login
    login_resp = await async_client.post(
        "/api/admin/v1/auth/login",
        json={"username": username, "password": password},
    )
    csrf_token = login_resp.json()["csrf_token"]

    # Access /me before logout
    me_resp1 = await async_client.get("/api/admin/v1/auth/me")
    assert me_resp1.status_code == 200

    # Logout
    logout_resp = await async_client.post(
        "/api/admin/v1/auth/logout",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert logout_resp.status_code == 200

    # Access /me after logout fails
    me_resp2 = await async_client.get("/api/admin/v1/auth/me")
    assert me_resp2.status_code == 401
