"""Admin viewing requests and appointments management routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db_session
from app.api.schemas.admin import AdminViewingItem, PaginatedResponse, ViewingActionRequest
from app.logging import get_logger
from app.models.user import User
from app.models.viewing_request import ViewingRequest
from app.services.admin_auth_service import AdminAuthService
from app.services.admin_rbac import (
    PERM_VIEWINGS_MANAGE,
    PERM_VIEWINGS_VIEW,
    require_permission,
    verify_csrf_token,
)
from app.services.viewing_request_service import ViewingRequestService

logger = get_logger(__name__)

router = APIRouter(prefix="/viewings", tags=["Admin Viewings"])


@router.get("", response_model=PaginatedResponse)
async def list_viewings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    broker_id: int | None = None,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_permission(PERM_VIEWINGS_VIEW)),
) -> PaginatedResponse:
    """Return paginated viewing requests."""
    stmt = (
        select(ViewingRequest)
        .options(
            selectinload(ViewingRequest.customer),
            selectinload(ViewingRequest.property),
            selectinload(ViewingRequest.broker),
        )
    )

    if status_filter:
        stmt = stmt.where(ViewingRequest.status == status_filter)
    if broker_id:
        stmt = stmt.where(ViewingRequest.broker_user_id == broker_id)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one() or 0

    stmt = (
        stmt.order_by(ViewingRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    viewings = result.scalars().all()

    items = []
    for v in viewings:
        customer_name = (
            f"{v.customer.first_name or ''} {v.customer.last_name or ''}".strip()
            or f"Customer #{v.customer_user_id}"
        )
        broker_name = (
            f"{v.broker.first_name or ''} {v.broker.last_name or ''}".strip()
            if v.broker
            else None
        )
        prop_title = v.property.title if v.property else f"Property #{v.property_id}"

        items.append(
            AdminViewingItem(
                id=v.id,
                customer_id=v.customer_user_id,
                customer_name=customer_name,
                property_id=v.property_id,
                property_title=prop_title,
                broker_id=v.broker_user_id,
                broker_name=broker_name,
                preferred_date=v.preferred_date,
                preferred_time=v.preferred_time,
                status=v.status,
                outcome=v.outcome,
                customer_comment=v.customer_comment,
                created_at=v.created_at,
            )
        )

    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/{viewing_id}/accept", status_code=status.HTTP_200_OK)
async def accept_viewing(
    viewing_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_VIEWINGS_MANAGE)),
    _: None = Depends(verify_csrf_token),
) -> dict[str, str]:
    """Accept viewing request."""
    service = ViewingRequestService()
    try:
        req = await service.accept_request(
            session, request_id=viewing_id, broker_user_id=staff_user.id
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    client_ip = request.client.host if request.client else None
    await AdminAuthService.record_audit_event(
        session,
        actor_user_id=staff_user.id,
        action="viewing.accept",
        entity_type="viewing_request",
        entity_id=viewing_id,
        metadata={"status": "accepted"},
        ip_address=client_ip,
    )
    await session.commit()
    return {"status": "ok", "message": f"Viewing #{req.id} accepted"}


@router.post("/{viewing_id}/reject", status_code=status.HTTP_200_OK)
async def reject_viewing(
    viewing_id: int,
    request: Request,
    body: ViewingActionRequest,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_VIEWINGS_MANAGE)),
    _: None = Depends(verify_csrf_token),
) -> dict[str, str]:
    """Reject viewing request."""
    service = ViewingRequestService()
    try:
        req = await service.reject_request(
            session,
            request_id=viewing_id,
            broker_user_id=staff_user.id,
            reason=body.notes,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    client_ip = request.client.host if request.client else None
    await AdminAuthService.record_audit_event(
        session,
        actor_user_id=staff_user.id,
        action="viewing.reject",
        entity_type="viewing_request",
        entity_id=viewing_id,
        metadata={"reason": body.notes},
        ip_address=client_ip,
    )
    await session.commit()
    return {"status": "ok", "message": f"Viewing #{req.id} rejected"}


@router.post("/{viewing_id}/complete", status_code=status.HTTP_200_OK)
async def complete_viewing(
    viewing_id: int,
    request: Request,
    body: ViewingActionRequest,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_VIEWINGS_MANAGE)),
    _: None = Depends(verify_csrf_token),
) -> dict[str, str]:
    """Mark viewing request as completed with outcome."""
    service = ViewingRequestService()
    try:
        req = await service.complete_request(
            session,
            request_id=viewing_id,
            broker_user_id=staff_user.id,
            outcome=body.outcome or "interested",
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    client_ip = request.client.host if request.client else None
    await AdminAuthService.record_audit_event(
        session,
        actor_user_id=staff_user.id,
        action="viewing.complete",
        entity_type="viewing_request",
        entity_id=viewing_id,
        metadata={"outcome": req.outcome},
        ip_address=client_ip,
    )
    await session.commit()
    return {"status": "ok", "message": f"Viewing #{req.id} completed"}


@router.post("/{viewing_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_viewing(
    viewing_id: int,
    request: Request,
    body: ViewingActionRequest,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_VIEWINGS_MANAGE)),
    _: None = Depends(verify_csrf_token),
) -> dict[str, str]:
    """Cancel viewing request."""
    service = ViewingRequestService()
    try:
        req = await service.cancel_request(
            session,
            request_id=viewing_id,
            actor_user_id=staff_user.id,
            reason=body.notes,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    client_ip = request.client.host if request.client else None
    await AdminAuthService.record_audit_event(
        session,
        actor_user_id=staff_user.id,
        action="viewing.cancel",
        entity_type="viewing_request",
        entity_id=viewing_id,
        metadata={"reason": body.notes},
        ip_address=client_ip,
    )
    await session.commit()
    return {"status": "ok", "message": f"Viewing #{req.id} cancelled"}
