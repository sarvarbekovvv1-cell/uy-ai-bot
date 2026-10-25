"""Viewing request database model for UyAI appointments and broker contact."""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.property import Property
    from app.models.user import User

REQUEST_TYPES = ("viewing", "broker_contact")
REQUEST_STATUSES = (
    "pending",
    "assigned",
    "accepted",
    "rejected",
    "cancelled",
    "completed",
)
VIEWING_OUTCOMES = ("interested", "not_interested", "reschedule_requested", "no_show")


class ViewingRequest(Base):
    """Database model for customer property viewing and broker contact requests."""

    __tablename__ = "viewing_requests"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )

    property_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("properties.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    customer_user_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    broker_user_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    request_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    preferred_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )
    preferred_time: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    customer_comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    cancellation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    outcome: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # Relationships
    property: Mapped["Property"] = relationship(
        "Property",
        back_populates="viewing_requests",
        lazy="selectin",
    )
    customer: Mapped["User"] = relationship(
        "User",
        foreign_keys=[customer_user_id],
        back_populates="viewing_requests_as_customer",
        lazy="selectin",
    )
    broker: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[broker_user_id],
        back_populates="viewing_requests_as_broker",
        lazy="selectin",
    )
    leads: Mapped[list["Lead"]] = relationship(
        "Lead",
        foreign_keys="Lead.source_request_id",
        back_populates="source_request",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<ViewingRequest(id={self.id}, type='{self.request_type}', "
            f"prop_id={self.property_id}, customer_id={self.customer_user_id}, "
            f"status='{self.status}')>"
        )
