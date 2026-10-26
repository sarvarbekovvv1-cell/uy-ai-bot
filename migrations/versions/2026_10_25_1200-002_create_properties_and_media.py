"""create properties and property_media tables

Revision ID: 002_create_properties_and_media
Revises: 001_initial_users_and_roles
Create Date: 2026-10-25 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_create_properties_and_media"
down_revision: str | None = "001_initial_users_and_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create 'properties' table
    op.create_table(
        "properties",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("owner_user_id", sa.BigInteger(), nullable=False),
        sa.Column("listing_type", sa.String(length=20), nullable=False),
        sa.Column("property_type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("region", sa.String(length=100), nullable=False),
        sa.Column("district", sa.String(length=100), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("latitude", sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column("rooms", sa.Integer(), nullable=False),
        sa.Column("total_area", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("living_area", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("floor", sa.Integer(), nullable=True),
        sa.Column("total_floors", sa.Integer(), nullable=True),
        sa.Column("condition", sa.String(length=30), nullable=False),
        sa.Column("construction_type", sa.String(length=50), nullable=True),
        sa.Column("has_furniture", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "cadastre_status", sa.String(length=30), server_default="unknown", nullable=False
        ),
        sa.Column("price", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=10), server_default="USD", nullable=False),
        sa.Column("negotiable", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
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
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_properties_district"), "properties", ["district"], unique=False)
    op.create_index(
        op.f("ix_properties_listing_type"), "properties", ["listing_type"], unique=False
    )
    op.create_index(
        op.f("ix_properties_owner_user_id"), "properties", ["owner_user_id"], unique=False
    )
    op.create_index(op.f("ix_properties_price"), "properties", ["price"], unique=False)
    op.create_index(
        op.f("ix_properties_property_type"), "properties", ["property_type"], unique=False
    )
    op.create_index(op.f("ix_properties_region"), "properties", ["region"], unique=False)
    op.create_index(op.f("ix_properties_status"), "properties", ["status"], unique=False)

    # 2. Create 'property_media' table
    op.create_table(
        "property_media",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("property_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_file_id", sa.String(length=255), nullable=False),
        sa.Column("telegram_file_unique_id", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=20), server_default="photo", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "property_id", "telegram_file_unique_id", name="uq_property_media_unique_file"
        ),
    )
    op.create_index(
        op.f("ix_property_media_property_id"), "property_media", ["property_id"], unique=False
    )
    op.create_index(
        op.f("ix_property_media_telegram_file_unique_id"),
        "property_media",
        ["telegram_file_unique_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_property_media_telegram_file_unique_id"), table_name="property_media")
    op.drop_index(op.f("ix_property_media_property_id"), table_name="property_media")
    op.drop_table("property_media")

    op.drop_index(op.f("ix_properties_status"), table_name="properties")
    op.drop_index(op.f("ix_properties_region"), table_name="properties")
    op.drop_index(op.f("ix_properties_property_type"), table_name="properties")
    op.drop_index(op.f("ix_properties_price"), table_name="properties")
    op.drop_index(op.f("ix_properties_owner_user_id"), table_name="properties")
    op.drop_index(op.f("ix_properties_listing_type"), table_name="properties")
    op.drop_index(op.f("ix_properties_district"), table_name="properties")
    op.drop_table("properties")
