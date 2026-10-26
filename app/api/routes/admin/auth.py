"""Admin authentication routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.api.schemas.admin import StaffLoginRequest, StaffUserResponse
from app.config import Settings, get_settings
from app.logging import get_logger
from app.models.admin_auth import AdminSession
from app.models.user import User
from app.services.admin_auth_service import AdminAuthService
from app.services.admin_rbac import (
    get_current_staff_user,
    get_staff_permissions,
    verify_csrf_token,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Admin Auth"])


@router.post("/login", response_model=StaffUserResponse)
async def login(
    request: Request,
    response: Response,
    body: StaffLoginRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> StaffUserResponse:
    """Authenticate staff user and issue HttpOnly session cookie."""
    auth_service = AdminAuthService(settings)
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    try:
        user, raw_session_token, csrf_token = await auth_service.authenticate_staff(
            session,
            username=body.username,
            password=body.password,
            ip_address=client_ip,
            user_agent=user_agent,
        )
    except ValueError as e:
        logger.warning("Staff login failed for username='%s': %s", body.username, e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e

    # Set HttpOnly, Secure, SameSite session cookie
    response.set_cookie(
        key=settings.admin_session_cookie_name,
        value=raw_session_token,
        max_age=settings.admin_session_max_age_seconds,
        httponly=True,
        secure=settings.admin_session_cookie_secure,
        samesite="lax",
        path="/",
    )

    roles = [r.name for r in user.roles]
    permissions = sorted(get_staff_permissions(user))

    return StaffUserResponse(
        id=user.id,
        username=body.username,
        first_name=user.first_name,
        last_name=user.last_name,
        roles=roles,
        permissions=permissions,
        csrf_token=csrf_token,
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    response: Response,
    auth_data: tuple[User, AdminSession] = Depends(get_current_staff_user),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    _: None = Depends(verify_csrf_token),
) -> dict[str, str]:
    """Revoke active session and delete session cookie."""
    user, admin_session = auth_data
    auth_service = AdminAuthService(settings)

    cookie_val = request.cookies.get(settings.admin_session_cookie_name)
    auth_header = request.headers.get("Authorization")
    raw_token = cookie_val or (
        auth_header.split(" ", 1)[1]
        if auth_header and auth_header.startswith("Bearer ")
        else ""
    )

    client_ip = request.client.host if request.client else None
    if raw_token:
        await auth_service.revoke_session(
            session,
            raw_session_token=raw_token,
            actor_user_id=user.id,
            ip_address=client_ip,
        )

    response.delete_cookie(
        key=settings.admin_session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.admin_session_cookie_secure,
        samesite="lax",
    )

    return {"status": "ok", "message": "Successfully logged out"}


@router.get("/me", response_model=StaffUserResponse)
async def get_me(
    auth_data: tuple[User, AdminSession] = Depends(get_current_staff_user),
    session: AsyncSession = Depends(get_db_session),
) -> StaffUserResponse:
    """Return current authenticated staff profile and permissions."""
    user, admin_session = auth_data

    # Fetch staff username from credentials
    from sqlalchemy import select

    from app.models.admin_auth import StaffCredential

    stmt = select(StaffCredential.username).where(StaffCredential.user_id == user.id)
    username = (await session.execute(stmt)).scalar_one_or_none() or f"staff_{user.id}"

    roles = [r.name for r in user.roles]
    permissions = sorted(get_staff_permissions(user))

    return StaffUserResponse(
        id=user.id,
        username=username,
        first_name=user.first_name,
        last_name=user.last_name,
        roles=roles,
        permissions=permissions,
        csrf_token=admin_session.csrf_token,
    )
