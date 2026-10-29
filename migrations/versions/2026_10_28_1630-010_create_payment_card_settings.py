"""create payment card settings table and extend valuation orders

Revision ID: 010_create_payment_card_settings
Revises: 009_create_valuation_orders_and_payments
Create Date: 2026-10-28 16:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "010_create_payment_card_settings"
down_revision: str | None = "009_create_valuation_orders_and_payments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. payment_card_settings table
    op.create_table(
        "payment_card_settings",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "card_number",
            sa.String(length=32),
            server_default="9860 0000 0000 0000",
            nullable=False,
        ),
        sa.Column(
            "card_holder",
            sa.String(length=128),
            server_default="Sarvar Bekov",
            nullable=False,
        ),
        sa.Column(
            "standard_price_uzs",
            sa.Numeric(precision=14, scale=2),
            server_default="15000",
            nullable=False,
        ),
        sa.Column(
            "premium_price_uzs",
            sa.Numeric(precision=14, scale=2),
            server_default="30000",
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. Add columns to valuation_orders
    with op.batch_alter_table("valuation_orders") as batch_op:
        batch_op.add_column(
            sa.Column(
                "package_type",
                sa.String(length=32),
                server_default="standard",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "receipt_file_id",
                sa.String(length=255),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "receipt_analysis",
                sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("valuation_orders") as batch_op:
        batch_op.drop_column("receipt_analysis")
        batch_op.drop_column("receipt_file_id")
        batch_op.drop_column("package_type")

    op.drop_table("payment_card_settings")
