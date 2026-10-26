"""Kaizen / PDCA continuous improvement and intelligence models."""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
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
    from app.models.user import User

KAIZEN_CYCLE_STATUSES: tuple[str, ...] = (
    "draft",
    "planned",
    "active",
    "checking",
    "completed",
    "cancelled",
)

KAIZEN_OUTCOMES: tuple[str, ...] = (
    "successful",
    "partially_successful",
    "unsuccessful",
)

KAIZEN_RECOMMENDATION_STATUSES: tuple[str, ...] = (
    "new",
    "accepted",
    "dismissed",
    "converted_to_cycle",
)

KAIZEN_SEVERITIES: tuple[str, ...] = (
    "info",
    "warning",
    "critical",
)


class KaizenCycle(Base):
    """Database model for Kaizen PDCA (Plan-Do-Check-Act) cycles."""

    __tablename__ = "kaizen_cycles"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", index=True)

    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    approved_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    metric_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    baseline_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    target_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    observed_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    unit: Mapped[str] = mapped_column(String(30), default="percentage", nullable=False)

    date_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    plan_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    do_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    check_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    act_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    baseline_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    check_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    outcome: Mapped[str | None] = mapped_column(String(30), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checking_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    created_by: Mapped["User"] = relationship(
        "User", foreign_keys=[created_by_user_id], lazy="selectin"
    )
    approved_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[approved_by_user_id], lazy="selectin"
    )
    recommendations: Mapped[list["KaizenRecommendation"]] = relationship(
        "KaizenRecommendation", back_populates="linked_cycle", cascade="all, delete-orphan"
    )


class KaizenRecommendation(Base):
    """Database model for Kaizen recommendations generated deterministically or via AI advisor."""

    __tablename__ = "kaizen_recommendations"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )

    metric_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation_text: Mapped[str] = mapped_column(Text, nullable=False)

    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="info", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="new", nullable=False, index=True)

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    linked_cycle_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("kaizen_cycles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    reviewed_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[reviewed_by_user_id], lazy="selectin"
    )
    linked_cycle: Mapped["KaizenCycle | None"] = relationship(
        "KaizenCycle", back_populates="recommendations"
    )
