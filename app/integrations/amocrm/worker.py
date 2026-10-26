"""Worker runner for processing amoCRM transactional outbox events."""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.integrations.amocrm.service import AmoCRMService
from app.logging import get_logger

logger = get_logger(__name__)


class AmoCRMWorker:
    """Outbox worker runner for background or scheduled CRM synchronization."""

    def __init__(
        self,
        service: AmoCRMService,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self.service = service
        self.session_factory = session_factory

    async def run_once(self, session: AsyncSession, batch_size: int = 20) -> int:
        """Execute one processing batch of pending outbox events."""
        # First recover any crashed/stuck events
        await self.service.recover_stuck_events(session)
        # Process pending batch
        return await self.service.process_outbox_events(session, batch_size=batch_size)

    async def run_loop(self, interval_seconds: float = 5.0, batch_size: int = 20) -> None:
        """Run continuous processing loop (for worker daemon)."""
        if not self.session_factory:
            raise RuntimeError("session_factory is required to run worker loop.")

        logger.info("Starting amoCRM Outbox Worker daemon (interval=%.1fs)", interval_seconds)
        while True:
            try:
                async with self.session_factory() as session:
                    processed = await self.run_once(session, batch_size=batch_size)
                    if processed > 0:
                        logger.info("Outbox worker processed %d CRM events", processed)
            except Exception as e:
                logger.error("Error in amoCRM outbox worker iteration: %s", e)

            await asyncio.sleep(interval_seconds)
