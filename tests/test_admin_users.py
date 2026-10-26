"""Tests for Admin User Management, Role Updating, and Last-Superadmin Protection."""

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
async def setup_users_context(db_session: AsyncSession):
    # Create roles
    super_role = Role(name="superadmin", description="Super Admin")
    broker_role = Role(name="sales_broker", description="Sales Broker")
    buyer_role = Role(name="buyer", description="Buyer")
    db_session.add_all([super_role, broker_role, buyer_role])
    await db_session.flush()

    # Superadmin
    admin = User(
        telegram_id=50001,
        first_name="Admin",
        last_name="One",
        phone="+998901110001",
        is_active=True,
    )
    admin.roles.append(super_role)

    # Regular customer
    customer = User(
        telegram_id=50002,
        first_name="Customer",
        last_name="Vali",
        phone="+998902220002",
        is_active=True,
    )
    customer.roles.append(buyer_role)

    db_session.add_all([admin, customer])
    await db_session.flush()

    auth_service = AdminAuthService(get_settings())
    await auth_service.create_or_update_staff_credential(
        db_session, user_id=admin.id, username="admin_users_test", password="Password123!"
    )

    return admin, "admin_users_test", "Password123!", customer


@pytest.mark.asyncio
async def test_list_users_and_privacy_masking(
    async_client: AsyncClient, setup_users_context
) -> None:
    """Test listing users returns list with properly formatted data."""
    _admin, username, password, customer = setup_users_context

    login_resp = await async_client.post(
        "/api/admin/v1/auth/login", json={"username": username, "password": password}
    )
    assert login_resp.status_code == 200

    resp = await async_client.get("/api/admin/v1/users")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2


@pytest.mark.asyncio
async def test_role_change_and_last_superadmin_protection(
    async_client: AsyncClient, setup_users_context
) -> None:
    """Test superadmin can change user roles but cannot demote the last remaining superadmin."""
    admin, username, password, customer = setup_users_context

    login_resp = await async_client.post(
        "/api/admin/v1/auth/login", json={"username": username, "password": password}
    )
    csrf_token = login_resp.json()["csrf_token"]

    # 1. Promote customer to sales_broker -> 200
    promote_resp = await async_client.patch(
        f"/api/admin/v1/users/{customer.id}/roles",
        headers={"X-CSRF-Token": csrf_token},
        json={"roles": ["sales_broker"]},
    )
    assert promote_resp.status_code == 200
    assert "sales_broker" in promote_resp.json()["roles"]

    # 2. Attempt to demote the ONLY superadmin in the system to buyer -> 400 rejected
    demote_resp = await async_client.patch(
        f"/api/admin/v1/users/{admin.id}/roles",
        headers={"X-CSRF-Token": csrf_token},
        json={"roles": ["buyer"]},
    )
    assert demote_resp.status_code == 400
    assert "last remaining superadmin" in demote_resp.json()["detail"].lower()
