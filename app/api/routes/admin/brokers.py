"""Admin broker management and workload monitoring routes."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db_session
from app.api.schemas.admin import AdminBrokerItem
from app.models.lead import ACTIVE_LEAD_STAGES, Lead
from app.models.role import Role
from app.models.user import User
from app.models.viewing_request import ViewingRequest
from app.services.admin_rbac import PERM_BROKERS_VIEW, require_permission

router = APIRouter(prefix="/brokers", tags=["Admin Brokers"])

BROKER_ROLE_NAMES = ("head_broker", "sales_broker", "rental_broker")


@router.get("", response_model=list[AdminBrokerItem])
async def list_brokers(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(require_permission(PERM_BROKERS_VIEW)),
) -> list[AdminBrokerItem]:
    """Return all broker staff users and their current active workloads."""
    stmt = (
        select(User)
        .join(User.roles)
        .options(selectinload(User.roles))
        .where(Role.name.in_(BROKER_ROLE_NAMES), User.is_active.is_(True))
        .distinct()
    )
    result = await session.execute(stmt)
    brokers = result.scalars().all()

    items = []
    for broker in brokers:
        # Determine primary broker role
        roles = [r.name for r in broker.roles if r.name in BROKER_ROLE_NAMES]
        primary_role = roles[0] if roles else "broker"

        # Active leads count
        active_leads = (
            await session.execute(
                select(func.count(Lead.id)).where(
                    Lead.broker_user_id == broker.id,
                    Lead.stage.in_(ACTIVE_LEAD_STAGES),
                )
            )
        ).scalar_one() or 0

        # Viewings count
        viewings_count = (
            await session.execute(
                select(func.count(ViewingRequest.id)).where(
                    ViewingRequest.broker_user_id == broker.id
                )
            )
        ).scalar_one() or 0

        # Won leads count
        won_leads = (
            await session.execute(
                select(func.count(Lead.id)).where(
                    Lead.broker_user_id == broker.id,
                    Lead.stage == "won",
                )
            )
        ).scalar_one() or 0

        # Lost leads count
        lost_leads = (
            await session.execute(
                select(func.count(Lead.id)).where(
                    Lead.broker_user_id == broker.id,
                    Lead.stage == "lost",
                )
            )
        ).scalar_one() or 0

        items.append(
            AdminBrokerItem(
                id=broker.id,
                first_name=broker.first_name,
                last_name=broker.last_name,
                username=broker.username,
                role=primary_role,
                active_leads_count=active_leads,
                viewings_count=viewings_count,
                won_leads_count=won_leads,
                lost_leads_count=lost_leads,
            )
        )

    return items
