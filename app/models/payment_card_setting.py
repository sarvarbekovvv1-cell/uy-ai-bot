"""SQLAlchemy model for payment card and valuation pricing settings."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class PaymentCardSetting(Base):
    """Stores active payment card details and pricing tiers for P2P valuation monetization."""

    __tablename__ = "payment_card_settings"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    card_number: Mapped[str] = mapped_column(
        String(32), nullable=False, default="9860 0000 0000 0000"
    )
    card_holder: Mapped[str] = mapped_column(
        String(128), nullable=False, default="Sarvar Bekov"
    )
    standard_price_uzs: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=15000
    )
    premium_price_uzs: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=30000
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
