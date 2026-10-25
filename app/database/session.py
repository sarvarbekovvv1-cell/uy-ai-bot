"""Async database engine and session management."""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.core.exceptions import DatabaseConnectionError
from app.logging import get_logger

logger = get_logger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return or create singleton AsyncEngine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        if not settings.database_url:
            raise DatabaseConnectionError("Database URL is not configured.")

        # Engine arguments suitable for PostgreSQL with asyncpg
        engine_kwargs: dict[str, Any] = {
            "echo": settings.app_debug,
            "future": True,
        }

        # Connection pool arguments for postgresql
        if "postgresql" in settings.database_url:
            engine_kwargs.update(
                {
                    "pool_size": 10,
                    "max_overflow": 20,
                    "pool_pre_ping": True,
                }
            )

        _engine = create_async_engine(settings.database_url, **engine_kwargs)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return or create singleton async sessionmaker."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_connection() -> bool:
    """Check database connectivity by executing a lightweight query."""
    engine = get_engine()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning(
            "Database connectivity check failed: %s",
            exc.__class__.__name__,
        )
        return False


async def close_db_engine() -> None:
    """Dispose database engine connections gracefully."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
