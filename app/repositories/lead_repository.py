"""Repository for Lead and CRM database operations."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.lead import (
    ACTIVE_LEAD_STAGES,
    Lead,
    LeadEvent,
    LeadFollowUp,
    LeadNote,
)
from app.models.property import Property


class LeadRepository:
    """Handles database access for Lead, FollowUp, Note, and Event entities."""

    async def create(
        self,
        session: AsyncSession,
        *,
        customer_user_id: int,
        property_id: int,
        source: str,
        broker_user_id: int | None = None,
        source_request_id: int | None = None,
        stage: str = "new",
        assigned_at: datetime | None = None,
    ) -> Lead:
        """Create and persist a new Lead."""
        lead = Lead(
            customer_user_id=customer_user_id,
            property_id=property_id,
            source=source,
            broker_user_id=broker_user_id,
            source_request_id=source_request_id,
            stage=stage,
            assigned_at=assigned_at,
        )
        session.add(lead)
        await session.flush()
        return lead

    async def get_by_id(self, session: AsyncSession, lead_id: int) -> Lead | None:
        """Fetch lead by ID with all relationships eagerly loaded."""
        stmt = (
            select(Lead)
            .options(
                selectinload(Lead.property).selectinload(Property.media),
                selectinload(Lead.customer),
                selectinload(Lead.broker),
                selectinload(Lead.source_request),
                selectinload(Lead.followups),
                selectinload(Lead.notes).selectinload(LeadNote.author),
                selectinload(Lead.events).selectinload(LeadEvent.actor),
            )
            .where(Lead.id == lead_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_customer_property(
        self,
        session: AsyncSession,
        *,
        customer_user_id: int,
        property_id: int,
    ) -> Lead | None:
        """Find active lead for a customer and property to prevent duplicates."""
        stmt = (
            select(Lead)
            .options(
                selectinload(Lead.property),
                selectinload(Lead.customer),
                selectinload(Lead.broker),
            )
            .where(
                Lead.customer_user_id == customer_user_id,
                Lead.property_id == property_id,
                Lead.stage.in_(ACTIVE_LEAD_STAGES),
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_leads(
        self,
        session: AsyncSession,
        *,
        allowed_listing_types: list[str],
        broker_user_id: int | None = None,
        unassigned_only: bool = False,
        stages: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Lead]:
        """Fetch leads filtered by listing types, assigned broker or status, and stages."""
        stmt = (
            select(Lead)
            .join(Property, Property.id == Lead.property_id)
            .options(
                selectinload(Lead.property).selectinload(Property.media),
                selectinload(Lead.customer),
                selectinload(Lead.broker),
                selectinload(Lead.followups),
            )
            .where(Property.listing_type.in_(allowed_listing_types))
        )

        if unassigned_only:
            stmt = stmt.where(Lead.broker_user_id.is_(None))
        elif broker_user_id is not None:
            stmt = stmt.where(Lead.broker_user_id == broker_user_id)

        if stages:
            stmt = stmt.where(Lead.stage.in_(stages))

        stmt = stmt.order_by(Lead.updated_at.desc(), Lead.id.desc())
        stmt = stmt.limit(limit).offset(offset)

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def count_leads(
        self,
        session: AsyncSession,
        *,
        allowed_listing_types: list[str],
        broker_user_id: int | None = None,
        unassigned_only: bool = False,
        stages: list[str] | None = None,
    ) -> int:
        """Count leads matching filter criteria."""
        stmt = (
            select(func.count(Lead.id))
            .join(Property, Property.id == Lead.property_id)
            .where(Property.listing_type.in_(allowed_listing_types))
        )

        if unassigned_only:
            stmt = stmt.where(Lead.broker_user_id.is_(None))
        elif broker_user_id is not None:
            stmt = stmt.where(Lead.broker_user_id == broker_user_id)

        if stages:
            stmt = stmt.where(Lead.stage.in_(stages))

        result = await session.execute(stmt)
        return int(result.scalar_one())

    async def count_by_stage_for_broker(
        self,
        session: AsyncSession,
        *,
        allowed_listing_types: list[str],
        broker_user_id: int | None = None,
    ) -> dict[str, int]:
        """Return counts of leads grouped by stage for a broker."""
        stmt = (
            select(Lead.stage, func.count(Lead.id))
            .join(Property, Property.id == Lead.property_id)
            .where(Property.listing_type.in_(allowed_listing_types))
        )
        if broker_user_id is not None:
            stmt = stmt.where(
                or_(
                    Lead.broker_user_id == broker_user_id,
                    Lead.broker_user_id.is_(None),
                )
            )
        stmt = stmt.group_by(Lead.stage)
        result = await session.execute(stmt)
        counts = dict.fromkeys(ACTIVE_LEAD_STAGES + ("won", "lost"), 0)
        for stage, count in result.all():
            counts[stage] = count
        return counts

    async def update(self, session: AsyncSession, lead_id: int, **values: Any) -> Lead | None:
        """Update lead attributes."""
        values["updated_at"] = datetime.now(UTC)
        stmt = (
            update(Lead)
            .where(Lead.id == lead_id)
            .values(**values)
            .execution_options(synchronize_session="fetch")
        )
        await session.execute(stmt)
        await session.flush()
        return await self.get_by_id(session, lead_id)

    # --- Follow-up Tasks ---

    async def create_followup(
        self,
        session: AsyncSession,
        *,
        lead_id: int,
        broker_user_id: int,
        task_type: str,
        due_at: datetime,
        note: str | None = None,
    ) -> LeadFollowUp:
        """Create a follow-up task."""
        followup = LeadFollowUp(
            lead_id=lead_id,
            broker_user_id=broker_user_id,
            task_type=task_type,
            due_at=due_at,
            note=note,
            status="pending",
        )
        session.add(followup)
        await session.flush()
        return followup

    async def get_followup_by_id(
        self,
        session: AsyncSession,
        followup_id: int,
    ) -> LeadFollowUp | None:
        """Fetch follow-up by ID with lead and broker loaded."""
        stmt = (
            select(LeadFollowUp)
            .options(
                selectinload(LeadFollowUp.lead).selectinload(Lead.property),
                selectinload(LeadFollowUp.lead).selectinload(Lead.customer),
                selectinload(LeadFollowUp.broker),
            )
            .where(LeadFollowUp.id == followup_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_followups_for_broker(
        self,
        session: AsyncSession,
        *,
        broker_user_id: int,
        allowed_listing_types: list[str],
        status: str = "pending",
        is_overdue: bool = False,
        due_start: datetime | None = None,
        due_end: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[LeadFollowUp]:
        """List follow-ups for a broker, with overdue or time range filtering."""
        stmt = (
            select(LeadFollowUp)
            .join(Lead, Lead.id == LeadFollowUp.lead_id)
            .join(Property, Property.id == Lead.property_id)
            .options(
                selectinload(LeadFollowUp.lead).selectinload(Lead.property),
                selectinload(LeadFollowUp.lead).selectinload(Lead.customer),
                selectinload(LeadFollowUp.broker),
            )
            .where(
                LeadFollowUp.broker_user_id == broker_user_id,
                Property.listing_type.in_(allowed_listing_types),
            )
        )

        if status:
            stmt = stmt.where(LeadFollowUp.status == status)

        now = datetime.now(UTC)
        if is_overdue:
            stmt = stmt.where(LeadFollowUp.due_at < now)
        else:
            if due_start is not None:
                stmt = stmt.where(LeadFollowUp.due_at >= due_start)
            if due_end is not None:
                stmt = stmt.where(LeadFollowUp.due_at <= due_end)

        stmt = stmt.order_by(LeadFollowUp.due_at.asc(), LeadFollowUp.id.asc())
        stmt = stmt.limit(limit).offset(offset)

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def update_followup(
        self,
        session: AsyncSession,
        followup_id: int,
        **values: Any,
    ) -> LeadFollowUp | None:
        """Update follow-up attributes."""
        stmt = (
            update(LeadFollowUp)
            .where(LeadFollowUp.id == followup_id)
            .values(**values)
            .execution_options(synchronize_session="fetch")
        )
        await session.execute(stmt)
        await session.flush()
        return await self.get_followup_by_id(session, followup_id)

    # --- Notes ---

    async def create_note(
        self,
        session: AsyncSession,
        *,
        lead_id: int,
        author_user_id: int,
        text: str,
    ) -> LeadNote:
        """Create an internal broker note."""
        note = LeadNote(
            lead_id=lead_id,
            author_user_id=author_user_id,
            text=text,
        )
        session.add(note)
        await session.flush()
        return note

    async def list_notes(
        self,
        session: AsyncSession,
        lead_id: int,
        limit: int = 50,
    ) -> list[LeadNote]:
        """Fetch notes for a lead, latest first."""
        stmt = (
            select(LeadNote)
            .options(selectinload(LeadNote.author))
            .where(LeadNote.lead_id == lead_id)
            .order_by(LeadNote.created_at.desc(), LeadNote.id.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    # --- Events (Audit Trail) ---

    async def create_event(
        self,
        session: AsyncSession,
        *,
        lead_id: int,
        actor_user_id: int | None = None,
        event_type: str,
        old_value: str | None = None,
        new_value: str | None = None,
        metadata_json: str | None = None,
    ) -> LeadEvent:
        """Record an audit trail event for a lead."""
        event = LeadEvent(
            lead_id=lead_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            old_value=old_value,
            new_value=new_value,
            metadata_json=metadata_json,
        )
        session.add(event)
        await session.flush()
        return event

    async def list_events(
        self,
        session: AsyncSession,
        lead_id: int,
        limit: int = 50,
    ) -> list[LeadEvent]:
        """Fetch audit events for a lead, latest first."""
        stmt = (
            select(LeadEvent)
            .options(selectinload(LeadEvent.actor))
            .where(LeadEvent.lead_id == lead_id)
            .order_by(LeadEvent.created_at.desc(), LeadEvent.id.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
