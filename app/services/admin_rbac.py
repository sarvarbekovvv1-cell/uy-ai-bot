"""Role-Based Access Control (RBAC), Permission Matrix, and Auth Dependencies for Admin Panel."""

import hmac
from collections.abc import Callable

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.config import Settings, get_settings
from app.logging import get_logger
from app.models.admin_auth import AdminSession
from app.models.user import User
from app.services.admin_auth_service import AdminAuthService

logger = get_logger(__name__)

# Canonical Permissions
PERM_DASHBOARD_VIEW = "dashboard.view"
PERM_PROPERTIES_VIEW = "properties.view"
PERM_PROPERTIES_MODERATE = "properties.moderate"
PERM_PROPERTIES_ARCHIVE = "properties.archive"
PERM_USERS_VIEW = "users.view"
PERM_USERS_MANAGE_ROLES = "users.manage_roles"
PERM_BROKERS_VIEW = "brokers.view"
PERM_BROKERS_MANAGE = "brokers.manage"
PERM_LEADS_VIEW = "leads.view"
PERM_LEADS_ASSIGN = "leads.assign"
PERM_LEADS_CHANGE_STAGE = "leads.change_stage"
PERM_LEADS_ADD_NOTE = "leads.add_note"
PERM_VIEWINGS_VIEW = "viewings.view"
PERM_VIEWINGS_MANAGE = "viewings.manage"
PERM_CRM_VIEW = "crm.view"
PERM_CRM_RETRY = "crm.retry"
PERM_AI_VIEW_METRICS = "ai.view_safe_metrics"
PERM_AUDIT_VIEW = "audit.view"

ALL_PERMISSIONS = {
    PERM_DASHBOARD_VIEW,
    PERM_PROPERTIES_VIEW,
    PERM_PROPERTIES_MODERATE,
    PERM_PROPERTIES_ARCHIVE,
    PERM_USERS_VIEW,
    PERM_USERS_MANAGE_ROLES,
    PERM_BROKERS_VIEW,
    PERM_BROKERS_MANAGE,
    PERM_LEADS_VIEW,
    PERM_LEADS_ASSIGN,
    PERM_LEADS_CHANGE_STAGE,
    PERM_LEADS_ADD_NOTE,
    PERM_VIEWINGS_VIEW,
    PERM_VIEWINGS_MANAGE,
    PERM_CRM_VIEW,
    PERM_CRM_RETRY,
    PERM_AI_VIEW_METRICS,
    PERM_AUDIT_VIEW,
}

# Role to Permissions Mapping (Default Deny: unknown role -> empty set)
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "superadmin": ALL_PERMISSIONS,
    "head_broker": {
        PERM_DASHBOARD_VIEW,
        PERM_PROPERTIES_VIEW,
        PERM_PROPERTIES_MODERATE,
        PERM_PROPERTIES_ARCHIVE,
        PERM_USERS_VIEW,
        PERM_BROKERS_VIEW,
        PERM_BROKERS_MANAGE,
        PERM_LEADS_VIEW,
        PERM_LEADS_ASSIGN,
        PERM_LEADS_CHANGE_STAGE,
        PERM_LEADS_ADD_NOTE,
        PERM_VIEWINGS_VIEW,
        PERM_VIEWINGS_MANAGE,
        PERM_CRM_VIEW,
        PERM_AI_VIEW_METRICS,
        PERM_AUDIT_VIEW,
    },
    "sales_broker": {
        PERM_DASHBOARD_VIEW,
        PERM_PROPERTIES_VIEW,
        PERM_LEADS_VIEW,
        PERM_LEADS_CHANGE_STAGE,
        PERM_LEADS_ADD_NOTE,
        PERM_VIEWINGS_VIEW,
        PERM_VIEWINGS_MANAGE,
    },
    "rental_broker": {
        PERM_DASHBOARD_VIEW,
        PERM_PROPERTIES_VIEW,
        PERM_LEADS_VIEW,
        PERM_LEADS_CHANGE_STAGE,
        PERM_LEADS_ADD_NOTE,
        PERM_VIEWINGS_VIEW,
        PERM_VIEWINGS_MANAGE,
    },
    "crm_operator": {
        PERM_DASHBOARD_VIEW,
        PERM_LEADS_VIEW,
        PERM_LEADS_CHANGE_STAGE,
        PERM_LEADS_ADD_NOTE,
        PERM_VIEWINGS_VIEW,
        PERM_CRM_VIEW,
        PERM_CRM_RETRY,
        PERM_AUDIT_VIEW,
    },
    "marketing_specialist": {
        PERM_DASHBOARD_VIEW,
        PERM_PROPERTIES_VIEW,
        PERM_LEADS_VIEW,
        PERM_AI_VIEW_METRICS,
    },
    # Customer roles: strictly zero permissions (default deny)
    "property_owner": set(),
    "buyer": set(),
    "tenant": set(),
}


def get_staff_permissions(user: User) -> set[str]:
    """Calculate effective permissions for a user across all assigned roles."""
    perms: set[str] = set()
    for role in user.roles:
        role_name = role.name
        if role_name in ROLE_PERMISSIONS:
            perms.update(ROLE_PERMISSIONS[role_name])
    return perms


def has_permission(user: User, permission: str) -> bool:
    """Check if user has a specific permission."""
    return permission in get_staff_permissions(user)


async def get_current_staff_user(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    uyai_admin_session: str | None = Cookie(default=None, alias="uyai_admin_session"),
) -> tuple[User, AdminSession]:
    """FastAPI dependency authenticating staff user from session cookie.

    Also supports Authorization: Bearer <token> fallback for API/testing convenience.
    """
    token = uyai_admin_session
    if not token:
        # Check Authorization header: Bearer <token>
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
        )

    auth_service = AdminAuthService(settings)
    auth_result = await auth_service.get_staff_from_session(session, token)
    if not auth_result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please log in again.",
        )

    user, admin_session = auth_result

    # Verify user has at least one staff permission (default deny for customers)
    perms = get_staff_permissions(user)
    if not perms:
        logger.warning("User id=%d has active session but zero staff permissions", user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Staff permissions required.",
        )

    return user, admin_session


async def verify_csrf_token(
    request: Request,
    auth_data: tuple[User, AdminSession] = Depends(get_current_staff_user),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> None:
    """Enforce CSRF verification on state-changing requests."""
    # Read-only HTTP methods are exempt from CSRF
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    _user, admin_session = auth_data

    cookie_val = request.cookies.get("uyai_admin_session")
    auth_header = request.headers.get("Authorization")

    # If authenticated purely via Authorization: Bearer header (no ambient cookie),
    # CSRF is not applicable as cross-site browser requests cannot set custom Authorization headers.
    if not cookie_val and auth_header and auth_header.startswith("Bearer "):
        return

    if not x_csrf_token or not hmac.compare_digest(x_csrf_token, admin_session.csrf_token):
        logger.warning("CSRF token validation failed for user_id=%d", _user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing CSRF token.",
        )


def require_permission(permission: str) -> Callable:
    """Dependency factory checking that active staff user has the requested permission."""

    async def _permission_checker(
        auth_data: tuple[User, AdminSession] = Depends(get_current_staff_user),
    ) -> User:
        user, _session = auth_data
        if not has_permission(user, permission):
            logger.warning(
                "Permission denied: user id=%d lacks '%s'", user.id, permission
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: Requires '{permission}'.",
            )
        return user

    return _permission_checker
