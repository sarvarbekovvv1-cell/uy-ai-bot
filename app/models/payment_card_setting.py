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
    card_number: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    card_holder: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    basic_price_uzs: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=50000
    )
    standard_price_uzs: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=65000
    )
    premium_price_uzs: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=90000
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    def is_configured(self) -> bool:
        """Return True only if active and card details are real (non-empty, non-placeholder)."""
        if not self.is_active:
            return False
        clean_num = (self.card_number or "").replace(" ", "").strip()
        clean_holder = (self.card_holder or "").strip()
        if not clean_num or not clean_holder:
            return False
        # Protect against dummy/placeholder card numbers
        if clean_num.startswith("0000") or clean_num == "9860000000000000":
            return False
        return True
