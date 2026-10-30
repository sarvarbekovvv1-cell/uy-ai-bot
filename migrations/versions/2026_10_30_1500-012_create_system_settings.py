"""create system_settings table and seed default broker phone

Revision ID: 012_create_system_settings
Revises: 011_valuation_3tiers_and_admin_verification
Create Date: 2026-10-30 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "012_create_system_settings"
down_revision: str | None = "011_valuation_3tiers_and_admin_verification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create system_settings table
    system_settings_table = op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # 2. Seed initial broker phone setting
    op.bulk_insert(
        system_settings_table,
        [
            {
                "key": "broker_phone",
                "value": "+998 71 200 00 00",
                "description": "Professional broker xizmati uchun aloqa telefoni",
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("system_settings")
