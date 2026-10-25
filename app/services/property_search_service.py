"""Service for public property discovery and search."""

import math

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PropertyNotFoundError
from app.logging import get_logger
from app.models.property import Property
from app.repositories.property_repository import PropertyRepository
from app.schemas.property_search import PropertySearchFilters

logger = get_logger(__name__)


class PropertySearchService:
    """Service handling public property searches and detail views for approved inventory."""

    def __init__(self, property_repo: PropertyRepository | None = None) -> None:
        self.property_repo = property_repo or PropertyRepository()

    async def search(
        self,
        session: AsyncSession,
        filters: PropertySearchFilters,
        page: int = 1,
        page_size: int = 5,
    ) -> tuple[list[Property], int, int]:
        """Search approved inventory deterministically and return (items, total_count, total_pages).

        CRITICAL SECURITY RULE:
        Only approved properties matching the requested listing_type and filters are returned.
        """
        page = max(1, page)
        page_size = max(1, min(page_size, 50))
        offset = (page - 1) * page_size

        items, total_count = await self.property_repo.search_approved(
            session, filters=filters, limit=page_size, offset=offset
        )

        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
        return items, total_count, total_pages

    async def get_approved_details(self, session: AsyncSession, property_id: int) -> Property:
        """Fetch public details for an approved property.

        CRITICAL SECURITY & PRIVACY RULE:
        Rejects draft, submitted, under_review, rejected, archived, sold, or rented properties.
        """
        prop = await self.property_repo.get_approved_by_id(session, property_id)
        if not prop:
            raise PropertyNotFoundError("Ko‘chmas mulk topilmadi yoki faol emas.")
        return prop
