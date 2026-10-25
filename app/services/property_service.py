"""Property domain service implementing listing lifecycle and RBAC enforcement."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationError,
    IncompletePropertyError,
    InvalidPropertyStatusError,
    PropertyAccessDeniedError,
    PropertyNotFoundError,
)
from app.logging import get_logger
from app.models.property import (
    CADASTRE_STATUSES,
    LISTING_TYPES,
    PROPERTY_CONDITIONS,
    PROPERTY_TYPES,
    SUPPORTED_CURRENCIES,
    Property,
)
from app.models.property_media import PropertyMedia
from app.repositories.property_media_repository import PropertyMediaRepository
from app.repositories.property_repository import PropertyRepository
from app.repositories.role_repository import RoleRepository

logger = get_logger(__name__)

# Photo limits for property listings
MIN_PHOTOS_REQUIRED = 1
MAX_PHOTOS_ALLOWED = 15

# Reviewer role authorization mapping
AUTHORIZED_REVIEW_ROLES = {
    "superadmin": ("sale", "rent"),
    "head_broker": ("sale", "rent"),
    "sales_broker": ("sale",),
    "rental_broker": ("rent",),
}


class PropertyService:
    """Service orchestrating property creation, validation, ownership, and staff review."""

    def __init__(
        self,
        property_repo: PropertyRepository | None = None,
        media_repo: PropertyMediaRepository | None = None,
        role_repo: RoleRepository | None = None,
    ) -> None:
        self.property_repo = property_repo or PropertyRepository()
        self.media_repo = media_repo or PropertyMediaRepository()
        self.role_repo = role_repo or RoleRepository()

    def validate_property_attributes(
        self,
        *,
        listing_type: str,
        property_type: str,
        rooms: int,
        total_area: Decimal,
        condition: str,
        price: Decimal,
        currency: str,
        cadastre_status: str = "unknown",
        floor: int | None = None,
        total_floors: int | None = None,
    ) -> None:
        """Validate property enumeration and numeric domain rules."""
        if listing_type not in LISTING_TYPES:
            raise IncompletePropertyError(
                f"Invalid listing_type '{listing_type}'. Expected one of {LISTING_TYPES}"
            )
        if property_type not in PROPERTY_TYPES:
            raise IncompletePropertyError(
                f"Invalid property_type '{property_type}'. Expected one of {PROPERTY_TYPES}"
            )
        if condition not in PROPERTY_CONDITIONS:
            raise IncompletePropertyError(
                f"Invalid condition '{condition}'. Expected one of {PROPERTY_CONDITIONS}"
            )
        if cadastre_status not in CADASTRE_STATUSES:
            raise IncompletePropertyError(
                f"Invalid cadastre_status '{cadastre_status}'. Expected one of {CADASTRE_STATUSES}"
            )
        if currency not in SUPPORTED_CURRENCIES:
            raise IncompletePropertyError(
                f"Invalid currency '{currency}'. Expected one of {SUPPORTED_CURRENCIES}"
            )

        # Numeric validations
        if rooms <= 0:
            raise IncompletePropertyError("Rooms count must be greater than zero.")
        if total_area <= Decimal(0):
            raise IncompletePropertyError("Total area must be greater than zero.")
        if price <= Decimal(0):
            raise IncompletePropertyError("Price must be greater than zero.")

        if floor is not None and floor < 0:
            raise IncompletePropertyError("Floor cannot be negative.")
        if total_floors is not None and total_floors <= 0:
            raise IncompletePropertyError("Total floors must be greater than zero.")
        if (
            floor is not None
            and total_floors is not None
            and floor > total_floors
            and total_floors > 0
        ):
            raise IncompletePropertyError(
                f"Floor ({floor}) cannot exceed total floors ({total_floors})."
            )

    async def create_draft(
        self,
        session: AsyncSession,
        *,
        owner_user_id: int,
        listing_type: str,
        property_type: str,
        region: str,
        district: str,
        address: str,
        rooms: int,
        total_area: Decimal,
        condition: str,
        price: Decimal,
        currency: str = "USD",
        negotiable: bool = False,
        living_area: Decimal | None = None,
        floor: int | None = None,
        total_floors: int | None = None,
        latitude: Decimal | None = None,
        longitude: Decimal | None = None,
        construction_type: str | None = None,
        has_furniture: bool = False,
        cadastre_status: str = "unknown",
        title: str | None = None,
        description: str | None = None,
    ) -> Property:
        """Create a new property in 'draft' status."""
        self.validate_property_attributes(
            listing_type=listing_type,
            property_type=property_type,
            rooms=rooms,
            total_area=total_area,
            condition=condition,
            price=price,
            currency=currency,
            cadastre_status=cadastre_status,
            floor=floor,
            total_floors=total_floors,
        )

        return await self.property_repo.create_draft(
            session,
            owner_user_id=owner_user_id,
            listing_type=listing_type,
            property_type=property_type,
            region=region,
            district=district,
            address=address,
            rooms=rooms,
            total_area=total_area,
            living_area=living_area,
            floor=floor,
            total_floors=total_floors,
            condition=condition,
            construction_type=construction_type,
            has_furniture=has_furniture,
            cadastre_status=cadastre_status,
            price=price,
            currency=currency,
            negotiable=negotiable,
            latitude=latitude,
            longitude=longitude,
            title=title,
            description=description,
        )

    async def add_photo(
        self,
        session: AsyncSession,
        *,
        property_id: int,
        owner_user_id: int,
        telegram_file_id: str,
        telegram_file_unique_id: str,
    ) -> PropertyMedia:
        """Add photo to property, enforcing ownership, draft state, and max photo limits."""
        prop = await self.property_repo.get_by_id(session, property_id)
        if not prop:
            raise PropertyNotFoundError(f"Property id={property_id} not found.")

        if prop.owner_user_id != owner_user_id:
            raise PropertyAccessDeniedError("You do not have permission to modify this property.")

        if prop.status != "draft":
            raise InvalidPropertyStatusError(
                f"Cannot add media to property in '{prop.status}' status."
            )

        current_count = await self.media_repo.count_by_property(session, property_id)
        if current_count >= MAX_PHOTOS_ALLOWED:
            raise IncompletePropertyError(f"Maximum limit of {MAX_PHOTOS_ALLOWED} photos reached.")

        return await self.media_repo.add_media(
            session,
            property_id=property_id,
            telegram_file_id=telegram_file_id,
            telegram_file_unique_id=telegram_file_unique_id,
            media_type="photo",
            sort_order=current_count + 1,
        )

    async def submit_listing(
        self,
        session: AsyncSession,
        *,
        property_id: int,
        owner_user_id: int,
    ) -> Property:
        """Submit draft listing for staff review."""
        prop = await self.property_repo.get_by_id(session, property_id)
        if not prop:
            raise PropertyNotFoundError(f"Property id={property_id} not found.")

        if prop.owner_user_id != owner_user_id:
            raise PropertyAccessDeniedError("You do not have permission to submit this property.")

        if prop.status != "draft":
            raise InvalidPropertyStatusError(
                f"Cannot submit property from '{prop.status}' status. Must be 'draft'."
            )

        # Enforce minimum photos
        photo_count = await self.media_repo.count_by_property(session, property_id)
        if photo_count < MIN_PHOTOS_REQUIRED:
            raise IncompletePropertyError(
                f"At least {MIN_PHOTOS_REQUIRED} photo is required before submission."
            )

        updated = await self.property_repo.set_status(
            session,
            property_id,
            "submitted",
            submitted_at=datetime.now(UTC),
        )
        if not updated:
            raise PropertyNotFoundError(f"Property id={property_id} not found.")

        logger.info(
            "Property id=%d submitted for review by owner_user_id=%d", property_id, owner_user_id
        )
        return updated

    async def verify_reviewer_permission(
        self,
        session: AsyncSession,
        reviewer_user_id: int,
        listing_type: str,
    ) -> None:
        """Check whether reviewer has RBAC permission to review this listing_type."""
        user_roles = await self.role_repo.get_user_roles(session, reviewer_user_id)
        can_review = False
        for role in user_roles:
            if role in AUTHORIZED_REVIEW_ROLES and listing_type in AUTHORIZED_REVIEW_ROLES[role]:
                can_review = True
                break

        if not can_review:
            raise AuthorizationError(
                f"User id={reviewer_user_id} with roles {user_roles} is not authorized "
                f"to review '{listing_type}' listings."
            )

    async def start_review(
        self,
        session: AsyncSession,
        *,
        property_id: int,
        reviewer_user_id: int,
    ) -> Property:
        """Transition submitted property to 'under_review' status."""
        prop = await self.property_repo.get_by_id(session, property_id)
        if not prop:
            raise PropertyNotFoundError(f"Property id={property_id} not found.")

        await self.verify_reviewer_permission(session, reviewer_user_id, prop.listing_type)

        if prop.status not in ("submitted", "under_review"):
            raise InvalidPropertyStatusError(
                f"Cannot review property in '{prop.status}' status. Must be 'submitted'."
            )

        updated = await self.property_repo.set_status(session, property_id, "under_review")
        if not updated:
            raise PropertyNotFoundError(f"Property id={property_id} not found.")
        return updated

    async def approve_listing(
        self,
        session: AsyncSession,
        *,
        property_id: int,
        reviewer_user_id: int,
    ) -> Property:
        """Approve property for listing publication."""
        prop = await self.property_repo.get_by_id(session, property_id)
        if not prop:
            raise PropertyNotFoundError(f"Property id={property_id} not found.")

        await self.verify_reviewer_permission(session, reviewer_user_id, prop.listing_type)

        if prop.status not in ("submitted", "under_review"):
            raise InvalidPropertyStatusError(
                f"Cannot approve property in '{prop.status}' status."
            )

        updated = await self.property_repo.set_status(
            session,
            property_id,
            "approved",
            approved_at=datetime.now(UTC),
            approved_by_user_id=reviewer_user_id,
            rejection_reason=None,
        )
        if not updated:
            raise PropertyNotFoundError(f"Property id={property_id} not found.")

        logger.info(
            "Property id=%d approved by reviewer_user_id=%d", property_id, reviewer_user_id
        )
        return updated

    async def reject_listing(
        self,
        session: AsyncSession,
        *,
        property_id: int,
        reviewer_user_id: int,
        rejection_reason: str,
    ) -> Property:
        """Reject property listing with mandatory reason."""
        if not rejection_reason or not rejection_reason.strip():
            raise IncompletePropertyError("Rejection reason must be provided.")

        prop = await self.property_repo.get_by_id(session, property_id)
        if not prop:
            raise PropertyNotFoundError(f"Property id={property_id} not found.")

        await self.verify_reviewer_permission(session, reviewer_user_id, prop.listing_type)

        if prop.status not in ("submitted", "under_review"):
            raise InvalidPropertyStatusError(
                f"Cannot reject property in '{prop.status}' status."
            )

        updated = await self.property_repo.set_status(
            session,
            property_id,
            "rejected",
            rejected_at=datetime.now(UTC),
            rejection_reason=rejection_reason.strip(),
        )
        if not updated:
            raise PropertyNotFoundError(f"Property id={property_id} not found.")

        logger.info(
            "Property id=%d rejected by reviewer_user_id=%d", property_id, reviewer_user_id
        )
        return updated

    async def get_owned_property(
        self,
        session: AsyncSession,
        *,
        property_id: int,
        owner_user_id: int,
    ) -> Property:
        """Retrieve property ensuring it belongs to the requesting owner."""
        prop = await self.property_repo.get_by_id(session, property_id)
        if not prop:
            raise PropertyNotFoundError(f"Property id={property_id} not found.")

        if prop.owner_user_id != owner_user_id:
            raise PropertyAccessDeniedError("You do not have permission to view this property.")

        return prop

    async def list_owner_properties(
        self,
        session: AsyncSession,
        owner_user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Property]:
        """Fetch all properties belonging to owner."""
        return await self.property_repo.list_by_owner(session, owner_user_id, limit, offset)

    async def list_pending_review_properties(
        self,
        session: AsyncSession,
        reviewer_user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Property]:
        """List pending properties for reviewer based on RBAC roles."""
        user_roles = await self.role_repo.get_user_roles(session, reviewer_user_id)
        allowed_types: set[str] = set()
        for role in user_roles:
            if role in AUTHORIZED_REVIEW_ROLES:
                allowed_types.update(AUTHORIZED_REVIEW_ROLES[role])

        if not allowed_types:
            raise AuthorizationError("User is not authorized to review any properties.")

        # If both sale and rent are allowed
        if len(allowed_types) >= 2:
            submitted = await self.property_repo.list_by_status(
                session, "submitted", None, limit, offset
            )
            under_review = await self.property_repo.list_by_status(
                session, "under_review", None, limit, offset
            )
            return submitted + under_review

        # Single allowed type
        listing_type = next(iter(allowed_types))
        submitted = await self.property_repo.list_by_status(
            session, "submitted", listing_type, limit, offset
        )
        under_review = await self.property_repo.list_by_status(
            session, "under_review", listing_type, limit, offset
        )
        return submitted + under_review
