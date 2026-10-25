"""Service for managing user favorite properties."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PropertyNotFoundError
from app.logging import get_logger
from app.models.favorite import Favorite
from app.models.property import Property
from app.repositories.favorite_repository import FavoriteRepository
from app.repositories.property_repository import PropertyRepository

logger = get_logger(__name__)


class FavoriteService:
    """Business service for favorite properties and saved inventory."""

    def __init__(
        self,
        favorite_repo: FavoriteRepository | None = None,
        property_repo: PropertyRepository | None = None,
    ) -> None:
        self.favorite_repo = favorite_repo or FavoriteRepository()
        self.property_repo = property_repo or PropertyRepository()

    async def add_favorite(
        self, session: AsyncSession, *, user_id: int, property_id: int
    ) -> Favorite:
        """Add property to favorites, ensuring the property is approved and active.

        CRITICAL SECURITY RULE:
        Users can only favorite approved inventory. Drafts, submitted, under review,
        or rejected properties are rejected with PropertyNotFoundError.
        """
        prop = await self.property_repo.get_approved_by_id(session, property_id)
        if not prop:
            logger.warning(
                "Attempted to favorite non-approved or missing property id=%s user_id=%s",
                property_id,
                user_id,
            )
            raise PropertyNotFoundError("Ko‘chmas mulk topilmadi yoki faol emas.")

        fav = await self.favorite_repo.add(session, user_id=user_id, property_id=property_id)
        return fav

    async def remove_favorite(
        self, session: AsyncSession, *, user_id: int, property_id: int
    ) -> bool:
        """Remove a property from favorites idempotently."""
        return await self.favorite_repo.remove(session, user_id=user_id, property_id=property_id)

    async def is_favorite(self, session: AsyncSession, *, user_id: int, property_id: int) -> bool:
        """Check if property is in user's favorites."""
        return await self.favorite_repo.is_favorite(
            session, user_id=user_id, property_id=property_id
        )

    async def list_saved_properties(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Property]:
        """Return user's active, approved favorite properties."""
        return await self.favorite_repo.list_approved_properties_by_user(
            session, user_id=user_id, limit=limit, offset=offset
        )
