"""Tests for database models, metadata, constraints, and relationships."""

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String

from app.models.role import DEFAULT_CUSTOMER_ROLE, SYSTEM_ROLES, Role, UserRole
from app.models.user import User


def test_user_model_metadata() -> None:
    """1. Verify User model table name, primary key, and column definitions."""
    assert User.__tablename__ == "users"

    table = User.__table__
    assert isinstance(table.c.id.type, BigInteger)
    assert table.c.id.primary_key is True

    # Check required fields
    assert isinstance(table.c.telegram_id.type, BigInteger)
    assert table.c.telegram_id.nullable is False

    assert isinstance(table.c.language.type, String)
    assert table.c.language.nullable is False

    assert isinstance(table.c.is_active.type, Boolean)
    assert table.c.is_verified.type is not None

    assert isinstance(table.c.created_at.type, DateTime)
    assert isinstance(table.c.updated_at.type, DateTime)


def test_unique_telegram_id_constraint() -> None:
    """2. Verify unique index and constraint on users.telegram_id."""
    table = User.__table__
    assert table.c.telegram_id.unique is True or any(
        idx.unique and "telegram_id" in [col.name for col in idx.columns] for idx in table.indexes
    )


def test_role_model_metadata() -> None:
    """3. Verify Role model table name and attributes."""
    assert Role.__tablename__ == "roles"
    table = Role.__table__
    assert isinstance(table.c.id.type, Integer)
    assert table.c.id.primary_key is True
    assert isinstance(table.c.name.type, String)
    assert table.c.name.nullable is False

    # Check default system roles
    assert DEFAULT_CUSTOMER_ROLE in SYSTEM_ROLES
    assert "superadmin" in SYSTEM_ROLES
    assert "head_broker" in SYSTEM_ROLES


def test_user_roles_relation() -> None:
    """4. Verify UserRole association model foreign keys and unique constraint."""
    assert UserRole.__tablename__ == "user_roles"
    table = UserRole.__table__

    assert table.c.user_id.nullable is False
    assert table.c.role_id.nullable is False

    # Verify foreign keys
    fk_targets = {fk.target_fullname for fk in table.foreign_keys}
    assert "users.id" in fk_targets
    assert "roles.id" in fk_targets

    # Verify unique constraint on user_id, role_id
    uq_names = [uq.name for uq in table.constraints if hasattr(uq, "name")]
    assert "uq_user_role" in uq_names


def test_role_uniqueness() -> None:
    """5. Verify that role names have unique constraint and index."""
    table = Role.__table__
    assert table.c.name.unique is True or any(
        idx.unique and "name" in [col.name for col in idx.columns] for idx in table.indexes
    )
