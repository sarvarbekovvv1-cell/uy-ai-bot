"""Lead and CRM management models for UyAI Broker Cabinet."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
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
    from app.models.property import Property
    from app.models.user import User
    from app.models.viewing_request import ViewingRequest

LEAD_SOURCES = ("broker_contact", "viewing", "manual")
LEAD_STAGES = (
    "new",
    "contacted",
    "qualified",
    "viewing_scheduled",
    "negotiation",
    "won",
    "lost",
)
ACTIVE_LEAD_STAGES = (
    "new",
    "contacted",
    "qualified",
    "viewing_scheduled",
    "negotiation",
)
TERMINAL_LEAD_STAGES = ("won", "lost")
FOLLOWUP_TYPES = ("call", "message", "meeting", "other")
FOLLOWUP_STATUSES = ("pending", "completed", "cancelled")
LOST_REASONS = (
    "price",
    "not_interested",
    "competitor",
    "property_unavailable",
    "no_response",
    "other",
)


class Lead(Base):
    """Database model for customer leads managed by brokers."""

    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )

    customer_user_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    property_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("properties.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    broker_user_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_request_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("viewing_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    stage: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="new",
        server_default="new",
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

    assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    contacted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    qualified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    viewing_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    close_reason: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Relationships
    customer: Mapped["User"] = relationship(
        "User",
        foreign_keys=[customer_user_id],
        back_populates="leads_as_customer",
        lazy="selectin",
    )
    property: Mapped["Property"] = relationship(
        "Property",
        foreign_keys=[property_id],
        back_populates="leads",
        lazy="selectin",
    )
    broker: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[broker_user_id],
        back_populates="leads_as_broker",
        lazy="selectin",
    )
    source_request: Mapped["ViewingRequest | None"] = relationship(
        "ViewingRequest",
        foreign_keys=[source_request_id],
        back_populates="leads",
        lazy="selectin",
    )

    followups: Mapped[list["LeadFollowUp"]] = relationship(
        "LeadFollowUp",
        back_populates="lead",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="LeadFollowUp.due_at",
    )
    notes: Mapped[list["LeadNote"]] = relationship(
        "LeadNote",
        back_populates="lead",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="LeadNote.created_at.desc()",
    )
    events: Mapped[list["LeadEvent"]] = relationship(
        "LeadEvent",
        back_populates="lead",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="LeadEvent.created_at.desc()",
    )

    def __repr__(self) -> str:
        return (
            f"<Lead(id={self.id}, stage='{self.stage}', source='{self.source}', "
            f"prop_id={self.property_id}, customer_id={self.customer_user_id}, "
            f"broker_id={self.broker_user_id})>"
        )


class LeadFollowUp(Base):
    """Database model for broker follow-up tasks linked to leads."""

    __tablename__ = "lead_followups"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    lead_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    broker_user_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    task_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    due_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    lead: Mapped["Lead"] = relationship(
        "Lead",
        foreign_keys=[lead_id],
        back_populates="followups",
        lazy="selectin",
    )
    broker: Mapped["User"] = relationship(
        "User",
        foreign_keys=[broker_user_id],
        back_populates="lead_followups",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<LeadFollowUp(id={self.id}, lead_id={self.lead_id}, "
            f"type='{self.task_type}', status='{self.status}', due_at='{self.due_at}')>"
        )


class LeadNote(Base):
    """Database model for internal broker notes on leads."""

    __tablename__ = "lead_notes"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    lead_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_user_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    lead: Mapped["Lead"] = relationship(
        "Lead",
        foreign_keys=[lead_id],
        back_populates="notes",
        lazy="selectin",
    )
    author: Mapped["User"] = relationship(
        "User",
        foreign_keys=[author_user_id],
        back_populates="lead_notes",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<LeadNote(id={self.id}, lead_id={self.lead_id}, author_id={self.author_user_id})>"


class LeadEvent(Base):
    """Database model for audit history tracking on leads."""

    __tablename__ = "lead_events"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    lead_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    old_value: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    new_value: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    metadata_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    lead: Mapped["Lead"] = relationship(
        "Lead",
        foreign_keys=[lead_id],
        back_populates="events",
        lazy="selectin",
    )
    actor: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[actor_user_id],
        back_populates="lead_events",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<LeadEvent(id={self.id}, lead_id={self.lead_id}, type='{self.event_type}')>"
