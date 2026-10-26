"""Admin property management and moderation routes."""

import base64
import os
import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db_session
from app.api.schemas.admin import (
    AdminPropertyCreateRequest,
    AdminPropertyDetail,
    AdminPropertyItem,
    AdminPropertyMediaItem,
    AdminPropertyOwnerInfo,
    PaginatedResponse,
    PropertyModerationRequest,
)
from app.logging import get_logger
from app.models.property import Property
from app.models.property_media import PropertyMedia
from app.models.user import User
from app.services.admin_auth_service import AdminAuthService
from app.services.admin_rbac import (
    PERM_PROPERTIES_ARCHIVE,
    PERM_PROPERTIES_CREATE,
    PERM_PROPERTIES_MODERATE,
    PERM_PROPERTIES_VIEW,
    has_permission,
    require_permission,
    verify_csrf_token,
)
from app.services.media_storage import get_media_storage
from app.services.property_service import PropertyService
from app.services.rate_limiter import rate_limit

logger = get_logger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
MEDIA_CACHE_DIR = os.path.join(BASE_DIR, ".cache", "media")
os.makedirs(MEDIA_CACHE_DIR, exist_ok=True)

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB

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

    if status_filter and status_filter != "all":
        if status_filter in ("pending_approval", "submitted", "under_review"):
            stmt = stmt.where(
                Property.status.in_(("submitted", "under_review", "pending_approval"))
            )
        else:
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found.")

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

    if prop.status not in ("pending_approval", "submitted", "under_review", "rejected", "draft"):
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

    if prop.status not in ("pending_approval", "submitted", "under_review", "approved", "draft"):
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


@router.post("/upload-media", status_code=status.HTTP_201_CREATED)
async def upload_property_media(
    request: Request,
    staff_user: User = Depends(require_permission(PERM_PROPERTIES_CREATE)),
    _: None = Depends(verify_csrf_token),
    __: None = Depends(rate_limit("media_upload", max_requests=30, window_seconds=60)),
) -> dict[str, str]:
    """Upload property photo with MIME and magic bytes security checks."""
    content_type_header = request.headers.get("content-type", "").lower()

    if content_type_header.startswith("application/json"):
        try:
            payload = await request.json()
            mime_type = payload.get("content_type", "")
            data_b64 = payload.get("data_base64", "")
            content = base64.b64decode(data_b64)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON/base64 payload: {e}",
            ) from e
    else:
        mime_type = content_type_header.split(";")[0].strip()
        content = await request.body()

    storage = get_media_storage()
    try:
        safe_uid = storage.save_media(content, mime_type)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    logger.info("Media %s uploaded by staff user_id=%d", safe_uid, staff_user.id)

    return {
        "media_unique_id": safe_uid,
        "file_type": "photo",
        "safe_url": f"/api/admin/v1/properties/media/{safe_uid}",
    }


@router.get("/media/{media_unique_id}")
async def get_uploaded_media(
    media_unique_id: str,
    _: User = Depends(require_permission(PERM_PROPERTIES_VIEW)),
) -> Response:
    """Stream uploaded media for preview in Admin panel with path traversal protection."""
    storage = get_media_storage()
    item = storage.get_media(media_unique_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found.",
        )

    data, mime = item
    return Response(
        content=data,
        media_type=mime,
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("", response_model=AdminPropertyDetail, status_code=status.HTTP_201_CREATED)
async def create_property(
    request: Request,
    body: AdminPropertyCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_PROPERTIES_CREATE)),
    _: None = Depends(verify_csrf_token),
) -> AdminPropertyDetail:
    """Create a new property listing with optional auto-approval and media attachment."""
    # 1. Check auto-approve permissions
    if body.auto_approve and not has_permission(staff_user, PERM_PROPERTIES_MODERATE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to auto-approve property listings.",
        )

    # 2. Resolve owner
    resolved_owner_id = staff_user.id
    if body.owner_user_id is not None:
        target_owner = await session.get(User, body.owner_user_id)
        if not target_owner:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Specified owner user #{body.owner_user_id} does not exist.",
            )
        resolved_owner_id = target_owner.id

    prop_service = PropertyService()
    try:
        prop_service.validate_property_attributes(
            listing_type=body.listing_type,
            property_type=body.property_type,
            rooms=body.rooms,
            total_area=body.total_area,
            condition=body.condition,
            price=body.price,
            currency=body.currency,
            cadastre_status=body.cadastre_status,
            floor=body.floor,
            total_floors=body.total_floors,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    # 3. Create property entity
    prop = await prop_service.create_draft(
        session,
        owner_user_id=resolved_owner_id,
        listing_type=body.listing_type,
        property_type=body.property_type,
        region=body.region,
        district=body.district,
        address=body.address,
        rooms=body.rooms,
        total_area=body.total_area,
        living_area=body.living_area,
        floor=body.floor,
        total_floors=body.total_floors,
        condition=body.condition,
        construction_type=body.construction_type,
        has_furniture=body.has_furniture,
        cadastre_status=body.cadastre_status,
        price=body.price,
        currency=body.currency,
        negotiable=body.negotiable,
        latitude=body.latitude,
        longitude=body.longitude,
        title=body.title,
        description=body.description,
    )

    # 3. Associate media records
    media_items: list[PropertyMedia] = []
    for idx, uid in enumerate(body.media_unique_ids):
        safe_uid = re.sub(r"[^a-zA-Z0-9_-]", "", uid)
        pm = PropertyMedia(
            property_id=prop.id,
            telegram_file_id=f"admin_file_{safe_uid}",
            telegram_file_unique_id=safe_uid,
            media_type="photo",
            sort_order=idx + 1,
        )
        session.add(pm)
        media_items.append(pm)

    # 4. Status assignment
    now_utc = datetime.now(UTC)
    if body.auto_approve:
        prop.status = "approved"
        prop.approved_at = now_utc
        prop.approved_by_user_id = staff_user.id
    else:
        prop.status = "submitted"
        prop.submitted_at = now_utc

    # 5. Audit log
    client_ip = request.client.host if request.client else None
    await AdminAuthService.record_audit_event(
        session,
        actor_user_id=staff_user.id,
        action="property.create_manual",
        entity_type="property",
        entity_id=prop.id,
        metadata={
            "listing_type": prop.listing_type,
            "property_type": prop.property_type,
            "district": prop.district,
            "price": float(prop.price),
            "status": prop.status,
            "auto_approve": body.auto_approve,
            "media_count": len(media_items),
        },
        ip_address=client_ip,
    )

    await session.commit()
    await session.refresh(prop)

    # Build response detail
    media_resp = [
        AdminPropertyMediaItem(
            id=m.id,
            file_type=m.media_type,
            safe_url=f"/api/miniapp/v1/properties/media/{m.id}",
            is_main=(idx == 0),
        )
        for idx, m in enumerate(media_items)
    ]

    owner_entity = target_owner if (body.owner_user_id is not None and target_owner) else staff_user
    owner_name = (
        f"{owner_entity.first_name or ''} {owner_entity.last_name or ''}".strip()
        or f"User #{owner_entity.id}"
    )

    return AdminPropertyDetail(
        id=prop.id,
        title=prop.title,
        property_type=prop.property_type,
        listing_type=prop.listing_type,
        status=prop.status,
        region=prop.region,
        district=prop.district,
        address=prop.address,
        price=prop.price,
        currency=prop.currency,
        rooms=prop.rooms,
        total_area=prop.total_area,
        condition=prop.condition,
        has_furniture=prop.has_furniture,
        cadastre_status=prop.cadastre_status,
        description=prop.description,
        created_at=prop.created_at,
        submitted_at=prop.submitted_at,
        rejection_reason=prop.rejection_reason,
        owner=AdminPropertyOwnerInfo(
            id=owner_entity.id,
            name=owner_name,
            phone=owner_entity.phone,
        ),
        media=media_resp,
    )
