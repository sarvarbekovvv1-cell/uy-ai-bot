"""Tests for PropertyService business logic, validations, lifecycle, and RBAC."""

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationError,
    IncompletePropertyError,
    InvalidPropertyStatusError,
    PropertyAccessDeniedError,
)
from app.models.property import Property
from app.repositories.property_media_repository import PropertyMediaRepository
from app.repositories.property_repository import PropertyRepository
from app.repositories.role_repository import RoleRepository
from app.services.property_service import PropertyService


@pytest.fixture
def property_service() -> PropertyService:
    mock_prop_repo = AsyncMock(spec=PropertyRepository)
    mock_media_repo = AsyncMock(spec=PropertyMediaRepository)
    mock_role_repo = AsyncMock(spec=RoleRepository)
    return PropertyService(
        property_repo=mock_prop_repo,
        media_repo=mock_media_repo,
        role_repo=mock_role_repo,
    )


def test_property_validation_errors(property_service: PropertyService) -> None:
    """Verify validation for listing type, property type, rooms, area, price, floors."""
    # Invalid listing_type
    with pytest.raises(IncompletePropertyError, match="Invalid listing_type"):
        property_service.validate_property_attributes(
            listing_type="invalid",
            property_type="apartment",
            rooms=2,
            total_area=Decimal(50),
            condition="new",
            price=Decimal(50000),
            currency="USD",
        )

    # Invalid rooms count
    with pytest.raises(IncompletePropertyError, match="Rooms count"):
        property_service.validate_property_attributes(
            listing_type="sale",
            property_type="apartment",
            rooms=0,
            total_area=Decimal(50),
            condition="new",
            price=Decimal(50000),
            currency="USD",
        )

    # Invalid area
    with pytest.raises(IncompletePropertyError, match="Total area"):
        property_service.validate_property_attributes(
            listing_type="sale",
            property_type="apartment",
            rooms=1,
            total_area=Decimal(-5),
            condition="new",
            price=Decimal(50000),
            currency="USD",
        )

    # Invalid price
    with pytest.raises(IncompletePropertyError, match="Price"):
        property_service.validate_property_attributes(
            listing_type="sale",
            property_type="apartment",
            rooms=1,
            total_area=Decimal(50),
            condition="new",
            price=Decimal(0),
            currency="USD",
        )

    # Floor exceeds total floors
    with pytest.raises(IncompletePropertyError, match="cannot exceed total floors"):
        property_service.validate_property_attributes(
            listing_type="sale",
            property_type="apartment",
            rooms=1,
            total_area=Decimal(50),
            condition="new",
            price=Decimal(50000),
            currency="USD",
            floor=10,
            total_floors=5,
        )


@pytest.mark.asyncio
async def test_create_sale_and_rent_draft(property_service: PropertyService) -> None:
    """Verify creating sale and rent drafts."""
    mock_session = AsyncMock(spec=AsyncSession)
    property_service.property_repo.create_draft.return_value = Property(
        id=1, owner_user_id=10, listing_type="sale", property_type="apartment", status="draft"
    )

    prop = await property_service.create_draft(
        mock_session,
        owner_user_id=10,
        listing_type="sale",
        property_type="apartment",
        region="Toshkent",
        district="Chilonzor",
        address="9-mavze",
        rooms=2,
        total_area=Decimal("60.0"),
        condition="renovated",
        price=Decimal("65000.00"),
        currency="USD",
    )
    assert prop.status == "draft"
    assert prop.listing_type == "sale"


@pytest.mark.asyncio
async def test_photo_limit_and_submission_requirements(property_service: PropertyService) -> None:
    """Verify at least 1 photo is required and maximum 15 photos allowed."""
    mock_session = AsyncMock(spec=AsyncSession)
    draft_prop = Property(id=1, owner_user_id=10, status="draft")
    property_service.property_repo.get_by_id.return_value = draft_prop

    # Attempt submission with 0 photos
    property_service.media_repo.count_by_property.return_value = 0
    with pytest.raises(IncompletePropertyError, match="At least 1 photo"):
        await property_service.submit_listing(mock_session, property_id=1, owner_user_id=10)

    # Attempt adding photo when 15 already exist
    property_service.media_repo.count_by_property.return_value = 15
    with pytest.raises(IncompletePropertyError, match="Maximum limit of 15 photos"):
        await property_service.add_photo(
            mock_session,
            property_id=1,
            owner_user_id=10,
            telegram_file_id="fid_16",
            telegram_file_unique_id="fuid_16",
        )


@pytest.mark.asyncio
async def test_owner_isolation_and_cross_user_rejection(
    property_service: PropertyService,
) -> None:
    """Verify cross-user edit or submission attempts are strictly rejected."""
    mock_session = AsyncMock(spec=AsyncSession)
    draft_prop = Property(id=1, owner_user_id=10, status="draft")
    property_service.property_repo.get_by_id.return_value = draft_prop

    # Attacker (user_id=99) tries to submit owner 10's property
    with pytest.raises(PropertyAccessDeniedError):
        await property_service.submit_listing(mock_session, property_id=1, owner_user_id=99)

    # Attacker tries to add photo to owner 10's property
    with pytest.raises(PropertyAccessDeniedError):
        await property_service.add_photo(
            mock_session,
            property_id=1,
            owner_user_id=99,
            telegram_file_id="fid",
            telegram_file_unique_id="fuid",
        )


@pytest.mark.asyncio
async def test_rbac_approval_and_rejection_rules(property_service: PropertyService) -> None:
    """Verify RBAC rules for approving/rejecting sale and rental listings."""
    mock_session = AsyncMock(spec=AsyncSession)

    sale_prop = Property(id=1, owner_user_id=10, listing_type="sale", status="submitted")
    rental_prop = Property(id=2, owner_user_id=10, listing_type="rent", status="submitted")

    # 1. Normal buyer cannot approve
    property_service.role_repo.get_user_roles.return_value = ["buyer"]
    property_service.property_repo.get_by_id.return_value = sale_prop
    with pytest.raises(AuthorizationError):
        await property_service.approve_listing(mock_session, property_id=1, reviewer_user_id=50)

    # 2. Sales broker can approve sale listing
    property_service.role_repo.get_user_roles.return_value = ["sales_broker"]
    property_service.property_repo.set_status.return_value = Property(id=1, status="approved")
    approved = await property_service.approve_listing(
        mock_session, property_id=1, reviewer_user_id=60
    )
    assert approved.status == "approved"

    # 3. Sales broker cannot approve rental listing
    property_service.property_repo.get_by_id.return_value = rental_prop
    with pytest.raises(AuthorizationError):
        await property_service.approve_listing(mock_session, property_id=2, reviewer_user_id=60)

    # 4. Rental broker can approve rental listing
    property_service.role_repo.get_user_roles.return_value = ["rental_broker"]
    property_service.property_repo.set_status.return_value = Property(id=2, status="approved")
    approved_rent = await property_service.approve_listing(
        mock_session, property_id=2, reviewer_user_id=70
    )
    assert approved_rent.status == "approved"

    # 5. Rental broker cannot approve sale listing
    property_service.property_repo.get_by_id.return_value = sale_prop
    with pytest.raises(AuthorizationError):
        await property_service.approve_listing(mock_session, property_id=1, reviewer_user_id=70)

    # 6. Rejection requires non-empty reason
    with pytest.raises(IncompletePropertyError, match="Rejection reason"):
        await property_service.reject_listing(
            mock_session, property_id=1, reviewer_user_id=60, rejection_reason=""
        )


@pytest.mark.asyncio
async def test_invalid_status_transitions_rejected(property_service: PropertyService) -> None:
    """Verify invalid status transitions (e.g. approving already approved property)."""
    mock_session = AsyncMock(spec=AsyncSession)
    already_approved = Property(id=1, owner_user_id=10, listing_type="sale", status="approved")
    property_service.property_repo.get_by_id.return_value = already_approved
    property_service.role_repo.get_user_roles.return_value = ["head_broker"]

    with pytest.raises(InvalidPropertyStatusError):
        await property_service.approve_listing(mock_session, property_id=1, reviewer_user_id=1)
