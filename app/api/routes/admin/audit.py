"""Admin immutable audit trail routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db_session
from app.api.schemas.admin import AdminAuditEventItem, PaginatedResponse
from app.models.admin_auth import AdminAuditEvent
from app.models.user import User
from app.services.admin_rbac import PERM_AUDIT_VIEW, require_permission

router = APIRouter(prefix="/audit", tags=["Admin Audit Log"])


@router.get("", response_model=PaginatedResponse)
async def list_audit_events(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    action: str | None = None,
    entity_type: str | None = None,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_permission(PERM_AUDIT_VIEW)),
) -> PaginatedResponse:
    """Return paginated, append-only administrative audit log records."""
    stmt = select(AdminAuditEvent).options(selectinload(AdminAuditEvent.actor))

    if action:
        stmt = stmt.where(AdminAuditEvent.action == action)
    if entity_type:
        stmt = stmt.where(AdminAuditEvent.entity_type == entity_type)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one() or 0

    stmt = (
        stmt.order_by(AdminAuditEvent.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    records = result.scalars().all()

    items = []
    for r in records:
        actor_name = None
        if r.actor:
            first = r.actor.first_name or ""
            last = r.actor.last_name or ""
            actor_name = f"{first} {last}".strip() or f"User #{r.actor.id}"

        items.append(
            AdminAuditEventItem(
                id=r.id,
                actor_id=r.actor_user_id,
                actor_name=actor_name,
                action=r.action,
                entity_type=r.entity_type,
                entity_id=r.entity_id,
                metadata_json=r.safe_metadata_json,
                ip_address=r.ip_address,
                created_at=r.created_at,
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
