"""Property database model and domain constants."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.favorite import Favorite
    from app.models.property_media import PropertyMedia
    from app.models.user import User

# Controlled Domain Constants
LISTING_TYPES: tuple[str, ...] = ("sale", "rent")

PROPERTY_TYPES: tuple[str, ...] = ("apartment", "house", "commercial", "land")

PROPERTY_CONDITIONS: tuple[str, ...] = (
    "new",
    "renovated",
    "needs_renovation",
    "shell",
)

CADASTRE_STATUSES: tuple[str, ...] = (
    "available",
    "not_available",
    "in_process",
    "unknown",
)

PROPERTY_STATUSES: tuple[str, ...] = (
    "draft",
    "submitted",
    "under_review",
    "approved",
    "rejected",
    "archived",
    "sold",
    "rented",
)

SUPPORTED_CURRENCIES: tuple[str, ...] = ("USD", "UZS")


class Property(Base):
    """Database model for real estate properties."""

    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    owner_user_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    listing_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    property_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    region: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    district: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    address: Mapped[str] = mapped_column(String(255), nullable=False)

    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)

    rooms: Mapped[int] = mapped_column(Integer, nullable=False)

    total_area: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    living_area: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_floors: Mapped[int | None] = mapped_column(Integer, nullable=True)

    condition: Mapped[str] = mapped_column(String(30), nullable=False)
    construction_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    has_furniture: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cadastre_status: Mapped[str] = mapped_column(String(30), default="unknown", nullable=False)

    price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    negotiable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    approved_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    owner: Mapped["User"] = relationship(
        "User",
        foreign_keys=[owner_user_id],
        back_populates="properties",
        lazy="selectin",
    )
    media: Mapped[list["PropertyMedia"]] = relationship(
        "PropertyMedia",
        back_populates="property",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PropertyMedia.sort_order",
    )
    favorites: Mapped[list["Favorite"]] = relationship(
        "Favorite",
        back_populates="property",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Property(id={self.id}, owner_user_id={self.owner_user_id}, "
            f"type='{self.property_type}', listing='{self.listing_type}', status='{self.status}')>"
        )
