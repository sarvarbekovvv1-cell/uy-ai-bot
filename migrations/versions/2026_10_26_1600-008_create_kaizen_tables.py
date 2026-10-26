"""create kaizen cycles and recommendations tables

Revision ID: 008_create_kaizen_tables
Revises: 007_create_admin_auth_and_audit
Create Date: 2026-10-26 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008_create_kaizen_tables"
down_revision: str | None = "007_create_admin_auth_and_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. kaizen_cycles table
    op.create_table(
        "kaizen_cycles",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "approved_by_user_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=True,
        ),
        sa.Column("metric_key", sa.String(length=100), nullable=False),
        sa.Column("baseline_value", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("target_value", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("observed_value", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("unit", sa.String(length=30), server_default="percentage", nullable=False),
        sa.Column("date_from", sa.Date(), nullable=True),
        sa.Column("date_to", sa.Date(), nullable=True),
        sa.Column("plan_text", sa.Text(), nullable=True),
        sa.Column("do_text", sa.Text(), nullable=True),
        sa.Column("check_text", sa.Text(), nullable=True),
        sa.Column("act_text", sa.Text(), nullable=True),
        sa.Column("baseline_snapshot_json", sa.Text(), nullable=True),
        sa.Column("check_snapshot_json", sa.Text(), nullable=True),
        sa.Column("outcome", sa.String(length=30), nullable=True),
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
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checking_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_kaizen_cycles_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"],
            ["users.id"],
            name=op.f("fk_kaizen_cycles_approved_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_kaizen_cycles")),
    )
    op.create_index(op.f("ix_kaizen_cycles_status"), "kaizen_cycles", ["status"], unique=False)
    op.create_index(
        op.f("ix_kaizen_cycles_metric_key"), "kaizen_cycles", ["metric_key"], unique=False
    )
    op.create_index(
        op.f("ix_kaizen_cycles_created_by_user_id"),
        "kaizen_cycles",
        ["created_by_user_id"],
        unique=False,
    )

    # 2. kaizen_recommendations table
    op.create_table(
        "kaizen_recommendations",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("metric_key", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("recommendation_text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("severity", sa.String(length=20), server_default="info", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="new", nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "reviewed_by_user_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "linked_cycle_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"],
            ["users.id"],
            name=op.f("fk_kaizen_recommendations_reviewed_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["linked_cycle_id"],
            ["kaizen_cycles.id"],
            name=op.f("fk_kaizen_recommendations_linked_cycle_id_kaizen_cycles"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_kaizen_recommendations")),
    )
    op.create_index(
        op.f("ix_kaizen_recommendations_status"),
        "kaizen_recommendations",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_kaizen_recommendations_metric_key"),
        "kaizen_recommendations",
        ["metric_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_kaizen_recommendations_category"),
        "kaizen_recommendations",
        ["category"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_kaizen_recommendations_category"), table_name="kaizen_recommendations")
    op.drop_index(op.f("ix_kaizen_recommendations_metric_key"), table_name="kaizen_recommendations")
    op.drop_index(op.f("ix_kaizen_recommendations_status"), table_name="kaizen_recommendations")
    op.drop_table("kaizen_recommendations")

    op.drop_index(op.f("ix_kaizen_cycles_created_by_user_id"), table_name="kaizen_cycles")
    op.drop_index(op.f("ix_kaizen_cycles_metric_key"), table_name="kaizen_cycles")
    op.drop_index(op.f("ix_kaizen_cycles_status"), table_name="kaizen_cycles")
    op.drop_table("kaizen_cycles")
