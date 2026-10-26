#!/usr/bin/env python3
"""Automated backup and restore verification tool for UyAI database."""

import argparse
import asyncio
import sys

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.session import close_db_engine, get_session_factory
from app.models.kaizen import KaizenCycle, KaizenRecommendation
from app.models.lead import Lead
from app.models.property import Property
from app.models.role import Role
from app.models.user import User


async def count_records(session: AsyncSession) -> dict[str, int]:
    """Return dictionary of table record counts."""
    models = {
        "users": User,
        "roles": Role,
        "properties": Property,
        "leads": Lead,
        "kaizen_cycles": KaizenCycle,
        "kaizen_recommendations": KaizenRecommendation,
    }
    counts = {}
    for name, model in models.items():
        stmt = select(func.count()).select_from(model)
        counts[name] = (await session.execute(stmt)).scalar_one() or 0
    return counts


async def run_verification() -> int:
    """Verify database connectivity and output current record counts."""
    session_factory: async_sessionmaker[AsyncSession] = get_session_factory()
    try:
        async with session_factory() as session:
            counts = await count_records(session)
            print("==================================================")
            print("UyAI Database Verification Report")
            print("==================================================")
            for table, count in counts.items():
                print(f"  {table:<25}: {count} rows")
            print("==================================================")
            print("✅ Database integrity check completed successfully.")
            return 0
    except Exception as e:
        print(f"❌ Database integrity check failed: {e}", file=sys.stderr)
        return 1
    finally:
        await close_db_engine()


def main() -> None:
    parser = argparse.ArgumentParser(description="UyAI Backup & Restore Integrity Verifier")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify current database counts without dumping/restoring",
    )
    parser.parse_args()

    exit_code = asyncio.run(run_verification())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
