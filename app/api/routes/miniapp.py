"""FastAPI REST routes for Telegram Mini App."""

import os
import re
import time
from collections import defaultdict
from decimal import Decimal
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_miniapp_user
from app.config import get_settings
from app.core.exceptions import (
    DuplicateViewingRequestError,
    PropertyNotFoundError,
    PropertyUnavailableError,
    ViewingValidationError,
)
from app.database.session import get_db_session
from app.logging import get_logger
from app.models.favorite import Favorite
from app.models.property import Property
from app.models.property_media import PropertyMedia
from app.models.user import User
from app.schemas.miniapp import (
    MiniAppBrokerContactInput,
    MiniAppBrokerContactResponse,
    MiniAppFavoriteResponse,
    MiniAppMapProperty,
    MiniAppPropertyDetail,
    MiniAppPropertyListResponse,
    MiniAppPropertyMedia,
    MiniAppPropertySummary,
    MiniAppUser,
    MiniAppViewingRequestInput,
    MiniAppViewingRequestResponse,
)
from app.services.favorite_service import FavoriteService
from app.services.media_storage import get_media_storage
from app.services.property_search_service import PropertySearchService
from app.services.viewing_request_service import ViewingRequestService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/miniapp/v1", tags=["Telegram Mini App"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
MEDIA_CACHE_DIR = os.path.join(BASE_DIR, ".cache", "media")
os.makedirs(MEDIA_CACHE_DIR, exist_ok=True)

PLACEHOLDER_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">'
    b'<rect width="100%" height="100%" fill="#f1f5f9"/>'
    b'<circle cx="300" cy="180" r="40" fill="#cbd5e1"/>'
    b'<path d="M200 300 L260 220 L320 280 L370 230 L430 300 Z" fill="#94a3b8"/>'
    b'<text x="50%" y="340" dominant-baseline="middle" text-anchor="middle" fill="#64748b" '
    b'font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif" font-size="20" '
    b'font-weight="600">UyAI Real Estate</text></svg>'
)


@router.get("/me", response_model=MiniAppUser, summary="Get current authenticated Mini App user")
async def get_me(
    current_user: Annotated[User, Depends(get_current_miniapp_user)],
) -> MiniAppUser:
    """Return authenticated customer profile."""
    return MiniAppUser.model_validate(current_user)


@router.get(
    "/properties",
    response_model=MiniAppPropertyListResponse,
    summary="Search and browse approved properties",
)
async def list_properties(
    current_user: Annotated[User, Depends(get_current_miniapp_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    listing_type: str | None = Query(None, pattern="^(sale|rent)$"),
    deal_type: str | None = Query(None, pattern="^(sale|rent)$"),
    property_type: str | None = Query(None),
    region: str | None = Query(None),
    district: str | None = Query(None),
    rooms: int | None = Query(None, ge=1, le=20),
    min_price: Decimal | None = Query(None, ge=0),
    max_price: Decimal | None = Query(None, ge=0),
    currency: str | None = Query(None, pattern="^(USD|UZS)$"),
    min_area: Decimal | None = Query(None, ge=0),
    max_area: Decimal | None = Query(None, ge=0),
    sort: str = Query("newest", pattern="^(newest|price_asc|price_desc|area_asc|area_desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
) -> MiniAppPropertyListResponse:
    """Search approved listings with deterministic filtering, sorting, and pagination."""
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_PRICE_RANGE",
                    "message": "min_price cannot exceed max_price",
                }
            },
        )
    if min_area is not None and max_area is not None and min_area > max_area:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_AREA_RANGE",
                    "message": "min_area cannot exceed max_area",
                }
            },
        )

    effective_listing_type = listing_type or deal_type
    base_conditions = [
        Property.status == "approved",
    ]
    if effective_listing_type:
        base_conditions.append(Property.listing_type == effective_listing_type)
    if currency:
        base_conditions.append(Property.currency == currency)

    if property_type and property_type.lower() not in ("all", "hamma", "barchasi"):
        base_conditions.append(Property.property_type == property_type)
    if region:
        base_conditions.append(func.lower(Property.region) == region.strip().lower())
    if district:
        base_conditions.append(func.lower(Property.district) == district.strip().lower())
    if rooms is not None:
        base_conditions.append(Property.rooms == rooms)
    if min_price is not None:
        base_conditions.append(Property.price >= min_price)
    if max_price is not None:
        base_conditions.append(Property.price <= max_price)
    if min_area is not None:
        base_conditions.append(Property.total_area >= min_area)
    if max_area is not None:
        base_conditions.append(Property.total_area <= max_area)

    # Count total matching
    count_stmt = select(func.count(Property.id)).where(*base_conditions)
    total_count = (await session.execute(count_stmt)).scalar() or 0

    # Determine sorting
    if sort == "price_asc":
        order_clauses = [Property.price.asc(), Property.id.desc()]
    elif sort == "price_desc":
        order_clauses = [Property.price.desc(), Property.id.desc()]
    elif sort == "area_asc":
        order_clauses = [Property.total_area.asc(), Property.id.desc()]
    elif sort == "area_desc":
        order_clauses = [Property.total_area.desc(), Property.id.desc()]
    else:  # newest
        order_clauses = [
            Property.approved_at.desc().nullslast(),
            Property.created_at.desc(),
            Property.id.desc(),
        ]

    offset = (page - 1) * page_size
    items_stmt = (
        select(Property)
        .options(selectinload(Property.media))
        .where(*base_conditions)
        .order_by(*order_clauses)
        .offset(offset)
        .limit(page_size)
    )
    props = list((await session.execute(items_stmt)).scalars().all())

    # Query current user's favorites for returned properties
    prop_ids = [p.id for p in props]
    fav_ids: set[int] = set()
    if prop_ids:
        fav_stmt = select(Favorite.property_id).where(
            Favorite.user_id == current_user.id,
            Favorite.property_id.in_(prop_ids),
        )
        fav_ids = set((await session.execute(fav_stmt)).scalars().all())

    items = []
    for p in props:
        thumb_url = None
        if p.media:
            first_media = min(p.media, key=lambda m: m.sort_order)
            thumb_url = f"/api/miniapp/v1/properties/{p.id}/media/{first_media.id}"

        items.append(
            MiniAppPropertySummary(
                id=p.id,
                listing_type=p.listing_type,
                property_type=p.property_type,
                title=p.title or f"{p.rooms} xonali {p.property_type}",
                region=p.region,
                district=p.district,
                rooms=p.rooms,
                total_area=p.total_area,
                price=p.price,
                currency=p.currency,
                condition=p.condition,
                floor=p.floor,
                total_floors=p.total_floors,
                is_favorite=p.id in fav_ids,
                thumbnail_url=thumb_url,
                latitude=p.latitude,
                longitude=p.longitude,
            )
        )

    import math

    total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1

    return MiniAppPropertyListResponse(
        items=items,
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/properties/{property_id}",
    response_model=MiniAppPropertyDetail,
    summary="Get approved property details",
)
async def get_property_details(
    property_id: int,
    current_user: Annotated[User, Depends(get_current_miniapp_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MiniAppPropertyDetail:
    """Fetch public details for an approved property. Rejects unapproved listings."""
    search_service = PropertySearchService()
    try:
        prop = await search_service.get_approved_details(session, property_id)
    except PropertyNotFoundError as pnf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "PROPERTY_NOT_FOUND",
                    "message": "Property not found or not active.",
                }
            },
        ) from pnf

    favorite_service = FavoriteService()
    is_fav = await favorite_service.is_favorite(
        session, user_id=current_user.id, property_id=prop.id
    )

    media_items = [
        MiniAppPropertyMedia(
            id=m.id,
            media_type=m.media_type,
            sort_order=m.sort_order,
            url=f"/api/miniapp/v1/properties/{prop.id}/media/{m.id}",
        )
        for m in sorted(prop.media, key=lambda x: x.sort_order)
    ]

    return MiniAppPropertyDetail(
        id=prop.id,
        listing_type=prop.listing_type,
        property_type=prop.property_type,
        title=prop.title or f"{prop.rooms} xonali {prop.property_type}",
        description=prop.description,
        region=prop.region,
        district=prop.district,
        address=prop.address,
        rooms=prop.rooms,
        total_area=prop.total_area,
        living_area=prop.living_area,
        floor=prop.floor,
        total_floors=prop.total_floors,
        condition=prop.condition,
        construction_type=prop.construction_type,
        has_furniture=prop.has_furniture,
        cadastre_status=prop.cadastre_status,
        price=prop.price,
        currency=prop.currency,
        negotiable=prop.negotiable,
        is_favorite=is_fav,
        latitude=prop.latitude,
        longitude=prop.longitude,
        media=media_items,
        created_at=prop.created_at,
    )


@router.get(
    "/properties/{property_id}/media/{media_id}",
    summary="Securely serve property photo/media",
)
async def get_property_media(
    property_id: int,
    media_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """Stream property media with caching and Telegram proxy protection."""
    stmt = (
        select(PropertyMedia)
        .join(Property)
        .where(
            PropertyMedia.id == media_id,
            PropertyMedia.property_id == property_id,
            Property.status == "approved",
        )
    )
    media = (await session.execute(stmt)).scalar_one_or_none()
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "MEDIA_NOT_FOUND",
                    "message": "Media item not found or inaccessible.",
                }
            },
        )

    safe_uid = re.sub(r"[^a-zA-Z0-9_-]", "", media.telegram_file_unique_id or f"media_{media.id}")
    cache_path = os.path.abspath(os.path.join(MEDIA_CACHE_DIR, f"{safe_uid}.jpg"))
    if not cache_path.startswith(os.path.abspath(MEDIA_CACHE_DIR)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_MEDIA", "message": "Invalid media identifier"}},
        )

    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            data = f.read()
        return Response(
            content=data,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    settings = get_settings()
    if not settings.bot_token:
        return Response(
            content=PLACEHOLDER_SVG,
            media_type="image/svg+xml",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    # Fetch from Telegram Bot API securely
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            get_file_url = f"https://api.telegram.org/bot{settings.bot_token}/getFile"
            res = await client.get(get_file_url, params={"file_id": media.telegram_file_id})
            if res.status_code == 200:
                file_info = res.json().get("result", {})
                file_path = file_info.get("file_path")
                if file_path:
                    download_url = (
                        f"https://api.telegram.org/file/bot{settings.bot_token}/{file_path}"
                    )
                    img_res = await client.get(download_url)
                    if img_res.status_code == 200:
                        img_bytes = img_res.content
                        with open(cache_path, "wb") as f:
                            f.write(img_bytes)
                        return Response(
                            content=img_bytes,
                            media_type="image/jpeg",
                            headers={"Cache-Control": "public, max-age=86400"},
                        )
    except Exception as exc:
        logger.warning("Could not download media %s from Telegram: %s", media.id, exc)

    return Response(
        content=PLACEHOLDER_SVG,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get(
    "/properties/media/{media_unique_id}",
    summary="Stream property media by unique identifier",
)
async def get_property_media_by_uid(
    media_unique_id: str,
) -> Response:
    """Stream property media by unique identifier with caching and path traversal protection."""
    storage = get_media_storage()
    item = storage.get_media(media_unique_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "MEDIA_NOT_FOUND", "message": "Media not found"}},
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


@router.get(
    "/favorites",
    response_model=list[MiniAppPropertySummary],
    summary="Get authenticated user's favorite properties",
)
async def get_favorites(
    current_user: Annotated[User, Depends(get_current_miniapp_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[MiniAppPropertySummary]:
    """Return all active saved favorite properties for the authenticated user."""
    favorite_service = FavoriteService()
    saved_props = await favorite_service.list_saved_properties(session, user_id=current_user.id)

    items = []
    for p in saved_props:
        thumb_url = None
        if p.media:
            first_media = min(p.media, key=lambda m: m.sort_order)
            thumb_url = f"/api/miniapp/v1/properties/{p.id}/media/{first_media.id}"

        items.append(
            MiniAppPropertySummary(
                id=p.id,
                listing_type=p.listing_type,
                property_type=p.property_type,
                title=p.title or f"{p.rooms} xonali {p.property_type}",
                region=p.region,
                district=p.district,
                rooms=p.rooms,
                total_area=p.total_area,
                price=p.price,
                currency=p.currency,
                condition=p.condition,
                floor=p.floor,
                total_floors=p.total_floors,
                is_favorite=True,
                thumbnail_url=thumb_url,
                latitude=p.latitude,
                longitude=p.longitude,
            )
        )
    return items


_RATE_LIMIT_BUCKETS: dict[str, list[float]] = defaultdict(list)
_MAX_BUCKETS = 10000


def enforce_miniapp_rate_limit(key: str, max_requests: int = 20, window_seconds: int = 60) -> None:
    """Bounded in-memory rate limiter keyed by verified user ID.

    Note: Suitable for single-instance deployment. In distributed multi-replica
    production, an external Redis-backed rate limiter is recommended.
    """
    now = time.time()
    if len(_RATE_LIMIT_BUCKETS) > _MAX_BUCKETS:
        _RATE_LIMIT_BUCKETS.clear()

    timestamps = [t for t in _RATE_LIMIT_BUCKETS[key] if now - t < window_seconds]
    if len(timestamps) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests. Please wait a moment before trying again.",
                }
            },
        )
    timestamps.append(now)
    _RATE_LIMIT_BUCKETS[key] = timestamps


@router.post(
    "/favorites/{property_id}",
    response_model=MiniAppFavoriteResponse,
    summary="Add property to user favorites",
)
async def add_favorite(
    property_id: int,
    current_user: Annotated[User, Depends(get_current_miniapp_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MiniAppFavoriteResponse:
    """Save an approved property to user's favorites."""
    enforce_miniapp_rate_limit(f"fav_{current_user.id}", max_requests=30, window_seconds=60)
    favorite_service = FavoriteService()
    try:
        await favorite_service.add_favorite(
            session, user_id=current_user.id, property_id=property_id
        )
        await session.commit()
    except PropertyNotFoundError as pnf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "PROPERTY_NOT_FOUND",
                    "message": "Property not found or not active.",
                }
            },
        ) from pnf

    return MiniAppFavoriteResponse(success=True, property_id=property_id, is_favorite=True)


@router.delete(
    "/favorites/{property_id}",
    response_model=MiniAppFavoriteResponse,
    summary="Remove property from user favorites",
)
async def remove_favorite(
    property_id: int,
    current_user: Annotated[User, Depends(get_current_miniapp_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MiniAppFavoriteResponse:
    """Remove a property from user's favorites."""
    favorite_service = FavoriteService()
    await favorite_service.remove_favorite(
        session, user_id=current_user.id, property_id=property_id
    )
    await session.commit()
    return MiniAppFavoriteResponse(success=True, property_id=property_id, is_favorite=False)


@router.get(
    "/map/properties",
    response_model=list[MiniAppMapProperty],
    summary="Fetch approved property coordinates for map viewport",
)
async def get_map_properties(
    _current_user: Annotated[User, Depends(get_current_miniapp_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    listing_type: str | None = Query(None, pattern="^(sale|rent)$"),
    property_type: str | None = Query(None),
    currency: str | None = Query(None, pattern="^(USD|UZS)$"),
    min_price: Decimal | None = Query(None, ge=0),
    max_price: Decimal | None = Query(None, ge=0),
    rooms: int | None = Query(None, ge=1, le=20),
    north: float | None = Query(None, ge=-90.0, le=90.0),
    south: float | None = Query(None, ge=-90.0, le=90.0),
    east: float | None = Query(None, ge=-180.0, le=180.0),
    west: float | None = Query(None, ge=-180.0, le=180.0),
    min_lat: float | None = Query(None, ge=-90.0, le=90.0),
    max_lat: float | None = Query(None, ge=-90.0, le=90.0),
    min_lng: float | None = Query(None, ge=-180.0, le=180.0),
    max_lng: float | None = Query(None, ge=-180.0, le=180.0),
) -> list[MiniAppMapProperty]:
    """Return lightweight property coordinates and metadata for map markers."""
    # Support both north/south/east/west and min_lat/max_lat/min_lng/max_lng aliases
    if south is None and min_lat is not None:
        south = min_lat
    if north is None and max_lat is not None:
        north = max_lat
    if west is None and min_lng is not None:
        west = min_lng
    if east is None and max_lng is not None:
        east = max_lng

    if north is not None and south is not None and south > north:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_BOUNDS",
                    "message": "south latitude cannot exceed north",
                }
            },
        )
    if east is not None and west is not None and west > east:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_BOUNDS",
                    "message": "west longitude cannot exceed east",
                }
            },
        )

    conditions = [
        Property.status == "approved",
        Property.latitude.is_not(None),
        Property.longitude.is_not(None),
        Property.latitude >= Decimal("-90"),
        Property.latitude <= Decimal("90"),
        Property.longitude >= Decimal("-180"),
        Property.longitude <= Decimal("180"),
    ]

    if listing_type:
        conditions.append(Property.listing_type == listing_type)
    if currency:
        conditions.append(Property.currency == currency)
    if property_type and property_type.lower() not in ("all", "hamma", "barchasi"):
        conditions.append(Property.property_type == property_type)
    if rooms is not None:
        conditions.append(Property.rooms == rooms)
    if min_price is not None:
        conditions.append(Property.price >= min_price)
    if max_price is not None:
        conditions.append(Property.price <= max_price)

    # Viewport bounds filtering
    if south is not None and north is not None:
        conditions.append(Property.latitude >= Decimal(str(south)))
        conditions.append(Property.latitude <= Decimal(str(north)))
    if west is not None and east is not None:
        conditions.append(Property.longitude >= Decimal(str(west)))
        conditions.append(Property.longitude <= Decimal(str(east)))

    stmt = (
        select(Property)
        .options(selectinload(Property.media))
        .where(*conditions)
        .order_by(Property.approved_at.desc().nullslast())
        .limit(200)
    )
    props = list((await session.execute(stmt)).scalars().all())

    markers = []
    for p in props:
        if p.latitude is None or p.longitude is None:
            continue
        thumb_url = None
        if p.media:
            first_media = min(p.media, key=lambda m: m.sort_order)
            thumb_url = f"/api/miniapp/v1/properties/{p.id}/media/{first_media.id}"

        markers.append(
            MiniAppMapProperty(
                id=p.id,
                latitude=p.latitude,
                longitude=p.longitude,
                price=p.price,
                currency=p.currency,
                rooms=p.rooms,
                property_type=p.property_type,
                listing_type=p.listing_type,
                title=p.title or f"{p.rooms} xonali {p.property_type}",
                district=p.district,
                thumbnail_url=thumb_url,
            )
        )
    return markers


@router.post(
    "/properties/{property_id}/viewing-request",
    response_model=MiniAppViewingRequestResponse,
    summary="Create viewing appointment request",
)
async def create_viewing_request(
    property_id: int,
    body: MiniAppViewingRequestInput,
    current_user: Annotated[User, Depends(get_current_miniapp_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MiniAppViewingRequestResponse:
    """Create a viewing request through existing ViewingRequestService and LeadService."""
    enforce_miniapp_rate_limit(f"view_{current_user.id}", max_requests=10, window_seconds=60)
    viewing_service = ViewingRequestService()
    try:
        req = await viewing_service.create_viewing_request(
            session,
            customer_user_id=current_user.id,
            property_id=property_id,
            preferred_date=body.preferred_date,
            preferred_time=body.preferred_time,
            customer_comment=body.customer_comment,
        )
        await session.commit()
    except PropertyUnavailableError as pue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PROPERTY_NOT_AVAILABLE", "message": str(pue)}},
        ) from pue
    except ViewingValidationError as vve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(vve)}},
        ) from vve
    except DuplicateViewingRequestError as dve:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "DUPLICATE_VIEWING_REQUEST", "message": str(dve)}},
        ) from dve

    return MiniAppViewingRequestResponse(
        id=req.id,
        property_id=req.property_id,
        request_type=req.request_type,
        status=req.status,
        preferred_date=req.preferred_date,
        preferred_time=req.preferred_time,
        created_at=req.created_at,
    )


@router.post(
    "/properties/{property_id}/broker-contact",
    response_model=MiniAppBrokerContactResponse,
    summary="Request broker contact for property",
)
async def create_broker_contact(
    property_id: int,
    body: MiniAppBrokerContactInput,
    current_user: Annotated[User, Depends(get_current_miniapp_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MiniAppBrokerContactResponse:
    """Request broker contact through existing ViewingRequestService and LeadService."""
    enforce_miniapp_rate_limit(f"broker_{current_user.id}", max_requests=10, window_seconds=60)
    viewing_service = ViewingRequestService()
    try:
        req = await viewing_service.create_broker_contact_request(
            session,
            customer_user_id=current_user.id,
            property_id=property_id,
            customer_comment=body.customer_comment,
        )
        await session.commit()
    except PropertyUnavailableError as pue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PROPERTY_NOT_AVAILABLE", "message": str(pue)}},
        ) from pue
    except DuplicateViewingRequestError as dve:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "DUPLICATE_CONTACT_REQUEST", "message": str(dve)}},
        ) from dve

    return MiniAppBrokerContactResponse(
        id=req.id,
        property_id=req.property_id,
        request_type=req.request_type,
        status=req.status,
        created_at=req.created_at,
    )
