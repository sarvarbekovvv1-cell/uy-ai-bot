"""Admin CRM outbox monitoring and retry management routes."""

import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.api.schemas.admin import (
    AdminCRMEntityLinkItem,
    AdminCRMSyncEventItem,
    PaginatedResponse,
)
from app.logging import get_logger
from app.models.crm_sync import CRMEntityLink, CRMSyncEvent
from app.models.user import User
from app.services.admin_auth_service import AdminAuthService
from app.services.admin_rbac import (
    PERM_CRM_RETRY,
    PERM_CRM_VIEW,
    require_permission,
    verify_csrf_token,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/crm", tags=["Admin CRM"])


def sanitize_crm_error(err: str | None) -> str | None:
    """Sanitize error trace to guarantee zero token or secret exposure."""
    if not err:
        return None
    sanitized = re.sub(r"Bearer\s+[A-Za-z0-9_\-\.]+", "Bearer [REDACTED]", err)
    sanitized = re.sub(
        r"(refresh_token|client_secret|client_id|access_token|secret|password)=[^&\s]+",
        r"\1=[REDACTED]",
        sanitized,
        flags=re.IGNORECASE,
    )
    return sanitized


@router.get("/events", response_model=PaginatedResponse)
@router.get("/outbox", response_model=PaginatedResponse)
async def list_crm_events(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_permission(PERM_CRM_VIEW)),
) -> PaginatedResponse:
    """Return paginated CRM outbox events with sanitized errors."""
    stmt = select(CRMSyncEvent).where(CRMSyncEvent.provider == "amocrm")

    if status_filter:
        stmt = stmt.where(CRMSyncEvent.status == status_filter)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one() or 0

    stmt = (
        stmt.order_by(CRMSyncEvent.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    events = result.scalars().all()

    items = [
        AdminCRMSyncEventItem(
            id=ev.id,
            event_type=ev.event_type,
            entity_type=ev.entity_type,
            entity_id=ev.entity_id,
            status=ev.status,
            attempt_count=ev.attempt_count,
            next_attempt_at=ev.next_attempt_at,
            last_error_safe=sanitize_crm_error(ev.last_error_safe),
            created_at=ev.created_at,
            processed_at=ev.processed_at,
        )
        for ev in events
    ]

    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/events/{event_id}/retry", status_code=status.HTTP_200_OK)
@router.post("/outbox/{event_id}/retry", status_code=status.HTTP_200_OK)
async def retry_crm_event(
    event_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_CRM_RETRY)),
    _: None = Depends(verify_csrf_token),
) -> dict[str, str]:
    """Reset a failed CRM outbox event back to pending state for immediate retry."""
    event = await session.get(CRMSyncEvent, event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CRM event not found.")

    if event.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot retry event in '{event.status}' state. "
                "Only failed events can be retried."
            ),
        )

    event.status = "pending"
    event.attempt_count = 0
    event.next_attempt_at = datetime.now(UTC)
    event.last_error_safe = f"Reset by staff user_id={staff_user.id}"

    client_ip = request.client.host if request.client else None
    target_str = f"{event.entity_type}:{event.entity_id}"
    await AdminAuthService.record_audit_event(
        session,
        actor_user_id=staff_user.id,
        action="crm.retry",
        entity_type="crm_sync_event",
        entity_id=event.id,
        metadata={"event_type": event.event_type, "target_entity": target_str},
        ip_address=client_ip,
    )

    await session.commit()
    logger.info(
        "CRM outbox event id=%d reset to pending by staff user_id=%d",
        event.id,
        staff_user.id,
    )
    return {"status": "ok", "message": f"Event #{event.id} queued for retry"}


@router.get("/links", response_model=PaginatedResponse)
async def list_crm_entity_links(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    entity_type: str | None = None,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_permission(PERM_CRM_VIEW)),
) -> PaginatedResponse:
    """Return paginated mappings between internal entities and external amoCRM IDs."""
    stmt = select(CRMEntityLink).where(CRMEntityLink.provider == "amocrm")

    if entity_type:
        stmt = stmt.where(CRMEntityLink.local_entity_type == entity_type)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one() or 0

    stmt = (
        stmt.order_by(CRMEntityLink.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    links = result.scalars().all()

    items = [
        AdminCRMEntityLinkItem(
            id=lk.id,
            provider=lk.provider,
            local_entity_type=lk.local_entity_type,
            local_entity_id=lk.local_entity_id,
            external_entity_type=lk.external_entity_type,
            external_entity_id=lk.external_entity_id,
            created_at=lk.created_at,
        )
        for lk in links
    ]

    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
