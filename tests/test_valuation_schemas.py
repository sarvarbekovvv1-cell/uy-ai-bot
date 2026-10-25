"""Tests for Property Valuation Pydantic schemas and validation rules."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.valuation import (
    PropertyValuationInput,
    PropertyValuationResult,
    SafeComparableProperty,
    ValuationExplanation,
)


def test_valid_valuation_input() -> None:
    """Verify valid valuation input passes validation."""
    data = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        total_area=Decimal("65.5"),
        rooms=2,
        condition="renovated",
        floor=4,
        total_floors=9,
        currency="USD",
    )
    assert data.listing_type == "sale"
    assert data.total_area == Decimal("65.5")
    assert data.rooms == 2
    assert data.floor == 4
    assert data.total_floors == 9


def test_valuation_input_rejects_negative_or_zero_area() -> None:
    """Verify total area must be strictly positive."""
    with pytest.raises(ValidationError):
        PropertyValuationInput(
            listing_type="sale",
            property_type="apartment",
            region="Toshkent",
            district="Chilonzor",
            total_area=Decimal("0"),
            rooms=2,
        )

    with pytest.raises(ValidationError):
        PropertyValuationInput(
            listing_type="sale",
            property_type="apartment",
            region="Toshkent",
            district="Chilonzor",
            total_area=Decimal("-15.0"),
            rooms=2,
        )


def test_valuation_input_rejects_floor_greater_than_total_floors() -> None:
    """Verify floor cannot exceed total building floors."""
    with pytest.raises(ValidationError, match="cannot exceed total floors"):
        PropertyValuationInput(
            listing_type="sale",
            property_type="apartment",
            region="Toshkent",
            district="Chilonzor",
            total_area=Decimal("50"),
            rooms=2,
            floor=10,
            total_floors=9,
        )


def test_valuation_input_rejects_invalid_rooms() -> None:
    """Verify rooms must be between 1 and 50."""
    with pytest.raises(ValidationError):
        PropertyValuationInput(
            listing_type="sale",
            property_type="apartment",
            region="Toshkent",
            district="Chilonzor",
            total_area=Decimal("50"),
            rooms=0,
        )

    with pytest.raises(ValidationError):
        PropertyValuationInput(
            listing_type="sale",
            property_type="apartment",
            region="Toshkent",
            district="Chilonzor",
            total_area=Decimal("50"),
            rooms=99,
        )


def test_valuation_explanation_schema_has_no_authoritative_prices() -> None:
    """CRITICAL SECURITY GUARANTEE:

    ValuationExplanation schema must not define authoritative price fields.
    Gemini cannot overwrite engine calculations.
    """
    fields = ValuationExplanation.model_fields.keys()
    assert "estimated_price" not in fields
    assert "estimated_min_price" not in fields
    assert "estimated_max_price" not in fields
    assert "price" not in fields


def test_safe_comparable_property_guarantees_no_pii() -> None:
    """Verify SafeComparableProperty does not contain phone numbers or owner IDs."""
    fields = SafeComparableProperty.model_fields.keys()
    assert "owner_user_id" not in fields
    assert "phone" not in fields
    assert "owner_phone" not in fields
    assert "telegram_id" not in fields
    assert "internal_notes" not in fields


def test_valuation_result_schema_types() -> None:
    """Verify PropertyValuationResult schema integrity."""
    res = PropertyValuationResult(
        estimated_price=Decimal("100000"),
        estimated_min_price=Decimal("95000"),
        estimated_max_price=Decimal("105000"),
        currency="USD",
        confidence="medium",
        comparable_count=5,
        median_price_per_m2=Decimal("1800.50"),
        comparison_tier=1,
        factors=["5 ta o‘xshash e'lon"],
        warnings=[],
        insufficient_data=False,
    )
    assert res.estimated_price == Decimal("100000")
    assert res.confidence == "medium"
    assert not res.insufficient_data
