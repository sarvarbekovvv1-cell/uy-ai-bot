"""Admin dashboard metrics and operational KPI endpoints."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.api.schemas.admin import DashboardMetricsResponse
from app.config import Settings, get_settings
from app.models.crm_sync import CRMSyncEvent
from app.models.lead import ACTIVE_LEAD_STAGES, Lead
from app.models.property import Property
from app.models.user import User
from app.models.viewing_request import ViewingRequest
from app.services.admin_rbac import PERM_DASHBOARD_VIEW, require_permission

router = APIRouter(prefix="/dashboard", tags=["Admin Dashboard"])


@router.get("", response_model=DashboardMetricsResponse)
async def get_dashboard_metrics(
    days: int = Query(default=30, ge=1, le=365),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    _: User = Depends(require_permission(PERM_DASHBOARD_VIEW)),
) -> DashboardMetricsResponse:
    """Return aggregated high-level business and operational KPIs."""
    cutoff = datetime.now(UTC) - timedelta(days=days)

    # 1. User counts
    total_users = (
        await session.execute(select(func.count(User.id)).where(User.is_active.is_(True)))
    ).scalar_one() or 0

    # 2. Property counts
    active_props = (
        await session.execute(
            select(func.count(Property.id)).where(Property.status == "approved")
        )
    ).scalar_one() or 0

    pending_props = (
        await session.execute(
            select(func.count(Property.id)).where(Property.status == "pending_approval")
        )
    ).scalar_one() or 0

    # 3. Lead counts
    active_leads = (
        await session.execute(
            select(func.count(Lead.id)).where(Lead.stage.in_(ACTIVE_LEAD_STAGES))
        )
    ).scalar_one() or 0

    new_leads = (
        await session.execute(
            select(func.count(Lead.id)).where(Lead.created_at >= cutoff)
        )
    ).scalar_one() or 0

    won_leads = (
        await session.execute(select(func.count(Lead.id)).where(Lead.stage == "won"))
    ).scalar_one() or 0

    lost_leads = (
        await session.execute(select(func.count(Lead.id)).where(Lead.stage == "lost"))
    ).scalar_one() or 0

    # 4. Viewing counts
    total_viewings = (
        await session.execute(select(func.count(ViewingRequest.id)))
    ).scalar_one() or 0

    # 5. CRM Outbox counts
    crm_pending = (
        await session.execute(
            select(func.count(CRMSyncEvent.id)).where(
                CRMSyncEvent.provider == "amocrm",
                CRMSyncEvent.status == "pending",
            )
        )
    ).scalar_one() or 0

    crm_failed = (
        await session.execute(
            select(func.count(CRMSyncEvent.id)).where(
                CRMSyncEvent.provider == "amocrm",
                CRMSyncEvent.status == "failed",
            )
        )
    ).scalar_one() or 0

    crm_succeeded = (
        await session.execute(
            select(func.count(CRMSyncEvent.id)).where(
                CRMSyncEvent.provider == "amocrm",
                CRMSyncEvent.status == "succeeded",
            )
        )
    ).scalar_one() or 0

    return DashboardMetricsResponse(
        total_users=total_users,
        active_properties=active_props,
        pending_moderation_properties=pending_props,
        active_leads=active_leads,
        new_leads_count=new_leads,
        won_leads=won_leads,
        lost_leads=lost_leads,
        total_viewings=total_viewings,
        crm_pending_events=crm_pending,
        crm_failed_events=crm_failed,
        crm_succeeded_events=crm_succeeded,
        ai_broker_enabled=settings.ai_broker_enabled,
    )
