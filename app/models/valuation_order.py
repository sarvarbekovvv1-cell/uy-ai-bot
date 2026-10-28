"""SQLAlchemy model for Property Valuation Orders and monetized payment tracking."""

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

VALUATION_PAYMENT_STATUSES = ("pending", "paid", "failed", "cancelled")
VALUATION_STATUSES = ("pending", "processing", "completed", "failed")
PAYMENT_PROVIDERS = ("click", "payme")


class ValuationOrder(Base):
    """Tracks a paid or pending property valuation request."""

    __tablename__ = "valuation_orders"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    order_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    user_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    # Serialized PropertyValuationInput dict
    property_input: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )

    # Pricing & Currency
    amount_uzs: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="UZS")

    # Payment lifecycle
    payment_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider_trans_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    payment_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )

    # Valuation execution lifecycle
    valuation_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )
    # Serialized PropertyValuationResult dict
    valuation_result: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    transactions = relationship(
        "PaymentTransaction",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="PaymentTransaction.created_at.desc()",
    )

    __table_args__ = (
        Index("ix_valuation_orders_user_status", "user_id", "payment_status"),
        Index("ix_valuation_orders_tg_created", "telegram_id", "created_at"),
    )
