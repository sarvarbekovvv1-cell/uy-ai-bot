"""Repository for User persistence and query operations."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Handles database access for User entities."""

    async def get_by_id(self, session: AsyncSession, user_id: int) -> User | None:
        """Fetch user by primary key ID."""
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_telegram_id(self, session: AsyncSession, telegram_id: int) -> User | None:
        """Fetch user by Telegram ID."""
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def exists_by_telegram_id(self, session: AsyncSession, telegram_id: int) -> bool:
        """Check whether a user with given Telegram ID exists."""
        stmt = select(User.id).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def create(
        self,
        session: AsyncSession,
        *,
        telegram_id: int,
        language: str = "uz",
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        phone: str | None = None,
        is_verified: bool = False,
        consent_accepted_at: datetime | None = None,
    ) -> User:
        """Create and persist a new user."""
        user = User(
            telegram_id=telegram_id,
            language=language,
            username=username,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            is_verified=is_verified,
            consent_accepted_at=consent_accepted_at,
        )
        session.add(user)
        await session.flush()
        return user

    async def update(
        self,
        session: AsyncSession,
        user: User,
        **kwargs: object,
    ) -> User:
        """Update fields on an existing user instance."""
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        await session.flush()
        return user
