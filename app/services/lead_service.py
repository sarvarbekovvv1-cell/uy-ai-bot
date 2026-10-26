"""Service for Broker Cabinet and Lead Management in UyAI."""

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    FollowUpNotFoundError,
    InvalidLeadTransitionError,
    LeadAlreadyAssignedError,
    LeadNotFoundError,
    LeadPermissionError,
    LeadValidationError,
    PropertyUnavailableError,
)
from app.logging import get_logger
from app.models.lead import (
    ACTIVE_LEAD_STAGES,
    FOLLOWUP_TYPES,
    LEAD_SOURCES,
    LEAD_STAGES,
    LOST_REASONS,
    TERMINAL_LEAD_STAGES,
    Lead,
    LeadFollowUp,
    LeadNote,
)
from app.models.viewing_request import ViewingRequest
from app.repositories.lead_repository import LeadRepository
from app.repositories.property_repository import PropertyRepository
from app.repositories.user_repository import UserRepository
from app.repositories.viewing_request_repository import ViewingRequestRepository

logger = get_logger(__name__)

ALLOWED_STAGE_TRANSITIONS: dict[str, set[str]] = {
    "new": {"contacted", "qualified", "viewing_scheduled", "negotiation", "won", "lost"},
    "contacted": {"qualified", "viewing_scheduled", "negotiation", "won", "lost"},
    "qualified": {"contacted", "viewing_scheduled", "negotiation", "won", "lost"},
    "viewing_scheduled": {"contacted", "qualified", "negotiation", "won", "lost"},
    "negotiation": {"contacted", "qualified", "viewing_scheduled", "won", "lost"},
    "won": set(),
    "lost": set(),
}

STAFF_ROLES: set[str] = {"superadmin", "head_broker", "sales_broker", "rental_broker"}


class LeadService:
    """Service managing broker leads, stage progression, follow-ups, and notes."""

    def __init__(
        self,
        lead_repo: LeadRepository | None = None,
        property_repo: PropertyRepository | None = None,
        user_repo: UserRepository | None = None,
        viewing_repo: ViewingRequestRepository | None = None,
    ) -> None:
        self.lead_repo = lead_repo or LeadRepository()
        self.property_repo = property_repo or PropertyRepository()
        self.user_repo = user_repo or UserRepository()
        self.viewing_repo = viewing_repo or ViewingRequestRepository()

    async def get_broker_allowed_listing_types(
        self, session: AsyncSession, broker_user_id: int
    ) -> list[str]:
        """Determine listing types a broker is authorized to manage.

        Rules:
        - superadmin, head_broker: ['sale', 'rent']
        - sales_broker: ['sale']
        - rental_broker: ['rent']
        - others: empty list (not authorized)
        """
        user = await self.user_repo.get_by_id(session, broker_user_id)
        if not user:
            return []

        user_roles = {r.name for r in user.roles}

        if "superadmin" in user_roles or "head_broker" in user_roles:
            return ["sale", "rent"]
        if "sales_broker" in user_roles:
            return ["sale"]
        if "rental_broker" in user_roles:
            return ["rent"]
        return []

    async def is_head_or_superadmin(self, session: AsyncSession, user_id: int) -> bool:
        """Check if user has elevated management role."""
        user = await self.user_repo.get_by_id(session, user_id)
        if not user:
            return False
        user_roles = {r.name for r in user.roles}
        return bool({"superadmin", "head_broker"} & user_roles)

    async def _enqueue_crm_event(
        self,
        session: AsyncSession,
        *,
        event_type: str,
        lead_id: int,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Enqueue outbox event for CRM synchronization if enabled."""
        from app.config import get_settings
        from app.models.crm_sync import CRMSyncEvent

        if not get_settings().amocrm_enabled:
            return

        event = CRMSyncEvent(
            provider="amocrm",
            event_type=event_type,
            entity_type="lead",
            entity_id=lead_id,
            payload_json=json.dumps(payload) if payload else None,
            status="pending",
            attempt_count=0,
            next_attempt_at=datetime.now(UTC),
        )
        session.add(event)

    def validate_stage_transition(self, current_stage: str, target_stage: str) -> None:
        """Validate state machine stage progression."""
        if target_stage not in LEAD_STAGES:
            raise LeadValidationError(
                f"Noma'lum bosqich '{target_stage}'. Mumkin bo‘lganlar: {LEAD_STAGES}"
            )

        if current_stage in TERMINAL_LEAD_STAGES:
            raise InvalidLeadTransitionError(
                f"Yopilgan lead ({current_stage}) qayta ochilishi yoki o‘zgartirilishi mumkin emas."
            )

        if current_stage == target_stage:
            return

        allowed = ALLOWED_STAGE_TRANSITIONS.get(current_stage, set())
        if target_stage not in allowed:
            raise InvalidLeadTransitionError(
                f"Lead bosqichini '{current_stage}' dan '{target_stage}' ga o‘tkazib bo‘lmaydi."
            )

    async def ensure_lead_for_request(
        self,
        session: AsyncSession,
        *,
        request: ViewingRequest,
        broker_user_id: int | None = None,
    ) -> Lead:
        """Create or link active lead for a viewing or broker contact request.

        Enforces 1 active lead per (customer, property).
        """
        active_lead = await self.lead_repo.get_active_by_customer_property(
            session,
            customer_user_id=request.customer_user_id,
            property_id=request.property_id,
        )

        now = datetime.now(UTC)

        if active_lead:
            # Update lead with source_request if not set
            updates: dict[str, Any] = {}
            if not active_lead.source_request_id:
                updates["source_request_id"] = request.id
            if broker_user_id and not active_lead.broker_user_id:
                updates["broker_user_id"] = broker_user_id
                updates["assigned_at"] = now

            if updates:
                active_lead = await self.lead_repo.update(session, active_lead.id, **updates)
            await self._enqueue_crm_event(
                session, event_type="lead_created", lead_id=active_lead.id
            )
            return active_lead

        # Create new lead
        source = request.request_type if request.request_type in LEAD_SOURCES else "manual"
        lead = await self.lead_repo.create(
            session,
            customer_user_id=request.customer_user_id,
            property_id=request.property_id,
            source=source,
            broker_user_id=broker_user_id,
            source_request_id=request.id,
            stage="new",
            assigned_at=now if broker_user_id else None,
        )

        await self.lead_repo.create_event(
            session,
            lead_id=lead.id,
            actor_user_id=broker_user_id,
            event_type="created",
            new_value="new",
            metadata_json=json.dumps({"source": source, "request_id": request.id}),
        )

        if broker_user_id:
            await self.lead_repo.create_event(
                session,
                lead_id=lead.id,
                actor_user_id=broker_user_id,
                event_type="assigned",
                new_value=str(broker_user_id),
            )

        logger.info(
            "Created lead id=%d for customer_id=%d and prop_id=%d via source=%s",
            lead.id,
            request.customer_user_id,
            request.property_id,
            source,
        )
        await self._enqueue_crm_event(session, event_type="lead_created", lead_id=lead.id)
        return lead

    async def create_lead(
        self,
        session: AsyncSession,
        *,
        customer_user_id: int,
        property_id: int,
        source: str = "manual",
        broker_user_id: int | None = None,
        source_request_id: int | None = None,
    ) -> Lead:
        """Create a new lead manually with deduplication check."""
        # Verify property exists
        prop = await self.property_repo.get_by_id(session, property_id)
        if not prop:
            raise PropertyUnavailableError("Ko‘chmas mulk topilmadi.")

        # Check existing active lead
        existing = await self.lead_repo.get_active_by_customer_property(
            session,
            customer_user_id=customer_user_id,
            property_id=property_id,
        )
        if existing:
            await self._enqueue_crm_event(session, event_type="lead_created", lead_id=existing.id)
            return existing

        now = datetime.now(UTC)
        lead = await self.lead_repo.create(
            session,
            customer_user_id=customer_user_id,
            property_id=property_id,
            source=source,
            broker_user_id=broker_user_id,
            source_request_id=source_request_id,
            stage="new",
            assigned_at=now if broker_user_id else None,
        )

        await self.lead_repo.create_event(
            session,
            lead_id=lead.id,
            actor_user_id=broker_user_id,
            event_type="created",
            new_value="new",
            metadata_json=json.dumps({"source": source}),
        )

        if broker_user_id:
            await self.lead_repo.create_event(
                session,
                lead_id=lead.id,
                actor_user_id=broker_user_id,
                event_type="assigned",
                new_value=str(broker_user_id),
            )

        await self._enqueue_crm_event(session, event_type="lead_created", lead_id=lead.id)
        return lead

    async def get_lead(
        self,
        session: AsyncSession,
        *,
        lead_id: int,
        broker_user_id: int,
    ) -> Lead:
        """Get lead with RBAC check."""
        lead = await self.lead_repo.get_by_id(session, lead_id)
        if not lead:
            raise LeadNotFoundError("Lead topilmadi.")

        allowed_types = await self.get_broker_allowed_listing_types(session, broker_user_id)
        if lead.property.listing_type not in allowed_types:
            raise LeadPermissionError("Sizda ushbu toifadagi leadni ko‘rish vakolati yo‘q.")

        return lead

    async def list_unassigned_leads(
        self,
        session: AsyncSession,
        *,
        broker_user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Lead]:
        """List unassigned active leads available for claiming by this broker."""
        allowed_types = await self.get_broker_allowed_listing_types(session, broker_user_id)
        if not allowed_types:
            raise LeadPermissionError("Sizda broker kabinetiga kirish vakolati yo‘q.")

        return await self.lead_repo.list_leads(
            session,
            allowed_listing_types=allowed_types,
            unassigned_only=True,
            stages=list(ACTIVE_LEAD_STAGES),
            limit=limit,
            offset=offset,
        )

    async def list_my_leads(
        self,
        session: AsyncSession,
        *,
        broker_user_id: int,
        stage: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Lead]:
        """List active leads assigned to this broker."""
        allowed_types = await self.get_broker_allowed_listing_types(session, broker_user_id)
        if not allowed_types:
            raise LeadPermissionError("Sizda broker kabinetiga kirish vakolati yo‘q.")

        stages = [stage] if stage else list(ACTIVE_LEAD_STAGES)
        return await self.lead_repo.list_leads(
            session,
            allowed_listing_types=allowed_types,
            broker_user_id=broker_user_id,
            stages=stages,
            limit=limit,
            offset=offset,
        )

    async def claim_lead(
        self,
        session: AsyncSession,
        *,
        lead_id: int,
        broker_user_id: int,
    ) -> Lead:
        """Assign an unassigned lead to the requesting broker."""
        lead = await self.lead_repo.get_by_id(session, lead_id)
        if not lead:
            raise LeadNotFoundError("Lead topilmadi.")

        allowed_types = await self.get_broker_allowed_listing_types(session, broker_user_id)
        if lead.property.listing_type not in allowed_types:
            raise LeadPermissionError("Sizda ushbu toifadagi leadni olish vakolati yo‘q.")

        if lead.broker_user_id is not None and lead.broker_user_id != broker_user_id:
            raise LeadAlreadyAssignedError("Ushbu lead allaqachon boshqa brokerga biriktirilgan.")

        now = datetime.now(UTC)
        updated = await self.lead_repo.update(
            session,
            lead_id,
            broker_user_id=broker_user_id,
            assigned_at=now,
        )
        if not updated:
            raise LeadNotFoundError("Lead topilmadi.")

        await self.lead_repo.create_event(
            session,
            lead_id=lead_id,
            actor_user_id=broker_user_id,
            event_type="assigned",
            new_value=str(broker_user_id),
        )

        logger.info("Broker id=%d claimed lead id=%d", broker_user_id, lead_id)
        return updated

    async def assign_broker(
        self,
        session: AsyncSession,
        *,
        lead_id: int,
        broker_user_id: int,
        assigned_by_user_id: int,
    ) -> Lead:
        """Assign or reassign a lead to a broker by manager."""
        lead = await self.lead_repo.get_by_id(session, lead_id)
        if not lead:
            raise LeadNotFoundError("Lead topilmadi.")

        target_broker = await self.user_repo.get_by_id(session, broker_user_id)
        if not target_broker or not target_broker.is_active:
            raise LeadValidationError("Yaroqsiz broker tanlandi.")

        allowed_types = await self.get_broker_allowed_listing_types(session, broker_user_id)
        if lead.property.listing_type not in allowed_types:
            raise LeadPermissionError(
                f"Tanlangan broker '{lead.property.listing_type}' toifasidagi e'lonlarni "
                "boshqarish huquqiga ega emas."
            )

        old_broker_id = lead.broker_user_id
        now = datetime.now(UTC)
        updated = await self.lead_repo.update(
            session,
            lead_id,
            broker_user_id=broker_user_id,
            assigned_at=now,
        )
        if not updated:
            raise LeadNotFoundError("Lead topilmadi.")

        await self.lead_repo.create_event(
            session,
            lead_id=lead_id,
            actor_user_id=assigned_by_user_id,
            event_type="assigned",
            old_value=str(old_broker_id) if old_broker_id else None,
            new_value=str(broker_user_id),
        )

        logger.info(
            "Lead id=%d reassigned from broker %s to broker %d by user %d",
            lead_id,
            old_broker_id,
            broker_user_id,
            assigned_by_user_id,
        )
        return updated

    async def update_stage(
        self,
        session: AsyncSession,
        *,
        lead_id: int,
        broker_user_id: int,
        target_stage: str,
        close_reason: str | None = None,
        enqueue_crm: bool = True,
    ) -> Lead:
        """Progress lead to a new stage."""
        lead = await self.lead_repo.get_by_id(session, lead_id)
        if not lead:
            raise LeadNotFoundError("Lead topilmadi.")

        allowed_types = await self.get_broker_allowed_listing_types(session, broker_user_id)
        if lead.property.listing_type not in allowed_types:
            raise LeadPermissionError("Sizda ushbu leadni boshqarish vakolati yo‘q.")

        is_manager = await self.is_head_or_superadmin(session, broker_user_id)
        if not is_manager and lead.broker_user_id != broker_user_id:
            raise LeadPermissionError("Siz faqat o‘zingizga biriktirilgan leadni boshqara olasiz.")

        self.validate_stage_transition(lead.stage, target_stage)

        now = datetime.now(UTC)
        updates: dict[str, Any] = {"stage": target_stage}

        if target_stage == "contacted" and not lead.contacted_at:
            updates["contacted_at"] = now
        elif target_stage == "qualified" and not lead.qualified_at:
            updates["qualified_at"] = now
        elif target_stage == "viewing_scheduled" and not lead.viewing_at:
            updates["viewing_at"] = now
        elif target_stage in TERMINAL_LEAD_STAGES:
            updates["closed_at"] = now
            if target_stage == "lost":
                if not close_reason or close_reason not in LOST_REASONS:
                    raise LeadValidationError(
                        f"Yo‘qotish sababini tanlang. Mumkin bo‘lganlar: {LOST_REASONS}"
                    )
                updates["close_reason"] = close_reason

        updated = await self.lead_repo.update(session, lead_id, **updates)
        if not updated:
            raise LeadNotFoundError("Lead topilmadi.")

        # Record stage changed audit event
        await self.lead_repo.create_event(
            session,
            lead_id=lead_id,
            actor_user_id=broker_user_id,
            event_type="stage_changed",
            old_value=lead.stage,
            new_value=target_stage,
            metadata_json=json.dumps({"close_reason": close_reason}) if close_reason else None,
        )

        if target_stage in TERMINAL_LEAD_STAGES:
            await self.lead_repo.create_event(
                session,
                lead_id=lead_id,
                actor_user_id=broker_user_id,
                event_type="closed",
                new_value=target_stage,
            )

        logger.info(
            "Broker id=%d moved lead id=%d from %s to %s",
            broker_user_id,
            lead_id,
            lead.stage,
            target_stage,
        )
        if enqueue_crm:
            await self._enqueue_crm_event(
                session,
                event_type="stage_updated",
                lead_id=lead_id,
                payload={"target_stage": target_stage},
            )
        return updated

    # --- Follow-Up Tasks ---

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
        """Schedule a follow-up task."""
        lead = await self.lead_repo.get_by_id(session, lead_id)
        if not lead:
            raise LeadNotFoundError("Lead topilmadi.")

        allowed_types = await self.get_broker_allowed_listing_types(session, broker_user_id)
        if lead.property.listing_type not in allowed_types:
            raise LeadPermissionError("Sizda ushbu leadga vazifa biriktirish vakolati yo‘q.")

        is_manager = await self.is_head_or_superadmin(session, broker_user_id)
        if not is_manager and lead.broker_user_id != broker_user_id:
            raise LeadPermissionError("Siz faqat o‘zingizning ledingizga vazifa qo‘sha olasiz.")

        if task_type not in FOLLOWUP_TYPES:
            raise LeadValidationError(
                f"Noma'lum vazifa turi '{task_type}'. Mumkin: {FOLLOWUP_TYPES}"
            )

        now = datetime.now(UTC)
        target_due = due_at if due_at.tzinfo is not None else due_at.replace(tzinfo=UTC)
        if target_due <= now:
            raise LeadValidationError("Vazifa muddati kelajakda bo‘lishi shart.")

        followup = await self.lead_repo.create_followup(
            session,
            lead_id=lead_id,
            broker_user_id=broker_user_id,
            task_type=task_type,
            due_at=target_due,
            note=note,
        )

        await self.lead_repo.create_event(
            session,
            lead_id=lead_id,
            actor_user_id=broker_user_id,
            event_type="followup_created",
            new_value=task_type,
            metadata_json=json.dumps(
                {"followup_id": followup.id, "due_at": target_due.isoformat()}
            ),
        )

        return followup

    async def complete_followup(
        self,
        session: AsyncSession,
        *,
        followup_id: int,
        broker_user_id: int,
    ) -> LeadFollowUp:
        """Mark a follow-up task completed."""
        followup = await self.lead_repo.get_followup_by_id(session, followup_id)
        if not followup:
            raise FollowUpNotFoundError("Vazifa topilmadi.")

        is_manager = await self.is_head_or_superadmin(session, broker_user_id)
        if not is_manager and followup.broker_user_id != broker_user_id:
            raise LeadPermissionError("Siz faqat o‘zingizning vazifangizni yakunlay olasiz.")

        now = datetime.now(UTC)
        updated = await self.lead_repo.update_followup(
            session,
            followup_id,
            status="completed",
            completed_at=now,
        )
        if not updated:
            raise FollowUpNotFoundError("Vazifa topilmadi.")

        await self.lead_repo.create_event(
            session,
            lead_id=followup.lead_id,
            actor_user_id=broker_user_id,
            event_type="followup_completed",
            new_value=str(followup_id),
        )

        return updated

    async def cancel_followup(
        self,
        session: AsyncSession,
        *,
        followup_id: int,
        broker_user_id: int,
    ) -> LeadFollowUp:
        """Cancel a follow-up task."""
        followup = await self.lead_repo.get_followup_by_id(session, followup_id)
        if not followup:
            raise FollowUpNotFoundError("Vazifa topilmadi.")

        is_manager = await self.is_head_or_superadmin(session, broker_user_id)
        if not is_manager and followup.broker_user_id != broker_user_id:
            raise LeadPermissionError("Siz faqat o‘zingizning vazifangizni bekor qila olasiz.")

        now = datetime.now(UTC)
        updated = await self.lead_repo.update_followup(
            session,
            followup_id,
            status="cancelled",
            cancelled_at=now,
        )
        if not updated:
            raise FollowUpNotFoundError("Vazifa topilmadi.")

        return updated

    async def list_followups(
        self,
        session: AsyncSession,
        *,
        broker_user_id: int,
        filter_type: str = "all",  # "all", "today", "overdue"
        limit: int = 50,
        offset: int = 0,
    ) -> list[LeadFollowUp]:
        """List follow-ups for a broker with filtering."""
        allowed_types = await self.get_broker_allowed_listing_types(session, broker_user_id)
        if not allowed_types:
            raise LeadPermissionError("Sizda broker kabinetiga kirish vakolati yo‘q.")

        now = datetime.now(UTC)
        if filter_type == "overdue":
            return await self.lead_repo.list_followups_for_broker(
                session,
                broker_user_id=broker_user_id,
                allowed_listing_types=allowed_types,
                status="pending",
                is_overdue=True,
                limit=limit,
                offset=offset,
            )
        elif filter_type == "today":
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            return await self.lead_repo.list_followups_for_broker(
                session,
                broker_user_id=broker_user_id,
                allowed_listing_types=allowed_types,
                status="pending",
                is_overdue=False,
                due_start=start_of_day,
                due_end=end_of_day,
                limit=limit,
                offset=offset,
            )

        return await self.lead_repo.list_followups_for_broker(
            session,
            broker_user_id=broker_user_id,
            allowed_listing_types=allowed_types,
            status="pending",
            limit=limit,
            offset=offset,
        )

    # --- Notes ---

    async def add_note(
        self,
        session: AsyncSession,
        *,
        lead_id: int,
        author_user_id: int,
        text: str,
    ) -> LeadNote:
        """Add an internal broker note to a lead."""
        lead = await self.lead_repo.get_by_id(session, lead_id)
        if not lead:
            raise LeadNotFoundError("Lead topilmadi.")

        allowed_types = await self.get_broker_allowed_listing_types(session, author_user_id)
        if lead.property.listing_type not in allowed_types:
            raise LeadPermissionError("Sizda ushbu leadga eslatma qo‘shish vakolati yo‘q.")

        clean_text = (text or "").strip()
        if not clean_text:
            raise LeadValidationError("Eslatma matni bo‘sh bo‘lishi mumkin emas.")

        note = await self.lead_repo.create_note(
            session,
            lead_id=lead_id,
            author_user_id=author_user_id,
            text=clean_text,
        )

        await self.lead_repo.create_event(
            session,
            lead_id=lead_id,
            actor_user_id=author_user_id,
            event_type="note_added",
        )

        await self._enqueue_crm_event(
            session,
            event_type="note_added",
            lead_id=lead_id,
            payload={"note_text": clean_text},
        )

        return note

    # --- Metrics & Statistics ---

    async def get_broker_stats(
        self,
        session: AsyncSession,
        *,
        broker_user_id: int,
    ) -> dict[str, Any]:
        """Aggregate counts for broker cabinet dashboard."""
        allowed_types = await self.get_broker_allowed_listing_types(session, broker_user_id)
        if not allowed_types:
            raise LeadPermissionError("Sizda broker kabinetiga kirish vakolati yo‘q.")

        stage_counts = await self.lead_repo.count_by_stage_for_broker(
            session,
            allowed_listing_types=allowed_types,
            broker_user_id=broker_user_id,
        )

        unassigned_count = await self.lead_repo.count_leads(
            session,
            allowed_listing_types=allowed_types,
            unassigned_only=True,
            stages=list(ACTIVE_LEAD_STAGES),
        )

        my_active_count = await self.lead_repo.count_leads(
            session,
            allowed_listing_types=allowed_types,
            broker_user_id=broker_user_id,
            stages=list(ACTIVE_LEAD_STAGES),
        )

        now = datetime.now(UTC)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)

        today_followups = await self.lead_repo.list_followups_for_broker(
            session,
            broker_user_id=broker_user_id,
            allowed_listing_types=allowed_types,
            status="pending",
            due_start=start_of_day,
            due_end=end_of_day,
        )

        overdue_followups = await self.lead_repo.list_followups_for_broker(
            session,
            broker_user_id=broker_user_id,
            allowed_listing_types=allowed_types,
            status="pending",
            is_overdue=True,
        )

        return {
            "unassigned_count": unassigned_count,
            "my_active_count": my_active_count,
            "today_tasks_count": len(today_followups),
            "overdue_tasks_count": len(overdue_followups),
            "stage_counts": stage_counts,
        }

    # --- Customer Privacy Helper ---

    async def can_view_customer_phone(
        self,
        session: AsyncSession,
        *,
        lead: Lead,
        requester_user_id: int,
    ) -> bool:
        """Customer phone is ONLY visible if requester is assigned broker or manager."""
        if lead.broker_user_id == requester_user_id:
            return True
        return await self.is_head_or_superadmin(session, requester_user_id)
