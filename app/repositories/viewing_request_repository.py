"""Repository for ViewingRequest database operations."""

from datetime import date
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.property import Property
from app.models.viewing_request import ViewingRequest


class ViewingRequestRepository:
    """Handles database access for ViewingRequest entities."""

    async def create(
        self,
        session: AsyncSession,
        *,
        property_id: int,
        customer_user_id: int,
        request_type: str,
        preferred_date: date | None = None,
        preferred_time: str | None = None,
        customer_comment: str | None = None,
        broker_user_id: int | None = None,
    ) -> ViewingRequest:
        """Create and persist a new viewing or broker contact request."""
        req = ViewingRequest(
            property_id=property_id,
            customer_user_id=customer_user_id,
            request_type=request_type,
            preferred_date=preferred_date,
            preferred_time=preferred_time,
            customer_comment=customer_comment,
            broker_user_id=broker_user_id,
            status="pending",
        )
        session.add(req)
        await session.flush()
        return req

    async def get_by_id(self, session: AsyncSession, request_id: int) -> ViewingRequest | None:
        """Fetch viewing request by ID with property, media, customer, and broker loaded."""
        stmt = (
            select(ViewingRequest)
            .options(
                selectinload(ViewingRequest.property).selectinload(Property.media),
                selectinload(ViewingRequest.customer),
                selectinload(ViewingRequest.broker),
            )
            .where(ViewingRequest.id == request_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_customer(
        self,
        session: AsyncSession,
        customer_user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ViewingRequest]:
        """Fetch viewing requests for a specific customer ordered newest first."""
        stmt = (
            select(ViewingRequest)
            .options(
                selectinload(ViewingRequest.property).selectinload(Property.media),
                selectinload(ViewingRequest.broker),
            )
            .where(ViewingRequest.customer_user_id == customer_user_id)
            .order_by(ViewingRequest.created_at.desc(), ViewingRequest.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_broker(
        self,
        session: AsyncSession,
        *,
        allowed_listing_types: list[str],
        broker_user_id: int | None = None,
        statuses: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ViewingRequest]:
        """Fetch viewing requests eligible for a broker."""
        stmt = (
            select(ViewingRequest)
            .join(Property, Property.id == ViewingRequest.property_id)
            .options(
                selectinload(ViewingRequest.property).selectinload(Property.media),
                selectinload(ViewingRequest.customer),
                selectinload(ViewingRequest.broker),
            )
            .where(Property.listing_type.in_(allowed_listing_types))
        )

        if statuses:
            stmt = stmt.where(ViewingRequest.status.in_(statuses))

        if broker_user_id is not None:
            # Match unassigned or assigned to this broker
            stmt = stmt.where(
                or_(
                    ViewingRequest.broker_user_id.is_(None),
                    ViewingRequest.broker_user_id == broker_user_id,
                )
            )

        stmt = stmt.order_by(ViewingRequest.created_at.desc(), ViewingRequest.id.desc())
        stmt = stmt.limit(limit).offset(offset)

        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def find_active_duplicate(
        self,
        session: AsyncSession,
        *,
        customer_user_id: int,
        property_id: int,
        request_type: str,
        preferred_date: date | None = None,
        preferred_time: str | None = None,
    ) -> ViewingRequest | None:
        """Find an existing active request to prevent spam/duplicates."""
        active_statuses = ["pending", "assigned", "accepted"]
        conditions = [
            ViewingRequest.customer_user_id == customer_user_id,
            ViewingRequest.property_id == property_id,
            ViewingRequest.request_type == request_type,
            ViewingRequest.status.in_(active_statuses),
        ]

        if request_type == "viewing" and preferred_date and preferred_time:
            conditions.extend(
                [
                    ViewingRequest.preferred_date == preferred_date,
                    ViewingRequest.preferred_time == preferred_time,
                ]
            )

        stmt = select(ViewingRequest).where(*conditions).order_by(ViewingRequest.id.desc()).limit(1)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def claim_request(
        self,
        session: AsyncSession,
        *,
        request_id: int,
        broker_user_id: int,
    ) -> bool:
        """Atomically claim a request for a broker."""
        stmt = (
            update(ViewingRequest)
            .where(
                ViewingRequest.id == request_id,
                ViewingRequest.status.in_(["pending", "assigned"]),
                or_(
                    ViewingRequest.broker_user_id.is_(None),
                    ViewingRequest.broker_user_id == broker_user_id,
                ),
            )
            .values(
                broker_user_id=broker_user_id,
                status="assigned",
                updated_at=func.now(),
            )
        )
        result = await session.execute(stmt)
        await session.flush()
        return (result.rowcount or 0) > 0

    async def update_status(
        self,
        session: AsyncSession,
        request_id: int,
        *,
        status: str,
        **kwargs: Any,
    ) -> ViewingRequest | None:
        """Update viewing request status and timestamps."""
        req = await self.get_by_id(session, request_id)
        if not req:
            return None

        req.status = status
        for key, value in kwargs.items():
            if hasattr(req, key):
                setattr(req, key, value)

        await session.flush()
        return req
