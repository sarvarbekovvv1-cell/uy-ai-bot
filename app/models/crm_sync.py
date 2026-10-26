"""Database models for CRM synchronization and transactional outbox."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base

CRM_EVENT_STATUSES = ("pending", "processing", "succeeded", "failed")
CRM_PROVIDERS = ("amocrm",)


class CRMSyncEvent(Base):
    """Transactional Outbox event for asynchronous CRM synchronization.

    Guarantees:
    - Atomically enqueued in the same database transaction as the business change.
    - Processed asynchronously by background worker or CLI runner.
    - Idempotent processing with retry tracking and backoff.
    - Never stores sensitive authorization secrets, tokens, or private customer keys.
    """

    __tablename__ = "crm_sync_events"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="amocrm",
        server_default="amocrm",
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=False,
        index=True,
    )

    payload_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    last_error_safe: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<CRMSyncEvent(id={self.id}, provider='{self.provider}', "
            f"event='{self.event_type}', entity='{self.entity_type}:{self.entity_id}', "
            f"status='{self.status}', attempts={self.attempt_count})>"
        )


class CRMEntityLink(Base):
    """Provider-agnostic mapping between local UyAI entities and external CRM objects.

    Examples:
    - local (user, 42) <-> external amocrm (contact, '1234567')
    - local (lead, 105) <-> external amocrm (lead, '9876543')

    Enforces strict 1-to-1 uniqueness per provider and entity type to prevent
    duplicate object creation in external CRM upon retries or cross-flow operations.
    """

    __tablename__ = "crm_entity_links"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "local_entity_type",
            "local_entity_id",
            "external_entity_type",
            name="uq_crm_entity_links_local_external",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="amocrm",
        server_default="amocrm",
        index=True,
    )
    local_entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    local_entity_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=False,
        index=True,
    )
    external_entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    external_entity_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
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

    def __repr__(self) -> str:
        return (
            f"<CRMEntityLink(id={self.id}, provider='{self.provider}', "
            f"local='{self.local_entity_type}:{self.local_entity_id}' <-> "
            f"external='{self.external_entity_type}:{self.external_entity_id}')>"
        )
