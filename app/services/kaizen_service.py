"""Kaizen PDCA (Plan-Do-Check-Act) Cycle Lifecycle Management Service."""

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.logging import get_logger
from app.models.kaizen import (
    KAIZEN_OUTCOMES,
    KaizenCycle,
    KaizenRecommendation,
)
from app.models.property_media import PropertyMedia
from app.services.admin_auth_service import AdminAuthService
from app.services.kaizen_analytics_service import KaizenAnalyticsService
from app.services.media_storage import get_media_storage

logger = get_logger(__name__)

VALID_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"planned", "cancelled"},
    "planned": {"active", "cancelled"},
    "active": {"checking", "cancelled"},
    "checking": {"completed", "active", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}

LOWER_IS_BETTER_METRICS: set[str] = {
    "median_response_time",
    "average_response_time",
    "p90_response_time",
    "viewing_cancellation_rate",
    "overdue_followups",
    "crm_failed_events",
    "moderation_backlog",
}


class KaizenService:
    """Manages creation, execution, checking, and completion of PDCA cycles."""

    @classmethod
    async def get_cycle(cls, session: AsyncSession, cycle_id: int) -> KaizenCycle:
        """Fetch KaizenCycle by ID or raise HTTP 404."""
        stmt = (
            select(KaizenCycle)
            .options(
                selectinload(KaizenCycle.created_by),
                selectinload(KaizenCycle.approved_by),
            )
            .where(KaizenCycle.id == cycle_id)
        )
        cycle = (await session.execute(stmt)).scalar_one_or_none()
        if not cycle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Kaizen PDCA cycle #{cycle_id} not found.",
            )
        return cycle

    @classmethod
    async def list_cycles(
        cls,
        session: AsyncSession,
        status_filter: str | None = None,
        metric_key: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[KaizenCycle], int]:
        """Return paginated Kaizen cycles with optional filters."""
        stmt = select(KaizenCycle).options(
            selectinload(KaizenCycle.created_by),
            selectinload(KaizenCycle.approved_by),
        )
        if status_filter:
            stmt = stmt.where(KaizenCycle.status == status_filter)
        if metric_key:
            stmt = stmt.where(KaizenCycle.metric_key == metric_key)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await session.execute(count_stmt)).scalar_one() or 0

        stmt = (
            stmt.order_by(KaizenCycle.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        cycles = list((await session.execute(stmt)).scalars().all())
        return cycles, total

    @classmethod
    async def create_cycle(
        cls,
        session: AsyncSession,
        title: str,
        metric_key: str,
        created_by_user_id: int,
        target_value: Decimal | float | None = None,
        description: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        plan_text: str | None = None,
        recommendation_id: int | None = None,
        ip_address: str | None = None,
    ) -> KaizenCycle:
        """Create a new PDCA cycle and lock the deterministic baseline snapshot."""
        try:
            snapshot = await KaizenAnalyticsService.get_metric_snapshot(
                session, metric_key=metric_key, date_from=date_from, date_to=date_to
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

        baseline_val = snapshot.get("value")
        baseline_dec = Decimal(str(baseline_val)) if baseline_val is not None else None
        target_dec = Decimal(str(target_value)) if target_value is not None else None

        cycle = KaizenCycle(
            title=title.strip(),
            description=description.strip() if description else None,
            status="draft",
            created_by_user_id=created_by_user_id,
            metric_key=metric_key,
            baseline_value=baseline_dec,
            target_value=target_dec,
            unit=snapshot.get("unit", "percentage"),
            date_from=date_from,
            date_to=date_to,
            plan_text=plan_text.strip() if plan_text else None,
            baseline_snapshot_json=json.dumps(snapshot),
        )
        session.add(cycle)
        await session.flush()

        # Link recommendation if provided
        if recommendation_id:
            rec = await session.get(KaizenRecommendation, recommendation_id)
            if rec:
                rec.linked_cycle_id = cycle.id
                rec.status = "converted_to_cycle"

        await AdminAuthService.record_audit_event(
            session,
            actor_user_id=created_by_user_id,
            action="kaizen.cycle_create",
            entity_type="kaizen_cycle",
            entity_id=cycle.id,
            metadata={
                "title": cycle.title,
                "metric_key": metric_key,
                "baseline_value": float(baseline_dec) if baseline_dec is not None else None,
                "target_value": float(target_dec) if target_dec is not None else None,
            },
            ip_address=ip_address,
        )

        await session.commit()
        await session.refresh(cycle)
        return cycle

    @classmethod
    def _validate_transition(cls, current_status: str, target_status: str) -> None:
        """Check if transition is legal per PDCA finite state machine."""
        allowed = VALID_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid PDCA state transition from '{current_status}' to '{target_status}'. "
                    f"Allowed next states: {sorted(allowed) or 'None (terminal)'}"
                ),
            )

    @classmethod
    async def plan_cycle(
        cls,
        session: AsyncSession,
        cycle_id: int,
        staff_user_id: int,
        plan_text: str,
        target_value: Decimal | float | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        ip_address: str | None = None,
    ) -> KaizenCycle:
        """Approve plan and transition cycle from draft to planned."""
        cycle = await cls.get_cycle(session, cycle_id)
        cls._validate_transition(cycle.status, "planned")

        cycle.status = "planned"
        cycle.plan_text = plan_text.strip()
        cycle.approved_by_user_id = staff_user_id
        if target_value is not None:
            cycle.target_value = Decimal(str(target_value))
        if date_from is not None:
            cycle.date_from = date_from
        if date_to is not None:
            cycle.date_to = date_to

        await AdminAuthService.record_audit_event(
            session,
            actor_user_id=staff_user_id,
            action="kaizen.cycle_plan",
            entity_type="kaizen_cycle",
            entity_id=cycle.id,
            metadata={
                "status": "planned",
                "target_value": float(cycle.target_value) if cycle.target_value else None,
            },
            ip_address=ip_address,
        )

        await session.commit()
        await session.refresh(cycle)
        return cycle

    @classmethod
    async def start_cycle(
        cls,
        session: AsyncSession,
        cycle_id: int,
        staff_user_id: int,
        do_text: str | None = None,
        ip_address: str | None = None,
    ) -> KaizenCycle:
        """Move cycle into DO phase: active execution."""
        cycle = await cls.get_cycle(session, cycle_id)
        cls._validate_transition(cycle.status, "active")

        cycle.status = "active"
        cycle.started_at = datetime.now(UTC)
        if do_text:
            cycle.do_text = do_text.strip()

        await AdminAuthService.record_audit_event(
            session,
            actor_user_id=staff_user_id,
            action="kaizen.cycle_start",
            entity_type="kaizen_cycle",
            entity_id=cycle.id,
            metadata={"status": "active", "started_at": cycle.started_at.isoformat()},
            ip_address=ip_address,
        )

        await session.commit()
        await session.refresh(cycle)
        return cycle

    @classmethod
    async def check_cycle(
        cls,
        session: AsyncSession,
        cycle_id: int,
        staff_user_id: int,
        check_text: str | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """Perform CHECK phase: re-evaluate metric, compute delta & progress."""
        cycle = await cls.get_cycle(session, cycle_id)
        cls._validate_transition(cycle.status, "checking")

        snapshot = await KaizenAnalyticsService.get_metric_snapshot(
            session,
            metric_key=cycle.metric_key,
            date_from=cycle.date_from,
            date_to=cycle.date_to,
        )

        observed_val = snapshot.get("value")
        observed_dec = Decimal(str(observed_val)) if observed_val is not None else None

        cycle.status = "checking"
        cycle.observed_value = observed_dec
        cycle.check_snapshot_json = json.dumps(snapshot)
        cycle.checking_at = datetime.now(UTC)
        if check_text:
            cycle.check_text = check_text.strip()

        delta: float | None = None
        progress_pct: float | None = None
        suggested_outcome: str = "unsuccessful"

        if cycle.baseline_value is not None and observed_dec is not None:
            delta = round(float(observed_dec - cycle.baseline_value), 2)
            if cycle.target_value is not None:
                target_diff = float(cycle.target_value - cycle.baseline_value)
                if abs(target_diff) > 0.0001:
                    progress_pct = round((delta / target_diff) * 100.0, 1)
                else:
                    progress_pct = 100.0 if abs(delta) < 0.0001 else 0.0

        if progress_pct is not None:
            if progress_pct >= 90.0:
                suggested_outcome = "successful"
            elif progress_pct >= 50.0:
                suggested_outcome = "partially_successful"
            else:
                suggested_outcome = "unsuccessful"

        await AdminAuthService.record_audit_event(
            session,
            actor_user_id=staff_user_id,
            action="kaizen.cycle_check",
            entity_type="kaizen_cycle",
            entity_id=cycle.id,
            metadata={
                "status": "checking",
                "baseline": float(cycle.baseline_value) if cycle.baseline_value else None,
                "target": float(cycle.target_value) if cycle.target_value else None,
                "observed": float(observed_dec) if observed_dec else None,
                "delta": delta,
                "progress_pct": progress_pct,
                "suggested_outcome": suggested_outcome,
            },
            ip_address=ip_address,
        )

        await session.commit()
        await session.refresh(cycle)

        return {
            "cycle": cycle,
            "delta": delta,
            "progress_towards_target_pct": progress_pct,
            "suggested_outcome": suggested_outcome,
            "snapshot": snapshot,
        }

    @classmethod
    async def complete_cycle(
        cls,
        session: AsyncSession,
        cycle_id: int,
        staff_user_id: int,
        outcome: str,
        act_text: str | None = None,
        ip_address: str | None = None,
    ) -> KaizenCycle:
        """Perform ACT phase: conclude PDCA cycle with verified outcome."""
        cycle = await cls.get_cycle(session, cycle_id)
        cls._validate_transition(cycle.status, "completed")

        if outcome not in KAIZEN_OUTCOMES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid outcome: '{outcome}'. Must be one of {KAIZEN_OUTCOMES}",
            )

        cycle.status = "completed"
        cycle.outcome = outcome
        cycle.completed_at = datetime.now(UTC)
        if act_text:
            cycle.act_text = act_text.strip()

        await AdminAuthService.record_audit_event(
            session,
            actor_user_id=staff_user_id,
            action="kaizen.cycle_complete",
            entity_type="kaizen_cycle",
            entity_id=cycle.id,
            metadata={
                "status": "completed",
                "outcome": outcome,
                "completed_at": cycle.completed_at.isoformat(),
            },
            ip_address=ip_address,
        )

        await session.commit()
        await session.refresh(cycle)
        return cycle

    @classmethod
    async def cancel_cycle(
        cls,
        session: AsyncSession,
        cycle_id: int,
        staff_user_id: int,
        reason: str | None = None,
        ip_address: str | None = None,
    ) -> KaizenCycle:
        """Cancel an in-progress PDCA cycle."""
        cycle = await cls.get_cycle(session, cycle_id)
        cls._validate_transition(cycle.status, "cancelled")

        cycle.status = "cancelled"
        cycle.cancelled_at = datetime.now(UTC)
        if reason:
            cycle.act_text = f"Cancelled: {reason.strip()}"

        await AdminAuthService.record_audit_event(
            session,
            actor_user_id=staff_user_id,
            action="kaizen.cycle_cancel",
            entity_type="kaizen_cycle",
            entity_id=cycle.id,
            metadata={"status": "cancelled", "reason": reason},
            ip_address=ip_address,
        )

        await session.commit()
        await session.refresh(cycle)
        return cycle

    @classmethod
    async def cleanup_orphan_media(
        cls,
        session: AsyncSession,
        max_age_hours: int = 24,
    ) -> int:
        """Find and remove unreferenced uploaded files older than max_age_hours."""
        active_uids_stmt = select(PropertyMedia.telegram_file_unique_id).where(
            PropertyMedia.telegram_file_unique_id.is_not(None)
        )
        active_uids = set((await session.execute(active_uids_stmt)).scalars().all())
        storage = get_media_storage()
        return storage.cleanup_orphans(active_uids, max_age_hours)
