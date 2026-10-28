"""SQLAlchemy model for Payment Provider Transactions (Click, Payme)."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database.base import Base


class PaymentTransaction(Base):
    """Detailed log and state machine record for Click and Payme transactions."""

    __tablename__ = "payment_transactions"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )

    order_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("valuation_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)  # "click" | "payme"
    provider_trans_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    # State:
    # For Click: "prepare" (action 0), "complete" (action 1), "cancelled"
    # For Payme: "created" (state 1), "performed" (state 2), "cancelled" (state -1 or -2)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="created")

    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="UZS")

    # Raw payload and metadata
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    error_code: Mapped[int | None] = mapped_column(nullable=True)
    error_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    perform_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[int | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    order = relationship("ValuationOrder", back_populates="transactions")

    __table_args__ = (
        Index("ix_payment_trans_provider_id", "provider", "provider_trans_id", unique=True),
    )
