"""Tests for Property and PropertyMedia models, types, and constraints."""


from sqlalchemy import DateTime, Integer, Numeric, String

from app.models.property import (
    CADASTRE_STATUSES,
    LISTING_TYPES,
    PROPERTY_CONDITIONS,
    PROPERTY_STATUSES,
    PROPERTY_TYPES,
    SUPPORTED_CURRENCIES,
    Property,
)
from app.models.property_media import PropertyMedia


def test_property_model_metadata() -> None:
    """Verify Property model table name, column types, and constraints."""
    assert Property.__tablename__ == "properties"
    table = Property.__table__

    # Owner foreign key
    assert "owner_user_id" in table.c
    fk_targets = {fk.target_fullname for fk in table.c.owner_user_id.foreign_keys}
    assert "users.id" in fk_targets

    # Price must be Numeric/Decimal, never float
    assert isinstance(table.c.price.type, Numeric)
    assert not isinstance(table.c.price.type, float)

    # Area, rooms, coordinates
    assert isinstance(table.c.total_area.type, Numeric)
    assert isinstance(table.c.rooms.type, Integer)
    assert isinstance(table.c.latitude.type, Numeric)
    assert isinstance(table.c.longitude.type, Numeric)

    # Status, timestamps
    assert isinstance(table.c.status.type, String)
    assert isinstance(table.c.created_at.type, DateTime)
    assert isinstance(table.c.updated_at.type, DateTime)


def test_property_domain_constants() -> None:
    """Verify supported property domain values."""
    assert "sale" in LISTING_TYPES
    assert "rent" in LISTING_TYPES

    assert "apartment" in PROPERTY_TYPES
    assert "house" in PROPERTY_TYPES

    assert "new" in PROPERTY_CONDITIONS
    assert "renovated" in PROPERTY_CONDITIONS

    assert "available" in CADASTRE_STATUSES
    assert "unknown" in CADASTRE_STATUSES

    assert "draft" in PROPERTY_STATUSES
    assert "submitted" in PROPERTY_STATUSES
    assert "approved" in PROPERTY_STATUSES
    assert "rejected" in PROPERTY_STATUSES

    assert "USD" in SUPPORTED_CURRENCIES
    assert "UZS" in SUPPORTED_CURRENCIES


def test_property_media_model_metadata() -> None:
    """Verify PropertyMedia model table name, foreign key, and unique constraint."""
    assert PropertyMedia.__tablename__ == "property_media"
    table = PropertyMedia.__table__

    assert "property_id" in table.c
    fk_targets = {fk.target_fullname for fk in table.c.property_id.foreign_keys}
    assert "properties.id" in fk_targets

    assert isinstance(table.c.telegram_file_id.type, String)
    assert isinstance(table.c.telegram_file_unique_id.type, String)
    assert isinstance(table.c.sort_order.type, Integer)

    # Unique constraint on property_id and telegram_file_unique_id
    uq_names = [uq.name for uq in table.constraints if hasattr(uq, "name")]
    assert "uq_property_media_unique_file" in uq_names
