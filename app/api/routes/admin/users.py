"""Admin user management and role assignment routes."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db_session
from app.api.schemas.admin import AdminUserItem, PaginatedResponse, UserRoleUpdateRequest
from app.logging import get_logger
from app.models.admin_auth import AdminSession
from app.models.role import SYSTEM_ROLES, Role, UserRole
from app.models.user import User
from app.services.admin_auth_service import AdminAuthService
from app.services.admin_rbac import (
    PERM_USERS_MANAGE_ROLES,
    PERM_USERS_VIEW,
    has_permission,
    require_permission,
    verify_csrf_token,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/users", tags=["Admin Users"])


def mask_phone_number(phone: str | None) -> str | None:
    """Mask phone number for privacy: +998901234567 -> +998 ••• •• 67."""
    if not phone or len(phone) < 6:
        return phone
    return phone[:4] + " ••• •• " + phone[-2:]


@router.get("", response_model=PaginatedResponse)
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    role: str | None = None,
    search: str | None = Query(default=None, max_length=100),
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_USERS_VIEW)),
) -> PaginatedResponse:
    """Return paginated users with role filters and privacy-sensitive phone masking."""
    stmt = select(User).options(selectinload(User.roles))

    if role:
        stmt = stmt.join(User.roles).where(Role.name == role)
    if search:
        search_pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            (User.first_name.ilike(search_pattern))
            | (User.last_name.ilike(search_pattern))
            | (User.username.ilike(search_pattern))
            | (User.phone.ilike(search_pattern))
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one() or 0

    stmt = stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(stmt)
    users = result.scalars().all()

    can_view_unmasked = has_permission(staff_user, PERM_USERS_MANAGE_ROLES)

    items = [
        AdminUserItem(
            id=u.id,
            telegram_id=u.telegram_id,
            first_name=u.first_name,
            last_name=u.last_name,
            username=u.username,
            phone=u.phone if can_view_unmasked else mask_phone_number(u.phone),
            language=u.language,
            is_active=u.is_active,
            roles=[r.name for r in u.roles],
            created_at=u.created_at,
        )
        for u in users
    ]

    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{user_id}", response_model=AdminUserItem)
async def get_user_detail(
    user_id: int,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_USERS_VIEW)),
) -> AdminUserItem:
    """Fetch user details."""
    stmt = select(User).options(selectinload(User.roles)).where(User.id == user_id)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    can_view_unmasked = has_permission(staff_user, PERM_USERS_MANAGE_ROLES)

    return AdminUserItem(
        id=user.id,
        telegram_id=user.telegram_id,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username,
        phone=user.phone if can_view_unmasked else mask_phone_number(user.phone),
        language=user.language,
        is_active=user.is_active,
        roles=[r.name for r in user.roles],
        created_at=user.created_at,
    )


@router.patch("/{user_id}/roles", status_code=status.HTTP_200_OK)
@router.put("/{user_id}/roles", status_code=status.HTTP_200_OK)
async def update_user_roles(
    user_id: int,
    request: Request,
    body: UserRoleUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_USERS_MANAGE_ROLES)),
    _: None = Depends(verify_csrf_token),
) -> dict[str, Any]:
    """Update user roles with strict validation and last-superadmin protection."""
    # 1. Validate target roles against known SYSTEM_ROLES
    invalid_roles = [r for r in body.roles if r not in SYSTEM_ROLES]
    if invalid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid roles: {invalid_roles}. Must be subset of {SYSTEM_ROLES}",
        )

    # 2. Fetch target user
    stmt = select(User).options(selectinload(User.roles)).where(User.id == user_id)
    target_user = (await session.execute(stmt)).scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    old_roles = [r.name for r in target_user.roles]

    # 3. Superadmin Protection: check if target is superadmin and being demoted
    if "superadmin" in old_roles and "superadmin" not in body.roles:
        # Count remaining superadmins in database
        superadmin_count_stmt = (
            select(func.count(UserRole.id)).join(Role).where(Role.name == "superadmin")
        )
        total_superadmins = (await session.execute(superadmin_count_stmt)).scalar_one() or 0
        if total_superadmins <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the last remaining superadmin in the system.",
            )

    # 4. Fetch Role models for target roles
    roles_stmt = select(Role).where(Role.name.in_(body.roles))
    new_role_objs = list((await session.execute(roles_stmt)).scalars().all())

    target_user.roles = new_role_objs

    # Revoke active sessions if target user was demoted from staff entirely
    staff_role_set = {
        "superadmin",
        "head_broker",
        "sales_broker",
        "rental_broker",
        "crm_operator",
        "marketing_specialist",
        "moderator",
    }
    had_staff = any(r in staff_role_set for r in old_roles)
    has_staff = any(r in staff_role_set for r in body.roles)
    if had_staff and not has_staff:
        rev_stmt = (
            update(AdminSession)
            .where(AdminSession.user_id == target_user.id)
            .values(is_revoked=True)
        )
        await session.execute(rev_stmt)
        logger.info("Revoked active staff sessions for demoted user_id=%d", target_user.id)

    # 5. Audit event
    client_ip = request.client.host if request.client else None
    await AdminAuthService.record_audit_event(
        session,
        actor_user_id=staff_user.id,
        action="user.role_change",
        entity_type="user",
        entity_id=target_user.id,
        metadata={"old_roles": old_roles, "new_roles": body.roles},
        ip_address=client_ip,
    )

    await session.commit()
    logger.info(
        "Updated roles for user_id=%d to %s by staff user_id=%d",
        target_user.id,
        body.roles,
        staff_user.id,
    )
    return {"status": "ok", "user_id": target_user.id, "roles": body.roles}
