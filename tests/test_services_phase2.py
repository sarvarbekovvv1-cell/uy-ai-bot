"""Tests for Phase 2 user and role services."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import DEFAULT_CUSTOMER_ROLE, UserRole
from app.models.user import User
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService


@pytest.mark.asyncio
async def test_duplicate_start_idempotency_at_service_level() -> None:
    """20. Verify repeated start/initialization does not create duplicate user records."""
    mock_user_repo = AsyncMock(spec=UserRepository)
    mock_role_repo = AsyncMock(spec=RoleRepository)
    mock_session = AsyncMock(spec=AsyncSession)

    existing_user = User(
        id=1,
        telegram_id=987654321,
        first_name="ExistingUser",
        language="uz",
        phone="+998901234567",
    )

    # First call: user already exists
    mock_user_repo.get_by_telegram_id.return_value = existing_user
    mock_user_repo.update.return_value = existing_user

    service = UserService(user_repo=mock_user_repo, role_repo=mock_role_repo)

    result = await service.initialize_user(
        mock_session,
        telegram_id=987654321,
        first_name="ExistingUserUpdated",
    )

    # Verify no new user is created
    mock_user_repo.create.assert_not_called()
    assert result.id == 1
    assert result.telegram_id == 987654321


@pytest.mark.asyncio
async def test_default_buyer_role_assignment() -> None:
    """21. Verify completing registration assigns default customer role (buyer)."""
    mock_user_repo = AsyncMock(spec=UserRepository)
    mock_role_repo = AsyncMock(spec=RoleRepository)
    mock_session = AsyncMock(spec=AsyncSession)

    user = User(id=42, telegram_id=55555, language="uz")
    mock_user_repo.get_by_telegram_id.return_value = user
    mock_user_repo.update.return_value = user

    service = UserService(user_repo=mock_user_repo, role_repo=mock_role_repo)

    await service.complete_registration(
        mock_session,
        telegram_id=55555,
        phone="+998901234567",
        is_verified=True,
    )

    # Verify assign_role called with DEFAULT_CUSTOMER_ROLE ('buyer')
    mock_role_repo.assign_role.assert_awaited_once_with(mock_session, 42, DEFAULT_CUSTOMER_ROLE)


@pytest.mark.asyncio
async def test_privileged_roles_cannot_be_self_assigned() -> None:
    """22. Verify privileged roles (superadmin, broker, etc.) cannot be assigned publicly."""
    mock_user_repo = AsyncMock(spec=UserRepository)
    mock_role_repo = AsyncMock(spec=RoleRepository)
    mock_session = AsyncMock(spec=AsyncSession)

    service = UserService(user_repo=mock_user_repo, role_repo=mock_role_repo)

    # Attempt to self-assign superadmin without admin privileges
    success_superadmin = await service.assign_role_safely(
        mock_session, user_id=1, role_name="superadmin", requested_by_admin=False
    )
    assert success_superadmin is False
    mock_role_repo.assign_role.assert_not_called()

    # Attempt to self-assign head_broker without admin privileges
    success_broker = await service.assign_role_safely(
        mock_session, user_id=1, role_name="head_broker", requested_by_admin=False
    )
    assert success_broker is False
    mock_role_repo.assign_role.assert_not_called()

    # Admin requested assignment succeeds
    mock_role_repo.assign_role.return_value = UserRole(user_id=1, role_id=2)
    success_admin_action = await service.assign_role_safely(
        mock_session, user_id=1, role_name="sales_broker", requested_by_admin=True
    )
    assert success_admin_action is True
    mock_role_repo.assign_role.assert_awaited_once_with(mock_session, 1, "sales_broker")
