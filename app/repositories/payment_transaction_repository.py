"""Repository for PaymentTransaction database access."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment_transaction import PaymentTransaction


class PaymentTransactionRepository:
    """Handles CRUD operations for payment provider transaction records."""

    async def get_by_provider_trans_id(
        self,
        session: AsyncSession,
        provider: str,
        provider_trans_id: str,
    ) -> PaymentTransaction | None:
        """Find transaction by provider's external transaction ID."""
        stmt = select(PaymentTransaction).where(
            PaymentTransaction.provider == provider,
            PaymentTransaction.provider_trans_id == str(provider_trans_id),
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_transaction(
        self,
        session: AsyncSession,
        *,
        order_id: int,
        provider: str,
        provider_trans_id: str,
        amount: Decimal,
        currency: str = "UZS",
        state: str = "created",
        raw_payload: dict[str, Any] | None = None,
    ) -> PaymentTransaction:
        """Create and persist a new payment transaction log."""
        tx = PaymentTransaction(
            order_id=order_id,
            provider=provider,
            provider_trans_id=str(provider_trans_id),
            amount=amount,
            currency=currency,
            state=state,
            raw_payload=raw_payload,
        )
        session.add(tx)
        await session.flush()
        return tx

    async def update_state(
        self,
        session: AsyncSession,
        tx: PaymentTransaction,
        state: str,
        *,
        perform_time: datetime | None = None,
        cancel_time: datetime | None = None,
        cancel_reason: int | None = None,
        error_code: int | None = None,
        error_note: str | None = None,
    ) -> PaymentTransaction:
        """Update transaction lifecycle state."""
        tx.state = state
        if perform_time is not None:
            tx.perform_time = perform_time
        if cancel_time is not None:
            tx.cancel_time = cancel_time
        if cancel_reason is not None:
            tx.cancel_reason = cancel_reason
        if error_code is not None:
            tx.error_code = error_code
        if error_note is not None:
            tx.error_note = error_note
        await session.flush()
        return tx
