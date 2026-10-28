"""Repository for ValuationOrder database access."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.valuation_order import ValuationOrder


class ValuationOrderRepository:
    """Handles CRUD operations for monetized property valuation orders."""

    @staticmethod
    def generate_order_id() -> str:
        """Generate human-readable, unique order ID: VAL-YYYYMMDD-XXXXXXXX."""
        today = datetime.now(UTC).strftime("%Y%m%d")
        unique_suffix = uuid.uuid4().hex[:8].upper()
        return f"VAL-{today}-{unique_suffix}"

    async def create_order(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        telegram_id: int,
        property_input: dict[str, Any],
        amount_uzs: Decimal,
        currency: str = "UZS",
    ) -> ValuationOrder:
        """Create and persist a new ValuationOrder in pending state."""
        order_id = self.generate_order_id()
        order = ValuationOrder(
            order_id=order_id,
            user_id=user_id,
            telegram_id=telegram_id,
            property_input=property_input,
            amount_uzs=amount_uzs,
            currency=currency,
            payment_status="pending",
            valuation_status="pending",
        )
        session.add(order)
        await session.flush()
        return order

    async def get_by_order_id(
        self,
        session: AsyncSession,
        order_id: str,
    ) -> ValuationOrder | None:
        """Retrieve valuation order by human-readable order_id with user relationship."""
        stmt = (
            select(ValuationOrder)
            .options(selectinload(ValuationOrder.user))
            .where(ValuationOrder.order_id == order_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(
        self,
        session: AsyncSession,
        order_pk: int,
    ) -> ValuationOrder | None:
        """Retrieve valuation order by primary key."""
        stmt = (
            select(ValuationOrder)
            .options(selectinload(ValuationOrder.user))
            .where(ValuationOrder.id == order_pk)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_pending_for_user(
        self,
        session: AsyncSession,
        user_id: int,
    ) -> ValuationOrder | None:
        """Retrieve the latest pending order for a user."""
        stmt = (
            select(ValuationOrder)
            .where(
                ValuationOrder.user_id == user_id,
                ValuationOrder.payment_status == "pending",
            )
            .order_by(ValuationOrder.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_paid(
        self,
        session: AsyncSession,
        order_id: str,
        provider: str,
        provider_trans_id: str,
    ) -> ValuationOrder | None:
        """Transition payment_status to 'paid' idempotently."""
        order = await self.get_by_order_id(session, order_id)
        if not order:
            return None

        if order.payment_status != "paid":
            order.payment_status = "paid"
            order.payment_provider = provider
            order.provider_trans_id = provider_trans_id
            order.paid_at = datetime.now(UTC)
            order.valuation_status = "processing"
            await session.flush()

        return order

    async def set_valuation_result(
        self,
        session: AsyncSession,
        order_id: str,
        *,
        valuation_status: str,
        valuation_result: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> ValuationOrder | None:
        """Save AI valuation execution outcome."""
        order = await self.get_by_order_id(session, order_id)
        if not order:
            return None

        order.valuation_status = valuation_status
        if valuation_result is not None:
            order.valuation_result = valuation_result
        if error_message is not None:
            order.error_message = error_message
        await session.flush()
        return order

    async def list_orders(
        self,
        session: AsyncSession,
        *,
        payment_status: str | None = None,
        valuation_status: str | None = None,
        user_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ValuationOrder], int]:
        """List valuation orders with pagination and total count for admin."""
        stmt = select(ValuationOrder).options(selectinload(ValuationOrder.user))
        count_stmt = select(func.count(ValuationOrder.id))

        if payment_status:
            stmt = stmt.where(ValuationOrder.payment_status == payment_status)
            count_stmt = count_stmt.where(ValuationOrder.payment_status == payment_status)
        if valuation_status:
            stmt = stmt.where(ValuationOrder.valuation_status == valuation_status)
            count_stmt = count_stmt.where(ValuationOrder.valuation_status == valuation_status)
        if user_id:
            stmt = stmt.where(ValuationOrder.user_id == user_id)
            count_stmt = count_stmt.where(ValuationOrder.user_id == user_id)

        stmt = stmt.order_by(ValuationOrder.created_at.desc()).limit(limit).offset(offset)

        orders_res = await session.execute(stmt)
        count_res = await session.execute(count_stmt)

        return list(orders_res.scalars().all()), (count_res.scalar_one_or_none() or 0)
