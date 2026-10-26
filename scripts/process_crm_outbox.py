#!/usr/bin/env python3
"""Operational CLI tool for managing and processing the UyAI CRM Outbox.

Usage:
    python3 scripts/process_crm_outbox.py --status
    python3 scripts/process_crm_outbox.py --process [--batch-size 20]
    python3 scripts/process_crm_outbox.py --retry-failed
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.database.session import get_session_factory
from app.integrations.amocrm.client import AmoCRMClient
from app.integrations.amocrm.constants import STATUS_FAILED, STATUS_PENDING
from app.integrations.amocrm.mapper import AmoCRMMapper
from app.integrations.amocrm.provider import RealAmoCRMProvider
from app.integrations.amocrm.service import AmoCRMService
from app.models.crm_sync import CRMSyncEvent


async def show_status(session: AsyncSession, service: AmoCRMService) -> None:
    """Print outbox status and queue depths safely."""
    stats = await service.get_outbox_stats(session)
    settings = get_settings()

    print("\n=== UyAI CRM Outbox Status ===")
    print(f"amoCRM Integration Enabled: {settings.amocrm_enabled}")
    base_url = settings.get_effective_amocrm_base_url()
    print(f"Base URL:                   {base_url or 'None'}")
    print(f"Pending Events:             {stats['pending']}")
    print(f"Processing Events:          {stats['processing']}")
    print(f"Succeeded Events:           {stats['succeeded']}")
    print(f"Failed / Dead Events:       {stats['failed']}")
    print(f"Last Succeeded Sync:        {stats['last_succeeded_at'] or 'Never'}")
    print("==============================\n")


async def process_events(
    session: AsyncSession, service: AmoCRMService, batch_size: int = 20
) -> int:
    """Process pending outbox events."""
    print(f"Processing up to {batch_size} pending CRM outbox events...")
    recovered = await service.recover_stuck_events(session)
    if recovered > 0:
        print(f"Recovered {recovered} stuck events back to pending.")

    processed = await service.process_outbox_events(session, batch_size=batch_size)
    print(f"Done. Successfully processed {processed} events.")
    return processed


async def retry_failed_events(session: AsyncSession) -> int:
    """Reset dead/failed events back to pending."""
    now = datetime.now(UTC)
    stmt = (
        update(CRMSyncEvent)
        .where(
            CRMSyncEvent.provider == "amocrm",
            CRMSyncEvent.status == STATUS_FAILED,
        )
        .values(
            status=STATUS_PENDING,
            attempt_count=0,
            next_attempt_at=now,
            last_error_safe=None,
        )
    )
    result = await session.execute(stmt)
    await session.commit()
    count = result.rowcount
    print(f"Reset {count} failed events back to pending for retry.")
    return count


async def main() -> int:
    parser = argparse.ArgumentParser(description="UyAI CRM Outbox Manager")
    parser.add_argument("--status", action="store_true", help="Display current outbox queue status")
    parser.add_argument("--process", action="store_true", help="Process pending outbox events")
    parser.add_argument(
        "--retry-failed", action="store_true", help="Reset failed events back to pending"
    )
    parser.add_argument("--batch-size", type=int, default=20, help="Batch size for processing")

    args = parser.parse_args()

    if not (args.status or args.process or args.retry_failed):
        parser.print_help()
        return 0

    settings = get_settings()
    session_factory: async_sessionmaker[AsyncSession] = get_session_factory()

    client = AmoCRMClient(settings=settings)
    provider = RealAmoCRMProvider(client=client)
    mapper = AmoCRMMapper(settings=settings)
    service = AmoCRMService(settings=settings, provider=provider, mapper=mapper)

    try:
        async with session_factory() as session:
            if args.status:
                await show_status(session, service)
            if args.retry_failed:
                await retry_failed_events(session)
            if args.process:
                await process_events(session, service, batch_size=args.batch_size)
    finally:
        await client.close()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
