"""Repository for Property database operations."""

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.property import Property


class PropertyRepository:
    """Handles database access for Property entities."""

    async def create_draft(
        self,
        session: AsyncSession,
        *,
        owner_user_id: int,
        listing_type: str,
        property_type: str,
        region: str,
        district: str,
        address: str,
        rooms: int,
        total_area: Decimal,
        condition: str,
        price: Decimal,
        currency: str = "USD",
        negotiable: bool = False,
        living_area: Decimal | None = None,
        floor: int | None = None,
        total_floors: int | None = None,
        latitude: Decimal | None = None,
        longitude: Decimal | None = None,
        construction_type: str | None = None,
        has_furniture: bool = False,
        cadastre_status: str = "unknown",
        title: str | None = None,
        description: str | None = None,
    ) -> Property:
        """Create and persist a new draft Property."""
        prop = Property(
            owner_user_id=owner_user_id,
            listing_type=listing_type,
            property_type=property_type,
            title=title,
            description=description,
            region=region,
            district=district,
            address=address,
            latitude=latitude,
            longitude=longitude,
            rooms=rooms,
            total_area=total_area,
            living_area=living_area,
            floor=floor,
            total_floors=total_floors,
            condition=condition,
            construction_type=construction_type,
            has_furniture=has_furniture,
            cadastre_status=cadastre_status,
            price=price,
            currency=currency,
            negotiable=negotiable,
            status="draft",
        )
        session.add(prop)
        await session.flush()
        return prop

    async def get_by_id(self, session: AsyncSession, property_id: int) -> Property | None:
        """Fetch property by ID including associated media."""
        stmt = (
            select(Property)
            .options(selectinload(Property.media))
            .where(Property.id == property_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_owned_property(
        self, session: AsyncSession, property_id: int, owner_user_id: int
    ) -> Property | None:
        """Fetch property by ID scoped strictly to owner to guarantee isolation."""
        stmt = (
            select(Property)
            .options(selectinload(Property.media))
            .where(Property.id == property_id, Property.owner_user_id == owner_user_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_owned_property(
        self,
        session: AsyncSession,
        property_id: int,
        owner_user_id: int,
        **kwargs: Any,
    ) -> Property | None:
        """Update property attributes strictly scoped to its owner."""
        prop = await self.get_owned_property(session, property_id, owner_user_id)
        if not prop:
            return None

        for key, value in kwargs.items():
            if hasattr(prop, key):
                setattr(prop, key, value)
        await session.flush()
        return prop

    async def list_by_owner(
        self,
        session: AsyncSession,
        owner_user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Property]:
        """Fetch all properties belonging to a specific owner ordered newest first."""
        stmt = (
            select(Property)
            .options(selectinload(Property.media))
            .where(Property.owner_user_id == owner_user_id)
            .order_by(Property.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_status(
        self,
        session: AsyncSession,
        status: str,
        listing_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Property]:
        """List properties by status, optionally filtered by listing_type."""
        stmt = (
            select(Property)
            .options(selectinload(Property.media))
            .where(Property.status == status)
        )
        if listing_type:
            stmt = stmt.where(Property.listing_type == listing_type)

        stmt = stmt.order_by(Property.created_at.asc()).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def set_status(
        self,
        session: AsyncSession,
        property_id: int,
        status: str,
        **kwargs: Any,
    ) -> Property | None:
        """Update status and accompanying metadata for a property."""
        prop = await self.get_by_id(session, property_id)
        if not prop:
            return None

        prop.status = status
        for key, value in kwargs.items():
            if hasattr(prop, key):
                setattr(prop, key, value)

        await session.flush()
        return prop
