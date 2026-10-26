"""create crm outbox and links tables

Revision ID: 006_create_crm_outbox_and_links
Revises: 005_create_leads_and_crm
Create Date: 2026-10-26 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006_create_crm_outbox_and_links"
down_revision: str | None = "005_create_leads_and_crm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. crm_sync_events table (Transactional Outbox)
    op.create_table(
        "crm_sync_events",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=50), server_default="amocrm", nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column(
            "entity_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_error_safe", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_sync_events")),
    )
    op.create_index(
        op.f("ix_crm_sync_events_provider"),
        "crm_sync_events",
        ["provider"],
        unique=False,
    )
    op.create_index(
        op.f("ix_crm_sync_events_event_type"),
        "crm_sync_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_crm_sync_events_entity_type"),
        "crm_sync_events",
        ["entity_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_crm_sync_events_entity_id"),
        "crm_sync_events",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_crm_sync_events_status"),
        "crm_sync_events",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_crm_sync_events_next_attempt_at"),
        "crm_sync_events",
        ["next_attempt_at"],
        unique=False,
    )

    # 2. crm_entity_links table (Mapping)
    op.create_table(
        "crm_entity_links",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=50), server_default="amocrm", nullable=False),
        sa.Column("local_entity_type", sa.String(length=50), nullable=False),
        sa.Column(
            "local_entity_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column("external_entity_type", sa.String(length=50), nullable=False),
        sa.Column("external_entity_id", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crm_entity_links")),
        sa.UniqueConstraint(
            "provider",
            "local_entity_type",
            "local_entity_id",
            "external_entity_type",
            name=op.f("uq_crm_entity_links_local_external"),
        ),
    )
    op.create_index(
        op.f("ix_crm_entity_links_provider"),
        "crm_entity_links",
        ["provider"],
        unique=False,
    )
    op.create_index(
        op.f("ix_crm_entity_links_local_entity_type"),
        "crm_entity_links",
        ["local_entity_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_crm_entity_links_local_entity_id"),
        "crm_entity_links",
        ["local_entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_crm_entity_links_external_entity_type"),
        "crm_entity_links",
        ["external_entity_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_crm_entity_links_external_entity_id"),
        "crm_entity_links",
        ["external_entity_id"],
        unique=False,
    )


def downgrade() -> None:
    # Drop crm_entity_links
    op.drop_index(op.f("ix_crm_entity_links_external_entity_id"), table_name="crm_entity_links")
    op.drop_index(op.f("ix_crm_entity_links_external_entity_type"), table_name="crm_entity_links")
    op.drop_index(op.f("ix_crm_entity_links_local_entity_id"), table_name="crm_entity_links")
    op.drop_index(op.f("ix_crm_entity_links_local_entity_type"), table_name="crm_entity_links")
    op.drop_index(op.f("ix_crm_entity_links_provider"), table_name="crm_entity_links")
    op.drop_table("crm_entity_links")

    # Drop crm_sync_events
    op.drop_index(op.f("ix_crm_sync_events_next_attempt_at"), table_name="crm_sync_events")
    op.drop_index(op.f("ix_crm_sync_events_status"), table_name="crm_sync_events")
    op.drop_index(op.f("ix_crm_sync_events_entity_id"), table_name="crm_sync_events")
    op.drop_index(op.f("ix_crm_sync_events_entity_type"), table_name="crm_sync_events")
    op.drop_index(op.f("ix_crm_sync_events_event_type"), table_name="crm_sync_events")
    op.drop_index(op.f("ix_crm_sync_events_provider"), table_name="crm_sync_events")
    op.drop_table("crm_sync_events")
