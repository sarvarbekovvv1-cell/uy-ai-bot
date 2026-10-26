#!/usr/bin/env python3
"""CLI runner daemon for the amoCRM Transactional Outbox Worker."""

import asyncio
import signal
import sys

from app.config import get_settings
from app.database.session import close_db_engine, get_session_factory
from app.integrations.amocrm.service import AmoCRMService
from app.integrations.amocrm.worker import AmoCRMWorker
from app.logging import get_logger, setup_logging

logger = get_logger(__name__)


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("Initializing amoCRM Outbox Worker daemon...")

    if not settings.amocrm_enabled:
        logger.warning(
            "AMOCRM_ENABLED is False. Worker will idle and monitor outbox until enabled."
        )

    service = AmoCRMService(settings)
    session_factory = get_session_factory()
    worker = AmoCRMWorker(service, session_factory=session_factory)

    stop_event = asyncio.Event()

    def handle_signal(sig_name: str) -> None:
        logger.info("Received shutdown signal (%s). Stopping CRM worker...", sig_name)
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda s=sig.name: handle_signal(s))
        except NotImplementedError:
            # Fallback for Windows or environments without full signal support
            pass

    # Worker processing loop with graceful termination
    logger.info("amoCRM Outbox Worker daemon running. Polling interval: 5.0s.")
    try:
        while not stop_event.is_set():
            try:
                async with session_factory() as session:
                    processed = await worker.run_once(session, batch_size=20)
                    if processed > 0:
                        logger.info("Outbox worker processed %d CRM events.", processed)
            except Exception as e:
                logger.error("Error in CRM worker cycle: %s", e)

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=5.0)
            except TimeoutError:
                pass
    finally:
        logger.info("Closing database engine and completing worker shutdown.")
        await close_db_engine()
        logger.info("amoCRM Outbox Worker stopped cleanly.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
