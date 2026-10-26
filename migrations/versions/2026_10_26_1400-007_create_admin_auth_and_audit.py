"""create admin auth, session, and audit tables

Revision ID: 007_create_admin_auth_and_audit
Revises: 006_create_crm_outbox_and_links
Create Date: 2026-10-26 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007_create_admin_auth_and_audit"
down_revision: str | None = "006_create_crm_outbox_and_links"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. staff_credentials table
    op.create_table(
        "staff_credentials",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_locked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("failed_login_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_staff_credentials_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff_credentials")),
    )
    op.create_index(
        op.f("ix_staff_credentials_user_id"),
        "staff_credentials",
        ["user_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_staff_credentials_username"),
        "staff_credentials",
        ["username"],
        unique=True,
    )

    # 2. admin_sessions table
    op.create_table(
        "admin_sessions",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("session_token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "user_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column("csrf_token", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("is_revoked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_admin_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_sessions")),
    )
    op.create_index(
        op.f("ix_admin_sessions_session_token_hash"),
        "admin_sessions",
        ["session_token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_admin_sessions_user_id"),
        "admin_sessions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_sessions_expires_at"),
        "admin_sessions",
        ["expires_at"],
        unique=False,
    )

    # 3. admin_audit_events table
    op.create_table(
        "admin_audit_events",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column(
            "entity_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=True,
        ),
        sa.Column("safe_metadata_json", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_admin_audit_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_audit_events")),
    )
    op.create_index(
        op.f("ix_admin_audit_events_actor_user_id"),
        "admin_audit_events",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_audit_events_action"),
        "admin_audit_events",
        ["action"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_audit_events_entity_type"),
        "admin_audit_events",
        ["entity_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_audit_events_entity_id"),
        "admin_audit_events",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_audit_events_created_at"),
        "admin_audit_events",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("admin_audit_events")
    op.drop_table("admin_sessions")
    op.drop_table("staff_credentials")
