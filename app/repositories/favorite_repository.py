"""Repository for user favorites database operations."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.favorite import Favorite
from app.models.property import Property


class FavoriteRepository:
    """Handles database access for user favorite listings."""

    async def is_favorite(self, session: AsyncSession, *, user_id: int, property_id: int) -> bool:
        """Check whether a property is favorited by a user."""
        stmt = select(Favorite.id).where(
            Favorite.user_id == user_id, Favorite.property_id == property_id
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def add(self, session: AsyncSession, *, user_id: int, property_id: int) -> Favorite:
        """Add a property to user favorites idempotently."""
        stmt = select(Favorite).where(
            Favorite.user_id == user_id, Favorite.property_id == property_id
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            return existing

        fav = Favorite(user_id=user_id, property_id=property_id)
        session.add(fav)
        await session.flush()
        return fav

    async def remove(self, session: AsyncSession, *, user_id: int, property_id: int) -> bool:
        """Remove a property from user favorites idempotently. Return True if removed."""
        stmt = delete(Favorite).where(
            Favorite.user_id == user_id, Favorite.property_id == property_id
        )
        result = await session.execute(stmt)
        await session.flush()
        return (result.rowcount or 0) > 0

    async def list_approved_properties_by_user(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Property]:
        """Fetch approved saved properties for a specific user ordered by favorite timestamp.

        CRITICAL SECURITY & CONSISTENCY RULE:
        Only returns properties that are currently approved.
        If a favorited property became sold, rented, rejected, or archived,
        it is hidden from active results.
        """
        stmt = (
            select(Property)
            .join(Favorite, Favorite.property_id == Property.id)
            .options(selectinload(Property.media))
            .where(Favorite.user_id == user_id, Property.status == "approved")
            .order_by(Favorite.created_at.desc(), Property.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
