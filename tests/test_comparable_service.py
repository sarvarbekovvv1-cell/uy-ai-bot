"""Tests for ComparablePropertyService security, isolation, and tier fallback."""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property import Property
from app.models.user import User
from app.schemas.valuation import PropertyValuationInput
from app.services.valuation.comparable_service import ComparablePropertyService


async def create_db_property(
    session: AsyncSession,
    owner_id: int,
    *,
    status: str = "approved",
    listing_type: str = "sale",
    currency: str = "USD",
    district: str = "Chilonzor",
    region: str = "Toshkent shahri",
    rooms: int = 2,
    total_area: Decimal = Decimal("50"),
    price: Decimal = Decimal("80000"),
) -> Property:
    """Helper to persist Property in test database."""
    prop = Property(
        owner_user_id=owner_id,
        listing_type=listing_type,
        property_type="apartment",
        title=f"Test {rooms}-room in {district}",
        region=region,
        district=district,
        address="Test street 1",
        rooms=rooms,
        total_area=total_area,
        condition="renovated",
        price=price,
        currency=currency,
        status=status,
    )
    session.add(prop)
    await session.commit()
    await session.refresh(prop)
    return prop


@pytest.mark.asyncio
async def test_approved_only_enforcement(db_session: AsyncSession) -> None:
    """CRITICAL SECURITY RULE:

    Only Property.status == 'approved' can be used as comparables.
    Draft, submitted, rejected, archived, and sold properties must be strictly excluded.
    """
    owner = User(telegram_id=9871, username="test_owner", first_name="Owner", phone="+998901111111")
    db_session.add(owner)
    await db_session.commit()

    # Create various statuses
    await create_db_property(db_session, owner.id, status="approved")
    await create_db_property(db_session, owner.id, status="approved")
    await create_db_property(db_session, owner.id, status="draft")
    await create_db_property(db_session, owner.id, status="submitted")
    await create_db_property(db_session, owner.id, status="under_review")
    await create_db_property(db_session, owner.id, status="rejected")
    await create_db_property(db_session, owner.id, status="archived")
    await create_db_property(db_session, owner.id, status="sold")

    service = ComparablePropertyService()
    inp = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        total_area=Decimal("50"),
        rooms=2,
        currency="USD",
    )

    comps, _ = await service.find_comparables(db_session, inp)
    assert len(comps) == 2
    for comp_prop, _ in comps:
        assert comp_prop.status == "approved"


@pytest.mark.asyncio
async def test_listing_type_isolation(db_session: AsyncSession) -> None:
    """CRITICAL RULE: Sale and rent comparables must NEVER be mixed."""
    owner = User(
        telegram_id=9872,
        username="test_owner2",
        first_name="Owner2",
        phone="+998902222222",
    )
    db_session.add(owner)
    await db_session.commit()

    # 2 sale properties, 2 rent properties
    await create_db_property(db_session, owner.id, listing_type="sale", price=Decimal("80000"))
    await create_db_property(db_session, owner.id, listing_type="sale", price=Decimal("85000"))
    await create_db_property(db_session, owner.id, listing_type="rent", price=Decimal("500"))
    await create_db_property(db_session, owner.id, listing_type="rent", price=Decimal("600"))

    service = ComparablePropertyService()

    # Sale valuation must only return sale properties
    inp_sale = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        total_area=Decimal("50"),
        rooms=2,
        currency="USD",
    )
    comps_sale, _ = await service.find_comparables(db_session, inp_sale)
    assert len(comps_sale) == 2
    for p, _ in comps_sale:
        assert p.listing_type == "sale"

    # Rent valuation must only return rent properties
    inp_rent = PropertyValuationInput(
        listing_type="rent",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        total_area=Decimal("50"),
        rooms=2,
        currency="USD",
    )
    comps_rent, _ = await service.find_comparables(db_session, inp_rent)
    assert len(comps_rent) == 2
    for p, _ in comps_rent:
        assert p.listing_type == "rent"


@pytest.mark.asyncio
async def test_currency_isolation(db_session: AsyncSession) -> None:
    """CRITICAL RULE: USD and UZS comparables must NEVER be mixed mathematically."""
    owner = User(
        telegram_id=9873,
        username="test_owner3",
        first_name="Owner3",
        phone="+998903333333",
    )
    db_session.add(owner)
    await db_session.commit()

    await create_db_property(db_session, owner.id, currency="USD", price=Decimal("80000"))
    await create_db_property(db_session, owner.id, currency="USD", price=Decimal("85000"))
    await create_db_property(
        db_session, owner.id, currency="UZS", price=Decimal("1000000000")
    )

    service = ComparablePropertyService()
    inp_usd = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        total_area=Decimal("50"),
        rooms=2,
        currency="USD",
    )
    comps, _ = await service.find_comparables(db_session, inp_usd)
    assert len(comps) == 2
    for p, _ in comps:
        assert p.currency == "USD"


@pytest.mark.asyncio
async def test_self_property_exclusion(db_session: AsyncSession) -> None:
    """Verify that a subject property does NOT enter its own comparable set."""
    owner = User(
        telegram_id=9874,
        username="test_owner4",
        first_name="Owner4",
        phone="+998904444444",
    )
    db_session.add(owner)
    await db_session.commit()

    prop1 = await create_db_property(db_session, owner.id, price=Decimal("80000"))
    prop2 = await create_db_property(db_session, owner.id, price=Decimal("82000"))
    prop3 = await create_db_property(db_session, owner.id, price=Decimal("84000"))

    service = ComparablePropertyService()
    inp = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        total_area=Decimal("50"),
        rooms=2,
        currency="USD",
        property_id=prop1.id,  # Exclude prop1!
    )
    comps, _ = await service.find_comparables(db_session, inp)
    comp_ids = [p.id for p, _ in comps]
    assert prop1.id not in comp_ids
    assert prop2.id in comp_ids
    assert prop3.id in comp_ids


@pytest.mark.asyncio
async def test_tier_fallback_hierarchy(db_session: AsyncSession) -> None:
    """Verify fallback tiers: Tier 1 (exact district) -> Tier 3 (regional fallback)."""
    owner = User(
        telegram_id=9875,
        username="test_owner5",
        first_name="Owner5",
        phone="+998905555555",
    )
    db_session.add(owner)
    await db_session.commit()

    # Create properties in Yunusobod (not Bektemir)
    await create_db_property(
        db_session, owner.id, district="Yunusobod", region="Toshkent shahri", price=Decimal("80000")
    )
    await create_db_property(
        db_session, owner.id, district="Yunusobod", region="Toshkent shahri", price=Decimal("82000")
    )

    service = ComparablePropertyService()
    # Subject property is in Bektemir where 0 direct comparables exist
    inp = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Bektemir",
        total_area=Decimal("50"),
        rooms=2,
        currency="USD",
    )
    comps, tier_used = await service.find_comparables(db_session, inp)
    assert tier_used == 3  # Fell back to region tier!
    assert len(comps) == 2


@pytest.mark.asyncio
async def test_fallback_contamination_prevention(db_session: AsyncSession) -> None:
    """Verify that when Tier 1 has sufficient comparables, broader tiers do not contaminate."""
    owner = User(
        telegram_id=9876,
        username="test_owner6",
        first_name="Owner6",
        phone="+998906666666",
    )
    db_session.add(owner)
    await db_session.commit()

    # 2 direct Tier 1 comparables in Chilonzor
    p1 = await create_db_property(
        db_session, owner.id, district="Chilonzor", region="Toshkent shahri", price=Decimal("80000")
    )
    p2 = await create_db_property(
        db_session, owner.id, district="Chilonzor", region="Toshkent shahri", price=Decimal("82000")
    )

    # 5 distant properties in Yunusobod with wild prices
    for _i in range(5):
        await create_db_property(
            db_session,
            owner.id,
            district="Yunusobod",
            region="Toshkent shahri",
            price=Decimal("300000"),
        )

    service = ComparablePropertyService()
    inp = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        total_area=Decimal("50"),
        rooms=2,
        currency="USD",
    )

    comps, tier_used = await service.find_comparables(db_session, inp)
    assert tier_used == 1  # Tier 1 was sufficient!
    assert len(comps) == 2
    comp_ids = {p.id for p, _ in comps}
    assert comp_ids == {p1.id, p2.id}
    # Distant Yunusobod properties MUST NOT be included
    assert all(p.district == "Chilonzor" for p, _ in comps)


@pytest.mark.asyncio
async def test_invalid_corrupt_data_filtered_at_sql_level(db_session: AsyncSession) -> None:
    """Verify that zero price, zero area, and invalid data cannot enter candidate set."""
    owner = User(
        telegram_id=9877,
        username="test_owner7",
        first_name="Owner7",
        phone="+998907777777",
    )
    db_session.add(owner)
    await db_session.commit()

    # Valid properties
    await create_db_property(db_session, owner.id, price=Decimal("80000"), total_area=Decimal("50"))
    await create_db_property(db_session, owner.id, price=Decimal("82000"), total_area=Decimal("50"))

    # Invalid properties (bypassing normal app validation for testing DB anomalies)
    invalid_zero_price = Property(
        owner_user_id=owner.id,
        listing_type="sale",
        property_type="apartment",
        title="Zero price",
        region="Toshkent shahri",
        district="Chilonzor",
        address="Bad street 1",
        rooms=2,
        total_area=Decimal("50"),
        condition="renovated",
        price=Decimal("0"),
        currency="USD",
        status="approved",
    )
    invalid_zero_area = Property(
        owner_user_id=owner.id,
        listing_type="sale",
        property_type="apartment",
        title="Zero area",
        region="Toshkent shahri",
        district="Chilonzor",
        address="Bad street 2",
        rooms=2,
        total_area=Decimal("0"),
        condition="renovated",
        price=Decimal("80000"),
        currency="USD",
        status="approved",
    )
    db_session.add_all([invalid_zero_price, invalid_zero_area])
    await db_session.commit()

    service = ComparablePropertyService()
    inp = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        total_area=Decimal("50"),
        rooms=2,
        currency="USD",
    )

    comps, _ = await service.find_comparables(db_session, inp)
    assert len(comps) == 2
    for p, _ in comps:
        assert p.price > Decimal("0")
        assert p.total_area > Decimal("0")
