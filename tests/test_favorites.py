"""Tests for Favorite model, repository, and FavoriteService."""

from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PropertyNotFoundError
from app.models.favorite import Favorite
from app.models.property import Property
from app.models.user import User
from app.repositories.favorite_repository import FavoriteRepository
from app.services.favorite_service import FavoriteService


@pytest.mark.asyncio
async def test_favorite_model_and_uniqueness(db_session: AsyncSession) -> None:
    """Verify Favorite table uniqueness on (user_id, property_id)."""
    user = User(telegram_id=98001, first_name="User", language="uz")
    prop = Property(
        owner_user_id=1,
        listing_type="sale",
        property_type="apartment",
        region="Toshkent",
        district="Yunusobod",
        address="1-mavze",
        rooms=2,
        total_area=Decimal("60"),
        condition="new",
        cadastre_status="available",
        price=Decimal("60000"),
        currency="USD",
        has_furniture=False,
        negotiable=False,
        status="approved",
    )
    db_session.add_all([user, prop])
    await db_session.flush()

    fav1 = Favorite(user_id=user.id, property_id=prop.id)
    db_session.add(fav1)
    await db_session.flush()

    # Duplicate favorite should violate unique constraint
    fav2 = Favorite(user_id=user.id, property_id=prop.id)
    db_session.add(fav2)
    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_favorite_repository_crud_and_idempotency(db_session: AsyncSession) -> None:
    """Verify FavoriteRepository add, remove, and idempotency."""
    user = User(telegram_id=98002, first_name="Buyer", language="uz")
    prop = Property(
        owner_user_id=1,
        listing_type="sale",
        property_type="apartment",
        region="Toshkent",
        district="Yunusobod",
        address="1-mavze",
        rooms=2,
        total_area=Decimal("60"),
        condition="new",
        cadastre_status="available",
        price=Decimal("60000"),
        currency="USD",
        has_furniture=False,
        negotiable=False,
        status="approved",
    )
    db_session.add_all([user, prop])
    await db_session.flush()

    repo = FavoriteRepository()

    # 1. Check is_favorite False initially
    assert not await repo.is_favorite(db_session, user_id=user.id, property_id=prop.id)

    # 2. Add favorite
    fav = await repo.add(db_session, user_id=user.id, property_id=prop.id)
    assert fav.id is not None
    assert await repo.is_favorite(db_session, user_id=user.id, property_id=prop.id)

    # 3. Add duplicate is idempotent
    fav_dup = await repo.add(db_session, user_id=user.id, property_id=prop.id)
    assert fav_dup.id == fav.id

    # 4. Remove favorite
    assert await repo.remove(db_session, user_id=user.id, property_id=prop.id)
    assert not await repo.is_favorite(db_session, user_id=user.id, property_id=prop.id)

    # 5. Remove non-existent does not crash
    assert not await repo.remove(db_session, user_id=user.id, property_id=prop.id)


@pytest.mark.asyncio
async def test_favorite_service_security_and_unavailable_hiding(
    db_session: AsyncSession,
) -> None:
    """Verify FavoriteService only favorites approved properties and hides unavailable ones."""
    user = User(telegram_id=98003, first_name="Buyer", language="uz")
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
        total_area=Decimal("60"),
        condition="new",
        cadastre_status="available",
        price=Decimal("60000"),
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
        total_area=Decimal("60"),
        condition="new",
        cadastre_status="available",
        price=Decimal("60000"),
        currency="USD",
        has_furniture=False,
        negotiable=False,
        status="draft",
    )
    db_session.add_all([approved_prop, draft_prop])
    await db_session.flush()

    service = FavoriteService()

    # 1. Favoriting draft property fails
    with pytest.raises(PropertyNotFoundError):
        await service.add_favorite(db_session, user_id=user.id, property_id=draft_prop.id)

    # 2. Favoriting approved property succeeds
    await service.add_favorite(db_session, user_id=user.id, property_id=approved_prop.id)
    saved = await service.list_saved_properties(db_session, user_id=user.id)
    assert len(saved) == 1
    assert saved[0].id == approved_prop.id

    # 3. If approved property becomes 'sold', it is hidden from active saved list
    approved_prop.status = "sold"
    await db_session.flush()

    saved_after_sold = await service.list_saved_properties(db_session, user_id=user.id)
    assert len(saved_after_sold) == 0
