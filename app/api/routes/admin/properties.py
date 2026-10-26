"""Admin property management and moderation routes."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db_session
from app.api.schemas.admin import (
    AdminPropertyDetail,
    AdminPropertyItem,
    AdminPropertyMediaItem,
    AdminPropertyOwnerInfo,
    PaginatedResponse,
    PropertyModerationRequest,
)
from app.logging import get_logger
from app.models.property import Property
from app.models.user import User
from app.services.admin_auth_service import AdminAuthService
from app.services.admin_rbac import (
    PERM_PROPERTIES_ARCHIVE,
    PERM_PROPERTIES_MODERATE,
    PERM_PROPERTIES_VIEW,
    has_permission,
    require_permission,
    verify_csrf_token,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/properties", tags=["Admin Properties"])


@router.get("", response_model=PaginatedResponse)
async def list_properties(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    property_type: str | None = None,
    district: str | None = None,
    search: str | None = Query(default=None, max_length=100),
    sort_by: str = Query(default="created_at", pattern="^(created_at|price|rooms|total_area)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_permission(PERM_PROPERTIES_VIEW)),
) -> PaginatedResponse:
    """Return paginated list of properties with server-side filters and sorting."""
    stmt = select(Property)

    if status_filter:
        stmt = stmt.where(Property.status == status_filter)
    if property_type:
        stmt = stmt.where(Property.property_type == property_type)
    if district:
        stmt = stmt.where(Property.district == district)
    if search:
        search_pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            (Property.title.ilike(search_pattern))
            | (Property.district.ilike(search_pattern))
            | (Property.address.ilike(search_pattern))
        )

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one() or 0

    # Sorting with strict allowlist
    sort_col = getattr(Property, sort_by)
    if sort_order == "desc":
        stmt = stmt.order_by(sort_col.desc())
    else:
        stmt = stmt.order_by(sort_col.asc())

    # Pagination
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await session.execute(stmt)
    properties = result.scalars().all()

    items = [
        AdminPropertyItem(
            id=p.id,
            title=p.title,
            property_type=p.property_type,
            listing_type=p.listing_type,
            status=p.status,
            region=p.region,
            district=p.district,
            price=p.price,
            currency=p.currency,
            rooms=p.rooms,
            total_area=p.total_area,
            created_at=p.created_at,
            submitted_at=p.submitted_at,
            rejection_reason=p.rejection_reason,
        )
        for p in properties
    ]

    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{property_id}", response_model=AdminPropertyDetail)
async def get_property_detail(
    property_id: int,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_PROPERTIES_VIEW)),
) -> AdminPropertyDetail:
    """Fetch complete property details, media, and safe owner information."""
    stmt = (
        select(Property)
        .options(
            selectinload(Property.media),
            selectinload(Property.owner),
        )
        .where(Property.id == property_id)
    )
    result = await session.execute(stmt)
    prop = result.scalar_one_or_none()

    if not prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Property not found."
        )

    # Safe media URLs (using API media proxy, never raw bot token or telegram paths)
    media_items = [
        AdminPropertyMediaItem(
            id=m.id,
            file_type=m.media_type,
            safe_url=f"/api/miniapp/v1/properties/media/{m.id}",
            is_main=(m.sort_order == 0),
        )
        for m in prop.media
    ]

    # Owner PII: only authorized staff (moderators or full staff) receive phone numbers
    owner_info = None
    if prop.owner:
        can_see_pii = has_permission(staff_user, PERM_PROPERTIES_MODERATE)
        fn = prop.owner.first_name or ""
        ln = prop.owner.last_name or ""
        owner_name = f"{fn} {ln}".strip() or f"User #{prop.owner.id}"
        owner_phone = prop.owner.phone if can_see_pii else None
        owner_info = AdminPropertyOwnerInfo(
            id=prop.owner.id,
            name=owner_name,
            phone=owner_phone,
        )

    return AdminPropertyDetail(
        id=prop.id,
        title=prop.title,
        property_type=prop.property_type,
        listing_type=prop.listing_type,
        status=prop.status,
        region=prop.region,
        district=prop.district,
        price=prop.price,
        currency=prop.currency,
        rooms=prop.rooms,
        total_area=prop.total_area,
        created_at=prop.created_at,
        submitted_at=prop.submitted_at,
        rejection_reason=prop.rejection_reason,
        description=prop.description,
        address=prop.address,
        condition=prop.condition,
        has_furniture=prop.has_furniture,
        cadastre_status=prop.cadastre_status,
        media=media_items,
        owner=owner_info,
    )


@router.post("/{property_id}/approve", status_code=status.HTTP_200_OK)
async def approve_property(
    property_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_PROPERTIES_MODERATE)),
    _: None = Depends(verify_csrf_token),
) -> dict[str, str]:
    """Approve property for public listing using existing domain status rules."""
    prop = await session.get(Property, property_id)
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found.")

    if prop.status not in ("pending_approval", "rejected", "draft"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve property in '{prop.status}' status.",
        )

    old_status = prop.status
    now = datetime.now(UTC)
    prop.status = "approved"
    prop.approved_at = now
    prop.approved_by_user_id = staff_user.id
    prop.rejection_reason = None

    client_ip = request.client.host if request.client else None
    await AdminAuthService.record_audit_event(
        session,
        actor_user_id=staff_user.id,
        action="property.approve",
        entity_type="property",
        entity_id=prop.id,
        metadata={"previous_status": old_status, "new_status": "approved"},
        ip_address=client_ip,
    )

    await session.commit()
    logger.info("Property id=%d approved by staff user_id=%d", prop.id, staff_user.id)
    return {"status": "ok", "message": f"Property #{prop.id} approved successfully"}


@router.post("/{property_id}/reject", status_code=status.HTTP_200_OK)
async def reject_property(
    property_id: int,
    request: Request,
    body: PropertyModerationRequest,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_PROPERTIES_MODERATE)),
    _: None = Depends(verify_csrf_token),
) -> dict[str, str]:
    """Reject property with explanatory rejection reason."""
    prop = await session.get(Property, property_id)
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found.")

    if prop.status not in ("pending_approval", "approved", "draft"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject property in '{prop.status}' status.",
        )

    clean_reason = (body.reason or "").strip()
    if len(clean_reason) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rejection reason must be at least 5 characters long.",
        )

    old_status = prop.status
    now = datetime.now(UTC)
    prop.status = "rejected"
    prop.rejected_at = now
    prop.rejection_reason = clean_reason

    client_ip = request.client.host if request.client else None
    await AdminAuthService.record_audit_event(
        session,
        actor_user_id=staff_user.id,
        action="property.reject",
        entity_type="property",
        entity_id=prop.id,
        metadata={"previous_status": old_status, "new_status": "rejected", "reason": clean_reason},
        ip_address=client_ip,
    )

    await session.commit()
    logger.info("Property id=%d rejected by staff user_id=%d", prop.id, staff_user.id)
    return {"status": "ok", "message": f"Property #{prop.id} rejected"}


@router.post("/{property_id}/archive", status_code=status.HTTP_200_OK)
async def archive_property(
    property_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_PROPERTIES_ARCHIVE)),
    _: None = Depends(verify_csrf_token),
) -> dict[str, str]:
    """Archive property listing."""
    prop = await session.get(Property, property_id)
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found.")

    if prop.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Property is already archived.",
        )

    previous_status = prop.status
    prop.status = "archived"

    client_ip = request.client.host if request.client else None
    await AdminAuthService.record_audit_event(
        session,
        actor_user_id=staff_user.id,
        action="property.archive",
        entity_type="property",
        entity_id=prop.id,
        metadata={"previous_status": previous_status, "new_status": "archived"},
        ip_address=client_ip,
    )

    await session.commit()
    logger.info("Property id=%d archived by staff user_id=%d", prop.id, staff_user.id)
    return {"status": "ok", "message": f"Property #{prop.id} archived"}
