"""create leads and crm management tables

Revision ID: 005_create_leads_and_crm
Revises: 004_create_viewing_requests
Create Date: 2026-10-25 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005_create_leads_and_crm"
down_revision: str | None = "004_create_viewing_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. leads table
    op.create_table(
        "leads",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "customer_user_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "property_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "broker_user_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=True,
        ),
        sa.Column(
            "source_request_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=True,
        ),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("stage", sa.String(length=50), server_default="new", nullable=False),
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
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("qualified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("viewing_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_reason", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(
            ["customer_user_id"],
            ["users.id"],
            name=op.f("fk_leads_customer_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name=op.f("fk_leads_property_id_properties"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["broker_user_id"],
            ["users.id"],
            name=op.f("fk_leads_broker_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_request_id"],
            ["viewing_requests.id"],
            name=op.f("fk_leads_source_request_id_viewing_requests"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_leads")),
    )
    op.create_index(
        op.f("ix_leads_customer_user_id"),
        "leads",
        ["customer_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_leads_property_id"),
        "leads",
        ["property_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_leads_broker_user_id"),
        "leads",
        ["broker_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_leads_source_request_id"),
        "leads",
        ["source_request_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_leads_source"),
        "leads",
        ["source"],
        unique=False,
    )
    op.create_index(
        op.f("ix_leads_stage"),
        "leads",
        ["stage"],
        unique=False,
    )

    # 2. lead_followups table
    op.create_table(
        "lead_followups",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "lead_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "broker_user_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column("task_type", sa.String(length=50), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="pending", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["leads.id"],
            name=op.f("fk_lead_followups_lead_id_leads"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["broker_user_id"],
            ["users.id"],
            name=op.f("fk_lead_followups_broker_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lead_followups")),
    )
    op.create_index(
        op.f("ix_lead_followups_lead_id"),
        "lead_followups",
        ["lead_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lead_followups_broker_user_id"),
        "lead_followups",
        ["broker_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lead_followups_task_type"),
        "lead_followups",
        ["task_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lead_followups_due_at"),
        "lead_followups",
        ["due_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lead_followups_status"),
        "lead_followups",
        ["status"],
        unique=False,
    )

    # 3. lead_notes table
    op.create_table(
        "lead_notes",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "lead_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "author_user_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["leads.id"],
            name=op.f("fk_lead_notes_lead_id_leads"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_user_id"],
            ["users.id"],
            name=op.f("fk_lead_notes_author_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lead_notes")),
    )
    op.create_index(
        op.f("ix_lead_notes_lead_id"),
        "lead_notes",
        ["lead_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lead_notes_author_user_id"),
        "lead_notes",
        ["author_user_id"],
        unique=False,
    )

    # 4. lead_events table
    op.create_table(
        "lead_events",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "lead_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("old_value", sa.String(length=255), nullable=True),
        sa.Column("new_value", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["leads.id"],
            name=op.f("fk_lead_events_lead_id_leads"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_lead_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lead_events")),
    )
    op.create_index(
        op.f("ix_lead_events_lead_id"),
        "lead_events",
        ["lead_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lead_events_actor_user_id"),
        "lead_events",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lead_events_event_type"),
        "lead_events",
        ["event_type"],
        unique=False,
    )


def downgrade() -> None:
    # Drop lead_events
    op.drop_index(op.f("ix_lead_events_event_type"), table_name="lead_events")
    op.drop_index(op.f("ix_lead_events_actor_user_id"), table_name="lead_events")
    op.drop_index(op.f("ix_lead_events_lead_id"), table_name="lead_events")
    op.drop_table("lead_events")

    # Drop lead_notes
    op.drop_index(op.f("ix_lead_notes_author_user_id"), table_name="lead_notes")
    op.drop_index(op.f("ix_lead_notes_lead_id"), table_name="lead_notes")
    op.drop_table("lead_notes")

    # Drop lead_followups
    op.drop_index(op.f("ix_lead_followups_status"), table_name="lead_followups")
    op.drop_index(op.f("ix_lead_followups_due_at"), table_name="lead_followups")
    op.drop_index(op.f("ix_lead_followups_task_type"), table_name="lead_followups")
    op.drop_index(op.f("ix_lead_followups_broker_user_id"), table_name="lead_followups")
    op.drop_index(op.f("ix_lead_followups_lead_id"), table_name="lead_followups")
    op.drop_table("lead_followups")

    # Drop leads
    op.drop_index(op.f("ix_leads_stage"), table_name="leads")
    op.drop_index(op.f("ix_leads_source"), table_name="leads")
    op.drop_index(op.f("ix_leads_source_request_id"), table_name="leads")
    op.drop_index(op.f("ix_leads_broker_user_id"), table_name="leads")
    op.drop_index(op.f("ix_leads_property_id"), table_name="leads")
    op.drop_index(op.f("ix_leads_customer_user_id"), table_name="leads")
    op.drop_table("leads")
