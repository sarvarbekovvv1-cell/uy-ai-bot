"""Tests for Phase 4 property search filters, repository, and search service."""

from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PropertyNotFoundError
from app.models.property import Property
from app.models.user import User
from app.repositories.property_repository import PropertyRepository
from app.schemas.property_search import PropertySearchFilters
from app.services.property_search_service import PropertySearchService


def test_search_filters_validation() -> None:
    """Verify validation and normalization in PropertySearchFilters schema."""
    # Valid filter
    filters = PropertySearchFilters(
        listing_type="sale",
        property_type="apartment",
        region="  Toshkent  ",
        district="  Chilonzor  ",
        rooms=3,
        min_price=Decimal("50000"),
        max_price=Decimal("100000"),
        currency="USD",
        min_area=Decimal("60"),
    )
    assert filters.region == "Toshkent"
    assert filters.district == "Chilonzor"
    assert filters.property_type == "apartment"
    assert filters.min_price == Decimal("50000")

    # Property type "all" normalized to None
    filters_all = PropertySearchFilters(listing_type="rent", property_type="all")
    assert filters_all.property_type is None

    # Invalid price range: min_price > max_price
    with pytest.raises(ValidationError, match="min_price cannot be greater than max_price"):
        PropertySearchFilters(
            listing_type="sale",
            min_price=Decimal("100000"),
            max_price=Decimal("50000"),
            currency="USD",
        )

    # Missing currency when price filter is specified
    with pytest.raises(ValidationError, match="currency is required"):
        PropertySearchFilters(
            listing_type="sale",
            min_price=Decimal("50000"),
        )


@pytest.mark.asyncio
async def test_approved_only_search_and_status_exclusion(db_session: AsyncSession) -> None:
    """Verify public search STRICTLY returns only approved properties.

    Must exclude: draft, submitted, under_review, rejected, archived, sold, rented.
    """
    user = User(telegram_id=99001, first_name="Owner", language="uz")
    db_session.add(user)
    await db_session.flush()

    statuses = [
        "draft",
        "submitted",
        "under_review",
        "approved",
        "rejected",
        "archived",
        "sold",
        "rented",
    ]
    for st in statuses:
        prop = Property(
            owner_user_id=user.id,
            listing_type="sale",
            property_type="apartment",
            region="Toshkent",
            district="Yunusobod",
            address="1-mavze",
            rooms=2,
            total_area=Decimal("60"),
            condition="renovated",
            cadastre_status="available",
            price=Decimal("65000"),
            currency="USD",
            has_furniture=True,
            negotiable=False,
            status=st,
        )
        db_session.add(prop)
    await db_session.flush()

    repo = PropertyRepository()
    filters = PropertySearchFilters(listing_type="sale")

    items, total = await repo.search_approved(db_session, filters)

    assert total == 1
    assert len(items) == 1
    assert items[0].status == "approved"


@pytest.mark.asyncio
async def test_search_filters_matching_and_currency(db_session: AsyncSession) -> None:
    """Verify search filter combinations: listing type, rooms, price, area, currency."""
    user = User(telegram_id=99002, first_name="Owner", language="uz")
    db_session.add(user)
    await db_session.flush()

    # Property 1: Sale, Apartment, Toshkent / Chilonzor, 2 rooms, 50k USD, 55 m²
    p1 = Property(
        owner_user_id=user.id,
        listing_type="sale",
        property_type="apartment",
        region="Toshkent",
        district="Chilonzor",
        address="3-mavze",
        rooms=2,
        total_area=Decimal("55"),
        condition="euro",
        cadastre_status="available",
        price=Decimal("50000"),
        currency="USD",
        has_furniture=True,
        negotiable=False,
        status="approved",
    )
    # Property 2: Rent, Apartment, Toshkent / Chilonzor, 2 rooms, 500 USD, 55 m²
    p2 = Property(
        owner_user_id=user.id,
        listing_type="rent",
        property_type="apartment",
        region="Toshkent",
        district="Chilonzor",
        address="3-mavze",
        rooms=2,
        total_area=Decimal("55"),
        condition="euro",
        cadastre_status="available",
        price=Decimal("500"),
        currency="USD",
        has_furniture=True,
        negotiable=False,
        status="approved",
    )
    # Property 3: Sale, House, Samarkand, 5 rooms, 120k USD, 150 m²
    p3 = Property(
        owner_user_id=user.id,
        listing_type="sale",
        property_type="house",
        region="Samarkand",
        district="Siyob",
        address="Bog' ko'chasi",
        rooms=6,
        total_area=Decimal("150"),
        condition="renovated",
        cadastre_status="available",
        price=Decimal("120000"),
        currency="USD",
        has_furniture=False,
        negotiable=True,
        status="approved",
    )
    # Property 4: Sale, Apartment, Toshkent, 1 room, 600_000_000 UZS
    p4 = Property(
        owner_user_id=user.id,
        listing_type="sale",
        property_type="apartment",
        region="Toshkent",
        district="Mirzo Ulug'bek",
        address="Buyuk Ipak Yo'li",
        rooms=1,
        total_area=Decimal("40"),
        condition="new",
        cadastre_status="available",
        price=Decimal("600000000"),
        currency="UZS",
        has_furniture=False,
        negotiable=False,
        status="approved",
    )
    db_session.add_all([p1, p2, p3, p4])
    await db_session.flush()

    service = PropertySearchService()

    # 1. Sale excludes Rent
    res_sale, count_sale, _ = await service.search(
        db_session, PropertySearchFilters(listing_type="sale")
    )
    assert count_sale == 3
    assert all(p.listing_type == "sale" for p in res_sale)

    # 2. Rent excludes Sale
    res_rent, count_rent, _ = await service.search(
        db_session, PropertySearchFilters(listing_type="rent")
    )
    assert count_rent == 1
    assert res_rent[0].id == p2.id

    # 3. Property type filter
    res_house, count_house, _ = await service.search(
        db_session, PropertySearchFilters(listing_type="sale", property_type="house")
    )
    assert count_house == 1
    assert res_house[0].id == p3.id

    # 4. Rooms 5+ filter (min_rooms=5)
    res_5plus, count_5plus, _ = await service.search(
        db_session, PropertySearchFilters(listing_type="sale", min_rooms=5)
    )
    assert count_5plus == 1
    assert res_5plus[0].rooms == 6

    # 5. Strict currency filtering (USD budget does NOT match UZS listing)
    res_usd, count_usd, _ = await service.search(
        db_session,
        PropertySearchFilters(
            listing_type="sale",
            min_price=Decimal("30000"),
            max_price=Decimal("80000"),
            currency="USD",
        ),
    )
    assert count_usd == 1
    assert res_usd[0].id == p1.id

    # 6. Minimum area filter
    res_area, count_area, _ = await service.search(
        db_session,
        PropertySearchFilters(listing_type="sale", min_area=Decimal("100")),
    )
    assert count_area == 1
    assert res_area[0].id == p3.id


@pytest.mark.asyncio
async def test_search_pagination_and_boundaries(db_session: AsyncSession) -> None:
    """Verify search pagination limits and page calculation."""
    user = User(telegram_id=99003, first_name="Owner", language="uz")
    db_session.add(user)
    await db_session.flush()

    # Create 12 approved sale properties
    for i in range(1, 13):
        db_session.add(
            Property(
                owner_user_id=user.id,
                listing_type="sale",
                property_type="apartment",
                region="Toshkent",
                district="Yunusobod",
                address=f"{i}-mavze",
                rooms=2,
                total_area=Decimal("60"),
                condition="new",
                cadastre_status="available",
                price=Decimal(40000 + i * 1000),
                currency="USD",
                has_furniture=False,
                negotiable=False,
                status="approved",
            )
        )
    await db_session.flush()

    service = PropertySearchService()
    filters = PropertySearchFilters(listing_type="sale")

    # Page 1 (size 5) -> 5 items, total 12, total_pages 3
    p1_items, total, total_pages = await service.search(db_session, filters, page=1, page_size=5)
    assert total == 12
    assert total_pages == 3
    assert len(p1_items) == 5

    # Page 3 (size 5) -> remaining 2 items
    p3_items, _, _ = await service.search(db_session, filters, page=3, page_size=5)
    assert len(p3_items) == 2

    # Beyond boundary (Page 4) -> 0 items
    p4_items, _, _ = await service.search(db_session, filters, page=4, page_size=5)
    assert len(p4_items) == 0


@pytest.mark.asyncio
async def test_public_property_details_security(db_session: AsyncSession) -> None:
    """Verify get_approved_details only returns approved listings and rejects others."""
    user = User(telegram_id=99004, first_name="Owner", language="uz")
    db_session.add(user)
    await db_session.flush()

    approved_prop = Property(
        owner_user_id=user.id,
        listing_type="sale",
        property_type="apartment",
        region="Toshkent",
        district="Yunusobod",
        address="1-mavze",
        rooms=2,
        total_area=Decimal("50"),
        condition="euro",
        cadastre_status="available",
        price=Decimal("45000"),
        currency="USD",
        has_furniture=False,
        negotiable=False,
        status="approved",
    )
    draft_prop = Property(
        owner_user_id=user.id,
        listing_type="sale",
        property_type="apartment",
        region="Toshkent",
        district="Yunusobod",
        address="1-mavze",
        rooms=2,
        total_area=Decimal("50"),
        condition="euro",
        cadastre_status="available",
        price=Decimal("45000"),
        currency="USD",
        has_furniture=False,
        negotiable=False,
        status="draft",
    )
    db_session.add_all([approved_prop, draft_prop])
    await db_session.flush()

    service = PropertySearchService()

    # Approved property succeeds
    retrieved = await service.get_approved_details(db_session, approved_prop.id)
    assert retrieved.id == approved_prop.id

    # Draft property raises PropertyNotFoundError
    with pytest.raises(PropertyNotFoundError):
        await service.get_approved_details(db_session, draft_prop.id)

    # Non-existent property raises PropertyNotFoundError
    with pytest.raises(PropertyNotFoundError):
        await service.get_approved_details(db_session, 999999)
