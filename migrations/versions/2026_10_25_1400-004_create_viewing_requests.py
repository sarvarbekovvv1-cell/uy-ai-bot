"""create viewing_requests table

Revision ID: 004_create_viewing_requests
Revises: 003_create_favorites
Create Date: 2026-10-25 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004_create_viewing_requests"
down_revision: str | None = "003_create_favorites"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "viewing_requests",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "property_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "customer_user_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "broker_user_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=True,
        ),
        sa.Column("request_type", sa.String(length=50), nullable=False),
        sa.Column("preferred_date", sa.Date(), nullable=True),
        sa.Column("preferred_time", sa.String(length=20), nullable=True),
        sa.Column("customer_comment", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="pending", nullable=False),
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
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("outcome", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name=op.f("fk_viewing_requests_property_id_properties"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["customer_user_id"],
            ["users.id"],
            name=op.f("fk_viewing_requests_customer_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["broker_user_id"],
            ["users.id"],
            name=op.f("fk_viewing_requests_broker_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_viewing_requests")),
    )
    op.create_index(
        op.f("ix_viewing_requests_broker_user_id"),
        "viewing_requests",
        ["broker_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_viewing_requests_customer_user_id"),
        "viewing_requests",
        ["customer_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_viewing_requests_preferred_date"),
        "viewing_requests",
        ["preferred_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_viewing_requests_property_id"),
        "viewing_requests",
        ["property_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_viewing_requests_request_type"),
        "viewing_requests",
        ["request_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_viewing_requests_status"),
        "viewing_requests",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_viewing_requests_status"), table_name="viewing_requests")
    op.drop_index(op.f("ix_viewing_requests_request_type"), table_name="viewing_requests")
    op.drop_index(op.f("ix_viewing_requests_property_id"), table_name="viewing_requests")
    op.drop_index(op.f("ix_viewing_requests_preferred_date"), table_name="viewing_requests")
    op.drop_index(op.f("ix_viewing_requests_customer_user_id"), table_name="viewing_requests")
    op.drop_index(op.f("ix_viewing_requests_broker_user_id"), table_name="viewing_requests")
    op.drop_table("viewing_requests")
