"""Service for viewing requests, broker contact, and appointment lifecycle."""

from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DuplicateViewingRequestError,
    InvalidViewingTransitionError,
    PropertyUnavailableError,
    ViewingPermissionError,
    ViewingRequestNotFoundError,
    ViewingValidationError,
)
from app.logging import get_logger
from app.models.viewing_request import VIEWING_OUTCOMES, ViewingRequest
from app.repositories.property_repository import PropertyRepository
from app.repositories.user_repository import UserRepository
from app.repositories.viewing_request_repository import ViewingRequestRepository

logger = get_logger(__name__)

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"assigned", "accepted", "rejected", "cancelled"},
    "assigned": {"accepted", "rejected", "cancelled"},
    "accepted": {"completed", "cancelled"},
    "rejected": set(),
    "cancelled": set(),
    "completed": set(),
}

STAFF_ROLES: set[str] = {"superadmin", "head_broker", "sales_broker", "rental_broker"}


class ViewingRequestService:
    """Service managing customer appointment requests and broker workflows."""

    def __init__(
        self,
        viewing_repo: ViewingRequestRepository | None = None,
        property_repo: PropertyRepository | None = None,
        user_repo: UserRepository | None = None,
    ) -> None:
        self.viewing_repo = viewing_repo or ViewingRequestRepository()
        self.property_repo = property_repo or PropertyRepository()
        self.user_repo = user_repo or UserRepository()

    def validate_transition(self, current_status: str, target_status: str) -> None:
        """Validate state machine transition.

        Allowed transitions:
        - pending -> assigned, accepted, rejected, cancelled
        - assigned -> accepted, rejected, cancelled
        - accepted -> completed, cancelled
        Disallowed:
        - terminal states (rejected, cancelled, completed) cannot transition.
        """
        allowed = ALLOWED_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise InvalidViewingTransitionError(
                f"Cannot transition viewing request from '{current_status}' to '{target_status}'."
            )

    async def get_broker_allowed_listing_types(
        self, session: AsyncSession, broker_user_id: int
    ) -> list[str]:
        """Determine listing types a broker is authorized to manage.

        Rules:
        - superadmin, head_broker: ['sale', 'rent']
        - sales_broker: ['sale']
        - rental_broker: ['rent']
        - others: empty list (not authorized)
        """
        user = await self.user_repo.get_by_id(session, broker_user_id)
        if not user:
            return []

        user_roles = {r.name for r in user.roles}

        if "superadmin" in user_roles or "head_broker" in user_roles:
            return ["sale", "rent"]
        if "sales_broker" in user_roles:
            return ["sale"]
        if "rental_broker" in user_roles:
            return ["rent"]
        return []

    async def create_viewing_request(
        self,
        session: AsyncSession,
        *,
        customer_user_id: int,
        property_id: int,
        preferred_date: date,
        preferred_time: str,
        customer_comment: str | None = None,
    ) -> ViewingRequest:
        """Create a new viewing appointment request for an approved property."""
        # 1. Verify property eligibility
        prop = await self.property_repo.get_by_id(session, property_id)
        if not prop or prop.status != "approved":
            raise PropertyUnavailableError("Ko‘chmas mulk mavjud emas yoki tasdiqlanmagan.")

        # 2. Validate preferred_date (must not be in the past)
        today = datetime.now(UTC).date()
        if preferred_date < today:
            raise ViewingValidationError("Uchrashuv sanasi o‘tgan kunda bo‘lishi mumkin emas.")

        # 3. Validate preferred_time
        clean_time = (preferred_time or "").strip()
        if not clean_time:
            raise ViewingValidationError("Afzal ko‘rgan vaqtni tanlang.")

        # 4. Check duplicate active viewing request
        duplicate = await self.viewing_repo.find_active_duplicate(
            session,
            customer_user_id=customer_user_id,
            property_id=property_id,
            request_type="viewing",
            preferred_date=preferred_date,
            preferred_time=clean_time,
        )
        if duplicate:
            raise DuplicateViewingRequestError(
                "Ushbu sana va vaqt uchun faol ko‘rish so‘rovingiz allaqachon mavjud."
            )

        # 5. Create request
        req = await self.viewing_repo.create(
            session,
            property_id=property_id,
            customer_user_id=customer_user_id,
            request_type="viewing",
            preferred_date=preferred_date,
            preferred_time=clean_time,
            customer_comment=customer_comment.strip() if customer_comment else None,
        )
        logger.info(
            "Created viewing request id=%d for customer_id=%d prop_id=%d",
            req.id,
            customer_user_id,
            property_id,
        )
        return req

    async def create_broker_contact_request(
        self,
        session: AsyncSession,
        *,
        customer_user_id: int,
        property_id: int,
        customer_comment: str | None = None,
    ) -> ViewingRequest:
        """Create a broker contact request for an approved property."""
        # 1. Verify property eligibility
        prop = await self.property_repo.get_by_id(session, property_id)
        if not prop or prop.status != "approved":
            raise PropertyUnavailableError("Ko‘chmas mulk mavjud emas yoki tasdiqlanmagan.")

        # 2. Check duplicate active broker_contact request
        duplicate = await self.viewing_repo.find_active_duplicate(
            session,
            customer_user_id=customer_user_id,
            property_id=property_id,
            request_type="broker_contact",
        )
        if duplicate:
            raise DuplicateViewingRequestError(
                "Ushbu mulk bo‘yicha broker bilan bog‘lanish so‘rovingiz allaqachon faol."
            )

        # 3. Create request
        req = await self.viewing_repo.create(
            session,
            property_id=property_id,
            customer_user_id=customer_user_id,
            request_type="broker_contact",
            customer_comment=customer_comment.strip() if customer_comment else None,
        )
        logger.info(
            "Created broker_contact request id=%d for customer_id=%d prop_id=%d",
            req.id,
            customer_user_id,
            property_id,
        )
        return req

    async def list_customer_requests(
        self, session: AsyncSession, customer_user_id: int
    ) -> list[ViewingRequest]:
        """List appointment and broker contact requests for customer."""
        return await self.viewing_repo.list_by_customer(session, customer_user_id)

    async def cancel_customer_request(
        self,
        session: AsyncSession,
        *,
        request_id: int,
        customer_user_id: int,
        reason: str | None = None,
    ) -> ViewingRequest:
        """Allow customer to cancel their own pending/assigned/accepted request."""
        req = await self.viewing_repo.get_by_id(session, request_id)
        if not req:
            raise ViewingRequestNotFoundError("So‘rov topilmadi.")

        if req.customer_user_id != customer_user_id:
            raise ViewingPermissionError(
                "Siz faqat o‘zingizning so‘rovlaringizni bekor qila olasiz."
            )

        self.validate_transition(req.status, "cancelled")

        updated = await self.viewing_repo.update_status(
            session,
            request_id,
            status="cancelled",
            cancelled_at=datetime.now(UTC),
            cancellation_reason=reason or "Foydalanuvchi tomonidan bekor qilindi.",
        )
        if not updated:
            raise ViewingRequestNotFoundError("So‘rov topilmadi.")

        logger.info(
            "Customer id=%d cancelled viewing request id=%d",
            customer_user_id,
            request_id,
        )
        return updated

    async def list_broker_requests(
        self,
        session: AsyncSession,
        broker_user_id: int,
        statuses: list[str] | None = None,
    ) -> list[ViewingRequest]:
        """List requests accessible to the specified broker according to RBAC."""
        allowed_types = await self.get_broker_allowed_listing_types(session, broker_user_id)
        if not allowed_types:
            raise ViewingPermissionError("Sizda broker so‘rovlarini ko‘rish vakolati yo‘q.")

        return await self.viewing_repo.list_for_broker(
            session,
            allowed_listing_types=allowed_types,
            broker_user_id=broker_user_id,
            statuses=statuses,
        )

    async def claim_request(
        self,
        session: AsyncSession,
        *,
        request_id: int,
        broker_user_id: int,
    ) -> ViewingRequest:
        """Claim an unassigned request for an authorized broker."""
        req = await self.viewing_repo.get_by_id(session, request_id)
        if not req:
            raise ViewingRequestNotFoundError("So‘rov topilmadi.")

        allowed_types = await self.get_broker_allowed_listing_types(session, broker_user_id)
        if req.property.listing_type not in allowed_types:
            raise ViewingPermissionError("Sizda ushbu toifadagi so‘rovni qabul qilish huquqi yo‘q.")

        if req.status not in ("pending", "assigned"):
            raise InvalidViewingTransitionError(
                f"Cannot claim viewing request in '{req.status}' status."
            )

        success = await self.viewing_repo.claim_request(
            session,
            request_id=request_id,
            broker_user_id=broker_user_id,
        )
        if not success:
            raise ViewingPermissionError("So‘rov allaqachon boshqa broker tomonidan olingan.")

        claimed = await self.viewing_repo.get_by_id(session, request_id)
        if not claimed:
            raise ViewingRequestNotFoundError("So‘rov topilmadi.")
        return claimed

    async def accept_request(
        self,
        session: AsyncSession,
        *,
        request_id: int,
        broker_user_id: int,
    ) -> ViewingRequest:
        """Accept a request, confirming the viewing or broker contact."""
        req = await self.viewing_repo.get_by_id(session, request_id)
        if not req:
            raise ViewingRequestNotFoundError("So‘rov topilmadi.")

        allowed_types = await self.get_broker_allowed_listing_types(session, broker_user_id)
        if req.property.listing_type not in allowed_types:
            raise ViewingPermissionError("Sizda ushbu toifadagi so‘rovni tasdiqlash huquqi yo‘q.")

        # Verify property is still approved (not sold/rented/archived)
        if req.property.status != "approved":
            raise PropertyUnavailableError(
                f"Ko‘chmas mulk hozirda faol emas (status: {req.property.status})."
            )

        self.validate_transition(req.status, "accepted")

        updated = await self.viewing_repo.update_status(
            session,
            request_id,
            status="accepted",
            broker_user_id=broker_user_id,
            accepted_at=datetime.now(UTC),
        )
        if not updated:
            raise ViewingRequestNotFoundError("So‘rov topilmadi.")

        logger.info(
            "Broker id=%d accepted viewing request id=%d",
            broker_user_id,
            request_id,
        )
        return updated

    async def reject_request(
        self,
        session: AsyncSession,
        *,
        request_id: int,
        broker_user_id: int,
        reason: str,
    ) -> ViewingRequest:
        """Reject a viewing or broker contact request with reason."""
        req = await self.viewing_repo.get_by_id(session, request_id)
        if not req:
            raise ViewingRequestNotFoundError("So‘rov topilmadi.")

        allowed_types = await self.get_broker_allowed_listing_types(session, broker_user_id)
        if req.property.listing_type not in allowed_types:
            raise ViewingPermissionError("Sizda ushbu toifadagi so‘rovni rad etish huquqi yo‘q.")

        clean_reason = (reason or "").strip()
        if len(clean_reason) < 3:
            raise ViewingValidationError("Rad etish sababini batafsilroq kiriting.")

        self.validate_transition(req.status, "rejected")

        updated = await self.viewing_repo.update_status(
            session,
            request_id,
            status="rejected",
            broker_user_id=broker_user_id,
            rejected_at=datetime.now(UTC),
            rejection_reason=clean_reason,
        )
        if not updated:
            raise ViewingRequestNotFoundError("So‘rov topilmadi.")

        logger.info(
            "Broker id=%d rejected viewing request id=%d with reason: %s",
            broker_user_id,
            request_id,
            clean_reason,
        )
        return updated

    async def complete_request(
        self,
        session: AsyncSession,
        *,
        request_id: int,
        broker_user_id: int,
        outcome: str,
    ) -> ViewingRequest:
        """Mark accepted request as completed and record outcome."""
        req = await self.viewing_repo.get_by_id(session, request_id)
        if not req:
            raise ViewingRequestNotFoundError("So‘rov topilmadi.")

        allowed_types = await self.get_broker_allowed_listing_types(session, broker_user_id)
        if req.property.listing_type not in allowed_types:
            raise ViewingPermissionError("Sizda ushbu toifadagi so‘rovni yakunlash huquqi yo‘q.")

        if outcome not in VIEWING_OUTCOMES:
            raise ViewingValidationError(
                f"Noto‘g‘ri natija '{outcome}'. Ruxsat etilganlar: {VIEWING_OUTCOMES}"
            )

        self.validate_transition(req.status, "completed")

        updated = await self.viewing_repo.update_status(
            session,
            request_id,
            status="completed",
            completed_at=datetime.now(UTC),
            outcome=outcome,
        )
        if not updated:
            raise ViewingRequestNotFoundError("So‘rov topilmadi.")

        logger.info(
            "Broker id=%d completed viewing request id=%d outcome=%s",
            broker_user_id,
            request_id,
            outcome,
        )
        return updated
