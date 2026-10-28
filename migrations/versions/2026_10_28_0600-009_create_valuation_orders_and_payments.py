"""create valuation orders and payment transactions tables

Revision ID: 009_create_valuation_orders_and_payments
Revises: 008_create_kaizen_tables
Create Date: 2026-10-28 06:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "009_create_valuation_orders_and_payments"
down_revision: str | None = "008_create_kaizen_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. valuation_orders table
    op.create_table(
        "valuation_orders",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column(
            "user_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column(
            "telegram_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "property_input",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("amount_uzs", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="UZS", nullable=False),
        sa.Column("payment_provider", sa.String(length=32), nullable=True),
        sa.Column("provider_trans_id", sa.String(length=128), nullable=True),
        sa.Column(
            "payment_status", sa.String(length=32), server_default="pending", nullable=False
        ),
        sa.Column(
            "valuation_status", sa.String(length=32), server_default="pending", nullable=False
        ),
        sa.Column(
            "valuation_result",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_valuation_orders_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_valuation_orders")),
    )
    op.create_index(
        op.f("ix_valuation_orders_order_id"),
        "valuation_orders",
        ["order_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_valuation_orders_user_id"),
        "valuation_orders",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_valuation_orders_telegram_id"),
        "valuation_orders",
        ["telegram_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_valuation_orders_payment_status"),
        "valuation_orders",
        ["payment_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_valuation_orders_valuation_status"),
        "valuation_orders",
        ["valuation_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_valuation_orders_provider_trans_id"),
        "valuation_orders",
        ["provider_trans_id"],
        unique=False,
    )
    op.create_index(
        "ix_valuation_orders_user_status",
        "valuation_orders",
        ["user_id", "payment_status"],
        unique=False,
    )
    op.create_index(
        "ix_valuation_orders_tg_created",
        "valuation_orders",
        ["telegram_id", "created_at"],
        unique=False,
    )

    # 2. payment_transactions table
    op.create_table(
        "payment_transactions",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "order_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_trans_id", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=32), server_default="created", nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="UZS", nullable=False),
        sa.Column(
            "raw_payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column("error_code", sa.Integer(), nullable=True),
        sa.Column("error_note", sa.Text(), nullable=True),
        sa.Column("perform_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["valuation_orders.id"],
            name=op.f("fk_payment_transactions_order_id_valuation_orders"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_transactions")),
    )
    op.create_index(
        op.f("ix_payment_transactions_order_id"),
        "payment_transactions",
        ["order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payment_transactions_provider_trans_id"),
        "payment_transactions",
        ["provider_trans_id"],
        unique=False,
    )
    op.create_index(
        "ix_payment_trans_provider_id",
        "payment_transactions",
        ["provider", "provider_trans_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("payment_transactions")
    op.drop_table("valuation_orders")
