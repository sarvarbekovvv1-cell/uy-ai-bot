"""Add 3 pricing tiers and admin verification columns to valuation orders

Revision ID: 011_valuation_3tiers_and_admin_verification
Revises: 010_create_payment_card_settings
Create Date: 2026-10-29 14:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "011_valuation_3tiers_and_admin_verification"
down_revision: str | None = "010_create_payment_card_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add basic_price_uzs to payment_card_settings
    with op.batch_alter_table("payment_card_settings") as batch_op:
        batch_op.add_column(
            sa.Column(
                "basic_price_uzs",
                sa.Numeric(precision=14, scale=2),
                server_default="50000",
                nullable=False,
            )
        )

    # 2. Add admin review columns to valuation_orders
    with op.batch_alter_table("valuation_orders") as batch_op:
        batch_op.add_column(
            sa.Column(
                "admin_notes",
                sa.Text(),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "approved_by_user_id",
                sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "reviewed_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("valuation_orders") as batch_op:
        batch_op.drop_column("reviewed_at")
        batch_op.drop_column("approved_by_user_id")
        batch_op.drop_column("admin_notes")

    with op.batch_alter_table("payment_card_settings") as batch_op:
        batch_op.drop_column("basic_price_uzs")
