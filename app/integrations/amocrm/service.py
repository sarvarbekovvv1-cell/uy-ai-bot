"""High-level synchronization service coordinating outbox events and amoCRM."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.integrations.amocrm.constants import (
    EVENT_LEAD_CREATED,
    EVENT_NOTE_ADDED,
    EVENT_STAGE_UPDATED,
    INITIAL_BACKOFF_SECONDS,
    MAX_BACKOFF_SECONDS,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_PROCESSING,
    STATUS_SUCCEEDED,
    STUCK_PROCESSING_TIMEOUT_MINUTES,
)
from app.integrations.amocrm.exceptions import (
    AmoCRMDisabledError,
    AmoCRMPermanentError,
    AmoCRMRateLimitError,
    AmoCRMTemporaryError,
    AmoCRMValidationError,
)
from app.integrations.amocrm.mapper import AmoCRMMapper
from app.integrations.amocrm.provider import AmoCRMProviderProtocol
from app.logging import get_logger
from app.models.crm_sync import CRMEntityLink, CRMSyncEvent
from app.models.lead import Lead
from app.models.user import User

logger = get_logger(__name__)


class AmoCRMService:
    """Service orchestrating transactional outbox persistence and CRM synchronization."""

    def __init__(
        self,
        settings: Settings,
        provider: AmoCRMProviderProtocol,
        mapper: AmoCRMMapper | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.mapper = mapper or AmoCRMMapper(settings)

    async def enqueue_sync_event(
        self,
        session: AsyncSession,
        *,
        event_type: str,
        entity_type: str,
        entity_id: int,
        payload: dict[str, Any] | None = None,
    ) -> CRMSyncEvent:
        """Enqueue an outbox event in the active database transaction.

        Guarantees that CRM event creation is atomically bound to the local business transaction.
        """
        payload_json = json.dumps(payload) if payload else None
        event = CRMSyncEvent(
            provider="amocrm",
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload_json=payload_json,
            status=STATUS_PENDING,
            attempt_count=0,
            next_attempt_at=datetime.now(UTC),
        )
        session.add(event)
        await session.flush()
        logger.info(
            "Enqueued CRM outbox event id=%d type=%s for %s:%d",
            event.id,
            event_type,
            entity_type,
            entity_id,
        )
        return event

    async def get_entity_link(
        self,
        session: AsyncSession,
        *,
        local_entity_type: str,
        local_entity_id: int,
        external_entity_type: str,
        provider: str = "amocrm",
    ) -> CRMEntityLink | None:
        """Fetch existing entity mapping."""
        stmt = select(CRMEntityLink).where(
            CRMEntityLink.provider == provider,
            CRMEntityLink.local_entity_type == local_entity_type,
            CRMEntityLink.local_entity_id == local_entity_id,
            CRMEntityLink.external_entity_type == external_entity_type,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def record_entity_link(
        self,
        session: AsyncSession,
        *,
        local_entity_type: str,
        local_entity_id: int,
        external_entity_type: str,
        external_entity_id: str,
        provider: str = "amocrm",
    ) -> CRMEntityLink:
        """Create or update deterministic external entity mapping."""
        existing = await self.get_entity_link(
            session,
            local_entity_type=local_entity_type,
            local_entity_id=local_entity_id,
            external_entity_type=external_entity_type,
            provider=provider,
        )
        if existing:
            existing.external_entity_id = external_entity_id
            existing.updated_at = datetime.now(UTC)
            await session.flush()
            return existing

        link = CRMEntityLink(
            provider=provider,
            local_entity_type=local_entity_type,
            local_entity_id=local_entity_id,
            external_entity_type=external_entity_type,
            external_entity_id=external_entity_id,
        )
        session.add(link)
        await session.flush()
        return link

    async def get_local_lead_id_by_external_id(
        self,
        session: AsyncSession,
        external_lead_id: str,
        provider: str = "amocrm",
    ) -> int | None:
        """Lookup local lead ID given amoCRM lead ID."""
        stmt = select(CRMEntityLink.local_entity_id).where(
            CRMEntityLink.provider == provider,
            CRMEntityLink.local_entity_type == "lead",
            CRMEntityLink.external_entity_type == "lead",
            CRMEntityLink.external_entity_id == str(external_lead_id),
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _sync_contact_for_user(
        self,
        session: AsyncSession,
        user: User,
    ) -> str:
        """Ensure customer is mapped to an amoCRM Contact. Returns external contact ID."""
        link = await self.get_entity_link(
            session,
            local_entity_type="user",
            local_entity_id=user.id,
            external_entity_type="contact",
        )
        if link:
            return link.external_entity_id

        # Normalize phone
        normalized_phone = self.mapper.normalize_phone(user.phone) or "+998000000000"
        name = self.mapper.build_contact_name(user)
        lang = user.language

        external_contact_id = await self.provider.create_or_update_contact(
            name=name,
            phone=normalized_phone,
            lang=lang,
        )
        await self.record_entity_link(
            session,
            local_entity_type="user",
            local_entity_id=user.id,
            external_entity_type="contact",
            external_entity_id=external_contact_id,
        )
        return external_contact_id

    async def sync_single_event(
        self,
        session: AsyncSession,
        event: CRMSyncEvent,
    ) -> None:
        """Execute single CRM sync event through provider."""
        if not self.settings.amocrm_enabled:
            raise AmoCRMDisabledError("amoCRM is disabled by configuration.")

        if event.event_type == EVENT_LEAD_CREATED:
            lead = await session.get(Lead, event.entity_id)
            if not lead:
                logger.warning(
                    "Lead id=%d not found during sync. Marking event dead.", event.entity_id
                )
                return

            # Check if lead is already linked in amoCRM
            link = await self.get_entity_link(
                session,
                local_entity_type="lead",
                local_entity_id=lead.id,
                external_entity_type="lead",
            )
            if link:
                # Already created in amoCRM; update stage/status to ensure consistency
                status_id = self.mapper.resolve_status_id(lead.stage)
                if status_id:
                    await self.provider.update_lead_stage(link.external_entity_id, status_id)
                return

            # Ensure customer contact exists
            contact_id = await self._sync_contact_for_user(session, lead.customer)

            # Build lead payload
            title = self.mapper.build_lead_title(lead)
            status_id = self.mapper.resolve_status_id(lead.stage)
            if status_id is None:
                raise AmoCRMPermanentError(
                    f"Missing amoCRM status_id mapping for stage: '{lead.stage}'. "
                    "Please configure AMOCRM_STAGE_MAPPING_JSON."
                )
            price = int(lead.property.price) if lead.property and lead.property.price else 0
            responsible_id = self.mapper.resolve_responsible_user_id(lead.broker_user_id)

            external_lead_id = await self.provider.create_lead(
                title=title,
                status_id=status_id,
                pipeline_id=self.settings.amocrm_pipeline_id,
                contact_id=contact_id,
                price=price,
                responsible_user_id=responsible_id,
            )

            # Record entity link immediately
            await self.record_entity_link(
                session,
                local_entity_type="lead",
                local_entity_id=lead.id,
                external_entity_type="lead",
                external_entity_id=external_lead_id,
            )

            # Attach safe property context note
            summary_note = self.mapper.build_property_summary_note(lead)
            try:
                await self.provider.add_lead_note(external_lead_id, summary_note)
            except Exception as note_err:
                logger.warning(
                    "Failed to attach property summary note to lead %s: %s",
                    external_lead_id,
                    note_err,
                )

        elif event.event_type == EVENT_STAGE_UPDATED:
            link = await self.get_entity_link(
                session,
                local_entity_type="lead",
                local_entity_id=event.entity_id,
                external_entity_type="lead",
            )
            if not link:
                # If lead has not been created in CRM yet, create it now
                lead = await session.get(Lead, event.entity_id)
                if lead:
                    event_copy = CRMSyncEvent(
                        event_type=EVENT_LEAD_CREATED,
                        entity_type="lead",
                        entity_id=lead.id,
                    )
                    await self.sync_single_event(session, event_copy)
                return

            # Extract target stage from payload or current lead
            target_stage = None
            if event.payload_json:
                try:
                    payload = json.loads(event.payload_json)
                    target_stage = payload.get("target_stage")
                except Exception:
                    pass

            if not target_stage:
                lead = await session.get(Lead, event.entity_id)
                target_stage = lead.stage if lead else "new"

            status_id = self.mapper.resolve_status_id(target_stage)
            if status_id is None:
                raise AmoCRMPermanentError(
                    f"Missing amoCRM status_id mapping for stage: '{target_stage}'. "
                    "Please configure AMOCRM_STAGE_MAPPING_JSON."
                )
            await self.provider.update_lead_stage(
                link.external_entity_id,
                status_id=status_id,
                pipeline_id=self.settings.amocrm_pipeline_id,
            )

        elif event.event_type == EVENT_NOTE_ADDED:
            link = await self.get_entity_link(
                session,
                local_entity_type="lead",
                local_entity_id=event.entity_id,
                external_entity_type="lead",
            )
            if not link:
                return

            note_text = None
            if event.payload_json:
                try:
                    payload = json.loads(event.payload_json)
                    note_text = payload.get("note_text")
                except Exception:
                    pass

            if note_text:
                await self.provider.add_lead_note(link.external_entity_id, note_text)

    async def process_outbox_events(
        self,
        session: AsyncSession,
        *,
        batch_size: int = 20,
    ) -> int:
        """Process pending outbox events whose next_attempt_at is due."""
        if not self.settings.amocrm_enabled:
            return 0

        now = datetime.now(UTC)

        # Select pending events
        stmt = (
            select(CRMSyncEvent)
            .where(
                CRMSyncEvent.provider == "amocrm",
                CRMSyncEvent.status == STATUS_PENDING,
                CRMSyncEvent.next_attempt_at <= now,
            )
            .order_by(CRMSyncEvent.created_at.asc())
            .limit(batch_size)
        )
        if session.bind and session.bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)
        result = await session.execute(stmt)
        events = list(result.scalars().all())

        if not events:
            return 0

        processed_count = 0
        max_retries = self.settings.amocrm_max_retries or 5

        for event in events:
            # Mark processing
            event.status = STATUS_PROCESSING
            await session.commit()

            try:
                await self.sync_single_event(session, event)
                event.status = STATUS_SUCCEEDED
                event.processed_at = datetime.now(UTC)
                event.last_error_safe = None
                await session.commit()
                processed_count += 1
                logger.info("Successfully synchronized CRM event id=%d", event.id)

            except AmoCRMRateLimitError as rle:
                event.attempt_count += 1
                event.status = STATUS_PENDING
                event.next_attempt_at = datetime.now(UTC) + timedelta(seconds=rle.retry_after)
                event.last_error_safe = f"RateLimit: Retry after {rle.retry_after:.1f}s"
                await session.commit()
                logger.warning(
                    "CRM event id=%d rate limited, backing off %.1fs",
                    event.id,
                    rle.retry_after,
                )

            except (AmoCRMTemporaryError, Exception) as temp_err:
                event.attempt_count += 1
                safe_msg = f"{type(temp_err).__name__}: {str(temp_err)[:150]}"

                is_permanent = isinstance(
                    temp_err, (AmoCRMPermanentError, AmoCRMValidationError)
                )
                if event.attempt_count >= max_retries or is_permanent:
                    event.status = STATUS_FAILED
                    event.last_error_safe = f"PERMANENT_FAILURE: {safe_msg}"
                    await session.commit()
                    logger.error(
                        "CRM event id=%d marked dead after %d attempts: %s",
                        event.id,
                        event.attempt_count,
                        safe_msg,
                    )
                else:
                    backoff = min(
                        INITIAL_BACKOFF_SECONDS * (2 ** (event.attempt_count - 1)),
                        MAX_BACKOFF_SECONDS,
                    )
                    event.status = STATUS_PENDING
                    event.next_attempt_at = datetime.now(UTC) + timedelta(seconds=backoff)
                    event.last_error_safe = safe_msg
                    await session.commit()
                    logger.warning(
                        "CRM event id=%d temporary failure, retry %d in %ds: %s",
                        event.id,
                        event.attempt_count,
                        backoff,
                        safe_msg,
                    )

        return processed_count

    async def recover_stuck_events(
        self,
        session: AsyncSession,
        *,
        timeout_minutes: int = STUCK_PROCESSING_TIMEOUT_MINUTES,
    ) -> int:
        """Reset events stuck in 'processing' state due to worker crashes back to 'pending'."""
        cutoff = datetime.now(UTC) - timedelta(minutes=timeout_minutes)
        stmt = (
            update(CRMSyncEvent)
            .where(
                CRMSyncEvent.provider == "amocrm",
                CRMSyncEvent.status == STATUS_PROCESSING,
                CRMSyncEvent.next_attempt_at <= cutoff,
            )
            .values(
                status=STATUS_PENDING,
                last_error_safe="Recovered from worker crash / stuck processing timeout",
            )
        )
        result = await session.execute(stmt)
        await session.commit()
        recovered = result.rowcount
        if recovered > 0:
            logger.warning("Recovered %d stuck CRM events back to pending", recovered)
        return recovered

    async def get_outbox_stats(self, session: AsyncSession) -> dict[str, Any]:
        """Return operational observability stats for CRM outbox."""
        stmt = select(
            CRMSyncEvent.status,
            func.count(CRMSyncEvent.id),
        ).group_by(CRMSyncEvent.status)
        result = await session.execute(stmt)
        counts = {row[0]: row[1] for row in result.all()}

        # Last successful sync
        stmt_last = select(func.max(CRMSyncEvent.processed_at)).where(
            CRMSyncEvent.status == STATUS_SUCCEEDED
        )
        last_succeeded = await session.scalar(stmt_last)

        return {
            "pending": counts.get(STATUS_PENDING, 0),
            "processing": counts.get(STATUS_PROCESSING, 0),
            "succeeded": counts.get(STATUS_SUCCEEDED, 0),
            "failed": counts.get(STATUS_FAILED, 0),
            "last_succeeded_at": last_succeeded.isoformat() if last_succeeded else None,
        }
