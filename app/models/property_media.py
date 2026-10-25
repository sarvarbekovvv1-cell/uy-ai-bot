"""Property media database model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.property import Property


class PropertyMedia(Base):
    """Database model for photos and videos associated with a property."""

    __tablename__ = "property_media"
    __table_args__ = (
        UniqueConstraint(
            "property_id", "telegram_file_unique_id", name="uq_property_media_unique_file"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    telegram_file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    telegram_file_unique_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    media_type: Mapped[str] = mapped_column(String(20), default="photo", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    # Relationships
    property: Mapped["Property"] = relationship("Property", back_populates="media")

    def __repr__(self) -> str:
        return (
            f"<PropertyMedia(id={self.id}, property_id={self.property_id}, "
            f"type='{self.media_type}', sort={self.sort_order})>"
        )
