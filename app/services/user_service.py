"""User management and registration domain services."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UyAIError
from app.logging import get_logger
from app.models.role import DEFAULT_CUSTOMER_ROLE, SYSTEM_ROLES
from app.models.user import User
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.utils.phone import normalize_phone_number

logger = get_logger(__name__)


class UserService:
    """Service orchestrating user lookups, registration, profile updates, and role assignments."""

    def __init__(
        self,
        user_repo: UserRepository | None = None,
        role_repo: RoleRepository | None = None,
    ) -> None:
        self.user_repo = user_repo or UserRepository()
        self.role_repo = role_repo or RoleRepository()

    async def get_by_telegram_id(self, session: AsyncSession, telegram_id: int) -> User | None:
        """Fetch user by Telegram ID."""
        return await self.user_repo.get_by_telegram_id(session, telegram_id)

    async def is_registration_complete(self, user: User | None) -> bool:
        """Check whether a user has completed the mandatory registration steps."""
        if not user:
            return False
        # Registration requires accepted consent, chosen language, and a valid phone
        return bool(user.consent_accepted_at is not None and user.phone is not None)

    async def initialize_user(
        self,
        session: AsyncSession,
        *,
        telegram_id: int,
        language: str = "uz",
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> User:
        """Create initial user record or return existing record safely."""
        user = await self.user_repo.get_by_telegram_id(session, telegram_id)
        if user:
            # Update latest username/names if changed
            user = await self.user_repo.update(
                session,
                user,
                username=username or user.username,
                first_name=first_name or user.first_name,
                last_name=last_name or user.last_name,
            )
            return user

        user = await self.user_repo.create(
            session,
            telegram_id=telegram_id,
            language=language,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        return user

    async def complete_registration(
        self,
        session: AsyncSession,
        *,
        telegram_id: int,
        phone: str,
        is_verified: bool,
        first_name: str | None = None,
        language: str | None = None,
    ) -> User:
        """Finalize user registration: normalize phone, record consent, and assign default role."""
        normalized_phone = normalize_phone_number(phone)
        if not normalized_phone:
            raise UyAIError("Invalid phone number format.")

        user = await self.user_repo.get_by_telegram_id(session, telegram_id)
        if not user:
            user = await self.user_repo.create(
                session,
                telegram_id=telegram_id,
                language=language or "uz",
                first_name=first_name,
                phone=normalized_phone,
                is_verified=is_verified,
                consent_accepted_at=datetime.now(UTC),
            )
        else:
            update_data: dict[str, object] = {
                "phone": normalized_phone,
                "is_verified": is_verified,
                "consent_accepted_at": datetime.now(UTC),
            }
            if first_name:
                update_data["first_name"] = first_name
            if language:
                update_data["language"] = language
            user = await self.user_repo.update(session, user, **update_data)

        # Assign default customer role (buyer)
        await self.role_repo.assign_role(session, user.id, DEFAULT_CUSTOMER_ROLE)
        logger.info("User registration completed for telegram_id=%d", telegram_id)
        return user

    async def update_language(
        self, session: AsyncSession, telegram_id: int, language: str
    ) -> User | None:
        """Update language preference for user."""
        if language not in ("uz", "ru"):
            raise UyAIError(f"Unsupported language code '{language}'.")

        user = await self.user_repo.get_by_telegram_id(session, telegram_id)
        if user:
            user = await self.user_repo.update(session, user, language=language)
        return user

    async def assign_role_safely(
        self, session: AsyncSession, user_id: int, role_name: str, requested_by_admin: bool = False
    ) -> bool:
        """Assign role with security guards against unauthorized privileged self-assignment.

        Privileged roles (superadmin, head_broker, sales_broker, etc.) CANNOT be assigned
        unless explicitly flagged as an admin action.
        """
        if role_name not in SYSTEM_ROLES:
            raise UyAIError(f"Role '{role_name}' is not a recognized system role.")

        if role_name != DEFAULT_CUSTOMER_ROLE and not requested_by_admin:
            logger.warning(
                "Unauthorized attempt to assign privileged role '%s' to user_id=%d",
                role_name,
                user_id,
            )
            return False

        assignment = await self.role_repo.assign_role(session, user_id, role_name)
        return assignment is not None
