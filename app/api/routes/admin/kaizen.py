"""Admin Kaizen / PDCA Intelligence API endpoints."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.api.schemas.admin import (
    KaizenCycleCancelRequest,
    KaizenCycleCheckRequest,
    KaizenCycleCompleteRequest,
    KaizenCycleCreateRequest,
    KaizenCycleItem,
    KaizenCyclePlanRequest,
    KaizenCycleStartRequest,
    KaizenGenerateRecommendationsRequest,
    KaizenRecommendationItem,
    KaizenRecommendationReviewRequest,
    PaginatedResponse,
)
from app.logging import get_logger
from app.models.kaizen import KaizenCycle
from app.models.user import User
from app.services.admin_rbac import (
    PERM_KAIZEN_GENERATE,
    PERM_KAIZEN_MANAGE,
    PERM_KAIZEN_VIEW,
    require_permission,
    verify_csrf_token,
)
from app.services.kaizen_analytics_service import KaizenAnalyticsService, KaizenDateRange
from app.services.kaizen_recommendation_service import KaizenRecommendationService
from app.services.kaizen_service import KaizenService
from app.services.rate_limiter import rate_limit

logger = get_logger(__name__)

router = APIRouter(prefix="/kaizen", tags=["Admin Kaizen"])


def _serialize_cycle(c: KaizenCycle) -> KaizenCycleItem:
    """Helper to convert KaizenCycle ORM entity to response schema."""
    created_name = None
    if c.created_by:
        created_name = (
            f"{c.created_by.first_name or ''} {c.created_by.last_name or ''}".strip()
            or c.created_by.username
        )

    return KaizenCycleItem(
        id=c.id,
        title=c.title,
        description=c.description,
        status=c.status,
        metric_key=c.metric_key,
        baseline_value=c.baseline_value,
        target_value=c.target_value,
        observed_value=c.observed_value,
        unit=c.unit,
        date_from=c.date_from,
        date_to=c.date_to,
        plan_text=c.plan_text,
        do_text=c.do_text,
        check_text=c.check_text,
        act_text=c.act_text,
        baseline_snapshot_json=c.baseline_snapshot_json,
        check_snapshot_json=c.check_snapshot_json,
        outcome=c.outcome,
        created_by_name=created_name,
        created_at=c.created_at,
        started_at=c.started_at,
        checking_at=c.checking_at,
        completed_at=c.completed_at,
        cancelled_at=c.cancelled_at,
    )


# -----------------------------------------------------------------------------
# 1. Operational Overview & Analytics
# -----------------------------------------------------------------------------
@router.get("/overview")
async def get_kaizen_overview(
    days: int = Query(default=30, ge=1, le=365),
    date_from: date | None = None,
    date_to: date | None = None,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_permission(PERM_KAIZEN_VIEW)),
) -> dict[str, Any]:
    """Return deterministic operational KPIs with flexible date filtering."""
    try:
        rng = KaizenDateRange(date_from=date_from, date_to=date_to, days=days)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    return await KaizenAnalyticsService.get_kpi_overview(session, rng)


# -----------------------------------------------------------------------------
# 2. Recommendations
# -----------------------------------------------------------------------------
@router.get("/recommendations", response_model=PaginatedResponse)
async def list_recommendations(
    status_filter: str | None = Query(default=None, alias="status"),
    category: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_permission(PERM_KAIZEN_VIEW)),
) -> PaginatedResponse:
    """List paginated Kaizen management recommendations."""
    items, total = await KaizenRecommendationService.list_recommendations(
        session, status_filter=status_filter, category=category, page=page, page_size=page_size
    )

    resp_items = [
        KaizenRecommendationItem(
            id=r.id,
            metric_key=r.metric_key,
            category=r.category,
            title=r.title,
            description=r.description,
            evidence_json=r.evidence_json,
            recommendation_text=r.recommendation_text,
            confidence=r.confidence,
            severity=r.severity,
            status=r.status,
            generated_at=r.generated_at,
            reviewed_at=r.reviewed_at,
            linked_cycle_id=r.linked_cycle_id,
        )
        for r in items
    ]
    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=resp_items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post(
    "/recommendations/generate",
    response_model=list[KaizenRecommendationItem],
    status_code=status.HTTP_201_CREATED,
)
async def generate_recommendations(
    request: Request,
    body: KaizenGenerateRecommendationsRequest,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_KAIZEN_GENERATE)),
    _: None = Depends(verify_csrf_token),
    __: None = Depends(rate_limit("kaizen_generate", max_requests=10, window_seconds=60)),
) -> list[KaizenRecommendationItem]:
    """Trigger recommendation engine combining deterministic rules and Gemini advisor."""
    try:
        rng = KaizenDateRange(date_from=body.date_from, date_to=body.date_to)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    client_ip = request.client.host if request.client else None
    new_recs = await KaizenRecommendationService.generate_and_persist_recommendations(
        session,
        staff_user_id=staff_user.id,
        date_range=rng,
        use_ai=body.use_ai,
        ip_address=client_ip,
    )

    return [
        KaizenRecommendationItem(
            id=r.id,
            metric_key=r.metric_key,
            category=r.category,
            title=r.title,
            description=r.description,
            evidence_json=r.evidence_json,
            recommendation_text=r.recommendation_text,
            confidence=r.confidence,
            severity=r.severity,
            status=r.status,
            generated_at=r.generated_at,
            reviewed_at=r.reviewed_at,
            linked_cycle_id=r.linked_cycle_id,
        )
        for r in new_recs
    ]


@router.post("/recommendations/{recommendation_id}/review", response_model=KaizenRecommendationItem)
async def review_recommendation(
    recommendation_id: int,
    request: Request,
    body: KaizenRecommendationReviewRequest,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_KAIZEN_MANAGE)),
    _: None = Depends(verify_csrf_token),
) -> KaizenRecommendationItem:
    """Accept or dismiss a recommendation."""
    client_ip = request.client.host if request.client else None
    rec = await KaizenRecommendationService.review_recommendation(
        session,
        recommendation_id=recommendation_id,
        staff_user_id=staff_user.id,
        action=body.action,
        ip_address=client_ip,
    )
    return KaizenRecommendationItem(
        id=rec.id,
        metric_key=rec.metric_key,
        category=rec.category,
        title=rec.title,
        description=rec.description,
        evidence_json=rec.evidence_json,
        recommendation_text=rec.recommendation_text,
        confidence=rec.confidence,
        severity=rec.severity,
        status=rec.status,
        generated_at=rec.generated_at,
        reviewed_at=rec.reviewed_at,
        linked_cycle_id=rec.linked_cycle_id,
    )


# -----------------------------------------------------------------------------
# 3. PDCA Cycles
# -----------------------------------------------------------------------------
@router.get("/cycles", response_model=PaginatedResponse)
async def list_cycles(
    status_filter: str | None = Query(default=None, alias="status"),
    metric_key: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_permission(PERM_KAIZEN_VIEW)),
) -> PaginatedResponse:
    """List paginated Kaizen PDCA cycles."""
    cycles, total = await KaizenService.list_cycles(
        session, status_filter=status_filter, metric_key=metric_key, page=page, page_size=page_size
    )
    resp_items = [_serialize_cycle(c) for c in cycles]
    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        items=resp_items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/cycles", response_model=KaizenCycleItem, status_code=status.HTTP_201_CREATED)
async def create_cycle(
    request: Request,
    body: KaizenCycleCreateRequest,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_KAIZEN_MANAGE)),
    _: None = Depends(verify_csrf_token),
) -> KaizenCycleItem:
    """Create a new PDCA cycle and record baseline metric snapshot."""
    client_ip = request.client.host if request.client else None
    cycle = await KaizenService.create_cycle(
        session,
        title=body.title,
        metric_key=body.metric_key,
        created_by_user_id=staff_user.id,
        target_value=body.target_value,
        description=body.description,
        date_from=body.date_from,
        date_to=body.date_to,
        plan_text=body.plan_text,
        recommendation_id=body.recommendation_id,
        ip_address=client_ip,
    )
    return _serialize_cycle(cycle)


@router.get("/cycles/{cycle_id}", response_model=KaizenCycleItem)
async def get_cycle(
    cycle_id: int,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_permission(PERM_KAIZEN_VIEW)),
) -> KaizenCycleItem:
    """Fetch PDCA cycle details."""
    cycle = await KaizenService.get_cycle(session, cycle_id)
    return _serialize_cycle(cycle)


@router.post("/cycles/{cycle_id}/plan", response_model=KaizenCycleItem)
async def plan_cycle(
    cycle_id: int,
    request: Request,
    body: KaizenCyclePlanRequest,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_KAIZEN_MANAGE)),
    _: None = Depends(verify_csrf_token),
) -> KaizenCycleItem:
    """Transition cycle to planned state with target values."""
    client_ip = request.client.host if request.client else None
    cycle = await KaizenService.plan_cycle(
        session,
        cycle_id=cycle_id,
        staff_user_id=staff_user.id,
        plan_text=body.plan_text,
        target_value=body.target_value,
        date_from=body.date_from,
        date_to=body.date_to,
        ip_address=client_ip,
    )
    return _serialize_cycle(cycle)


@router.post("/cycles/{cycle_id}/start", response_model=KaizenCycleItem)
async def start_cycle(
    cycle_id: int,
    request: Request,
    body: KaizenCycleStartRequest,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_KAIZEN_MANAGE)),
    _: None = Depends(verify_csrf_token),
) -> KaizenCycleItem:
    """Transition cycle to active state (DO phase)."""
    client_ip = request.client.host if request.client else None
    cycle = await KaizenService.start_cycle(
        session,
        cycle_id=cycle_id,
        staff_user_id=staff_user.id,
        do_text=body.do_text,
        ip_address=client_ip,
    )
    return _serialize_cycle(cycle)


@router.post("/cycles/{cycle_id}/check")
async def check_cycle(
    cycle_id: int,
    request: Request,
    body: KaizenCycleCheckRequest,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_KAIZEN_MANAGE)),
    _: None = Depends(verify_csrf_token),
) -> dict[str, Any]:
    """Execute CHECK phase: compute observed value, delta, and target progress."""
    client_ip = request.client.host if request.client else None
    result = await KaizenService.check_cycle(
        session,
        cycle_id=cycle_id,
        staff_user_id=staff_user.id,
        check_text=body.check_text,
        ip_address=client_ip,
    )
    return {
        "cycle": _serialize_cycle(result["cycle"]),
        "delta": result["delta"],
        "progress_towards_target_pct": result["progress_towards_target_pct"],
        "snapshot": result["snapshot"],
    }


@router.post("/cycles/{cycle_id}/complete", response_model=KaizenCycleItem)
async def complete_cycle(
    cycle_id: int,
    request: Request,
    body: KaizenCycleCompleteRequest,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_KAIZEN_MANAGE)),
    _: None = Depends(verify_csrf_token),
) -> KaizenCycleItem:
    """Execute ACT phase: conclude PDCA cycle with verified outcome."""
    client_ip = request.client.host if request.client else None
    cycle = await KaizenService.complete_cycle(
        session,
        cycle_id=cycle_id,
        staff_user_id=staff_user.id,
        outcome=body.outcome,
        act_text=body.act_text,
        ip_address=client_ip,
    )
    return _serialize_cycle(cycle)


@router.post("/cycles/{cycle_id}/cancel", response_model=KaizenCycleItem)
async def cancel_cycle(
    cycle_id: int,
    request: Request,
    body: KaizenCycleCancelRequest,
    session: AsyncSession = Depends(get_db_session),
    staff_user: User = Depends(require_permission(PERM_KAIZEN_MANAGE)),
    _: None = Depends(verify_csrf_token),
) -> KaizenCycleItem:
    """Cancel a PDCA cycle."""
    client_ip = request.client.host if request.client else None
    cycle = await KaizenService.cancel_cycle(
        session,
        cycle_id=cycle_id,
        staff_user_id=staff_user.id,
        reason=body.reason,
        ip_address=client_ip,
    )
    return _serialize_cycle(cycle)
