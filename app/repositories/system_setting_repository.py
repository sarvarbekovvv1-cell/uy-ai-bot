"""Repository for managing application-wide system settings in database."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.logging import get_logger
from app.models.system_setting import SystemSetting
from app.utils.phone import format_uzbek_phone, normalize_phone_number

logger = get_logger(__name__)

DEFAULT_BROKER_PHONE = "+998 71 200 00 00"
KEY_BROKER_PHONE = "broker_phone"


class SystemSettingRepository:
    """Provides atomic retrieval and updates for general system-level configuration."""

    async def get_setting_obj(
        self,
        session: AsyncSession,
        key: str,
    ) -> SystemSetting | None:
        """Fetch raw SystemSetting row by key."""
        stmt = select(SystemSetting).where(SystemSetting.key == key).limit(1)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_value(
        self,
        session: AsyncSession | None,
        key: str,
        default: str | None = None,
    ) -> str | None:
        """Get string setting value from database or fallback to default."""
        if session is None:
            return default

        try:
            stmt = select(SystemSetting.value).where(SystemSetting.key == key).limit(1)
            res = await session.execute(stmt)
            val = res.scalar_one_or_none()
            if val is not None and val.strip():
                return val.strip()
        except Exception as e:
            logger.warning(f"Error fetching system setting '{key}' from DB: {e}")

        return default

    async def set_value(
        self,
        session: AsyncSession,
        key: str,
        value: str,
        description: str | None = None,
    ) -> SystemSetting:
        """Upsert a system setting row."""
        stmt = select(SystemSetting).where(SystemSetting.key == key).limit(1)
        res = await session.execute(stmt)
        setting = res.scalar_one_or_none()

        now = datetime.now(UTC)
        if setting:
            setting.value = value
            if description is not None:
                setting.description = description
            setting.updated_at = now
        else:
            setting = SystemSetting(
                key=key,
                value=value,
                description=description,
                updated_at=now,
            )
            session.add(setting)

        await session.flush()
        return setting

    async def get_broker_phone(self, session: AsyncSession | None = None) -> str:
        """Get professional broker contact phone number.

        Checks database first; falls back to environment configuration or canonical default.
        Always returns a clean, human-readable formatted phone number (+998 XX XXX XX XX).
        """
        config = get_settings()
        fallback = getattr(config, "broker_phone", None) or DEFAULT_BROKER_PHONE

        db_val = await self.get_value(session, KEY_BROKER_PHONE, default=None)
        raw = db_val if db_val else fallback
        formatted = format_uzbek_phone(raw)
        return formatted or raw

    async def set_broker_phone(self, session: AsyncSession, raw_phone: str) -> str:
        """Validate, format, and save professional broker contact phone number.

        Raises ValueError if raw_phone cannot be parsed into a valid phone number.
        """
        cleaned = (raw_phone or "").strip()
        if not cleaned:
            raise ValueError("Telefon raqami bo'sh bo'lishi mumkin emas.")

        normalized = normalize_phone_number(cleaned)
        if not normalized:
            raise ValueError(
                "Telefon raqami formati noto'g'ri. Iltimos, haqiqiy telefon raqamini kiriting "
                "(masalan: +998 90 123 45 67 yoki +998 71 200 00 00)."
            )

        formatted = format_uzbek_phone(normalized) or normalized
        await self.set_value(
            session=session,
            key=KEY_BROKER_PHONE,
            value=formatted,
            description="Professional broker xizmati uchun aloqa telefoni",
        )
        return formatted
