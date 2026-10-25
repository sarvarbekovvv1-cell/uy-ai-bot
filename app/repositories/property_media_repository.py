"""Repository for PropertyMedia database operations."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property_media import PropertyMedia


class PropertyMediaRepository:
    """Handles database access for PropertyMedia entities."""

    async def add_media(
        self,
        session: AsyncSession,
        *,
        property_id: int,
        telegram_file_id: str,
        telegram_file_unique_id: str,
        media_type: str = "photo",
        sort_order: int = 0,
    ) -> PropertyMedia:
        """Add media record to property, avoiding duplicate telegram_file_unique_id."""
        existing = await self.get_by_unique_id(session, property_id, telegram_file_unique_id)
        if existing:
            return existing

        media = PropertyMedia(
            property_id=property_id,
            telegram_file_id=telegram_file_id,
            telegram_file_unique_id=telegram_file_unique_id,
            media_type=media_type,
            sort_order=sort_order,
        )
        session.add(media)
        await session.flush()
        return media

    async def get_by_unique_id(
        self, session: AsyncSession, property_id: int, telegram_file_unique_id: str
    ) -> PropertyMedia | None:
        """Find media item by unique file ID for given property."""
        stmt = select(PropertyMedia).where(
            PropertyMedia.property_id == property_id,
            PropertyMedia.telegram_file_unique_id == telegram_file_unique_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_property(
        self, session: AsyncSession, property_id: int
    ) -> list[PropertyMedia]:
        """List all media for a property sorted by sort_order."""
        stmt = (
            select(PropertyMedia)
            .where(PropertyMedia.property_id == property_id)
            .order_by(PropertyMedia.sort_order.asc(), PropertyMedia.id.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_property(self, session: AsyncSession, property_id: int) -> int:
        """Count total media items for a property."""
        stmt = select(func.count(PropertyMedia.id)).where(PropertyMedia.property_id == property_id)
        result = await session.execute(stmt)
        return result.scalar_one() or 0
