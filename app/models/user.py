"""User database model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.favorite import Favorite
    from app.models.property import Property
    from app.models.role import Role
    from app.models.viewing_request import ViewingRequest


class User(Base):
    """Database model for registered users."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="uz", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary="user_roles",
        back_populates="users",
        lazy="selectin",
    )
    properties: Mapped[list["Property"]] = relationship(
        "Property",
        foreign_keys="Property.owner_user_id",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    favorites: Mapped[list["Favorite"]] = relationship(
        "Favorite",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    viewing_requests_as_customer: Mapped[list["ViewingRequest"]] = relationship(
        "ViewingRequest",
        foreign_keys="ViewingRequest.customer_user_id",
        back_populates="customer",
        lazy="selectin",
    )
    viewing_requests_as_broker: Mapped[list["ViewingRequest"]] = relationship(
        "ViewingRequest",
        foreign_keys="ViewingRequest.broker_user_id",
        back_populates="broker",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, phone='{self.phone}')>"
