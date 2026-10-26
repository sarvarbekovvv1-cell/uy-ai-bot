"""Tests for Admin RBAC, Permission Matrix, Vertical Authorization, and CSRF Protection."""

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


async def create_staff_user(
    db_session: AsyncSession,
    role_name: str,
    telegram_id: int,
    username: str,
) -> tuple[User, str, str]:
    """Helper creating user with role and staff credentials."""
    role_stmt = Role.__table__.select().where(Role.name == role_name)
    existing_role = (await db_session.execute(role_stmt)).first()
    if not existing_role:
        role = Role(name=role_name, description=f"{role_name} description")
        db_session.add(role)
        await db_session.flush()
    else:
        role = await db_session.get(Role, existing_role.id)

    user = User(
        telegram_id=telegram_id,
        first_name=f"First_{role_name}",
        last_name="Staff",
        is_active=True,
        is_verified=True,
    )
    user.roles.append(role)
    db_session.add(user)
    await db_session.flush()

    password = "StaffTestPassword123!"
    auth_service = AdminAuthService(get_settings())
    await auth_service.create_or_update_staff_credential(
        db_session,
        user_id=user.id,
        username=username,
        password=password,
    )
    return user, username, password


@pytest.mark.asyncio
async def test_vertical_authorization_customer_roles_denied(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test customer roles (buyer, tenant, property_owner) cannot access Admin API."""
    for idx, customer_role in enumerate(["buyer", "tenant", "property_owner"]):
        user, username, password = await create_staff_user(
            db_session,
            customer_role,
            800000 + idx,
            f"cust_{customer_role}",
        )

        # Attempting to log into Admin Panel with customer role fails closed
        resp = await async_client.post(
            "/api/admin/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert resp.status_code == 401
        assert "Access denied" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_rbac_permission_matrix_across_staff_roles(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test permission matrix across staff roles against privileged endpoints."""
    # 1. Marketing specialist cannot retry CRM events (requires crm_operator)
    mkt_user, mkt_name, mkt_pass = await create_staff_user(
        db_session, "marketing_specialist", 70001, "mkt_user"
    )
    login_mkt = await async_client.post(
        "/api/admin/v1/auth/login",
        json={"username": mkt_name, "password": mkt_pass},
    )
    assert login_mkt.status_code == 200
    csrf_mkt = login_mkt.json()["csrf_token"]

    # Dashboard view allowed
    resp_dash = await async_client.get("/api/admin/v1/dashboard")
    assert resp_dash.status_code == 200

    # CRM retry forbidden for marketing
    resp_crm_retry = await async_client.post(
        "/api/admin/v1/crm/events/1/retry",
        headers={"X-CSRF-Token": csrf_mkt},
    )
    assert resp_crm_retry.status_code == 403

    # Logout marketing
    await async_client.post("/api/admin/v1/auth/logout", headers={"X-CSRF-Token": csrf_mkt})

    # 2. CRM Operator can access CRM section but cannot moderate properties
    crm_user, crm_name, crm_pass = await create_staff_user(
        db_session, "crm_operator", 70002, "crm_user"
    )
    login_crm = await async_client.post(
        "/api/admin/v1/auth/login",
        json={"username": crm_name, "password": crm_pass},
    )
    assert login_crm.status_code == 200
    csrf_crm = login_crm.json()["csrf_token"]

    # Properties moderate forbidden for crm_operator
    resp_prop_mod = await async_client.post(
        "/api/admin/v1/properties/1/approve",
        headers={"X-CSRF-Token": csrf_crm},
    )
    assert resp_prop_mod.status_code == 403


@pytest.mark.asyncio
async def test_csrf_protection_on_mutating_requests(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test state-changing requests reject missing or invalid X-CSRF-Token headers."""
    user, username, password = await create_staff_user(
        db_session, "superadmin", 70003, "admin_csrf"
    )
    login_resp = await async_client.post(
        "/api/admin/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert login_resp.status_code == 200

    # 1. Mutating request with NO CSRF header -> 403
    resp_no_csrf = await async_client.post("/api/admin/v1/auth/logout")
    assert resp_no_csrf.status_code == 403
    assert "CSRF" in resp_no_csrf.json()["detail"]

    # 2. Mutating request with WRONG CSRF header -> 403
    resp_wrong_csrf = await async_client.post(
        "/api/admin/v1/auth/logout",
        headers={"X-CSRF-Token": "invalid_tampered_csrf_token"},
    )
    assert resp_wrong_csrf.status_code == 403
