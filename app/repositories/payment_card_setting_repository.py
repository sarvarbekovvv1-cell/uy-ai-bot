"""Repository for managing payment card and pricing tier settings."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment_card_setting import PaymentCardSetting


class PaymentCardSettingRepository:
    """Provides atomic retrieval and updates for P2P card monetization configuration."""

    async def get_setting(self, session: AsyncSession) -> PaymentCardSetting:
        """Get the singleton payment card setting, creating default row if none exists."""
        stmt = select(PaymentCardSetting).order_by(PaymentCardSetting.id.asc()).limit(1)
        res = await session.execute(stmt)
        setting = res.scalar_one_or_none()

        if not setting:
            setting = PaymentCardSetting(
                card_number="9860 0000 0000 0000",
                card_holder="Sarvar Bekov",
                standard_price_uzs=Decimal("15000"),
                premium_price_uzs=Decimal("30000"),
                is_active=True,
            )
            session.add(setting)
            await session.flush()
            await session.refresh(setting)

        return setting

    async def update_setting(
        self,
        session: AsyncSession,
        *,
        card_number: str | None = None,
        card_holder: str | None = None,
        standard_price_uzs: Decimal | None = None,
        premium_price_uzs: Decimal | None = None,
        is_active: bool | None = None,
    ) -> PaymentCardSetting:
        """Update payment card settings."""
        setting = await self.get_setting(session)

        if card_number is not None:
            setting.card_number = card_number.strip()
        if card_holder is not None:
            setting.card_holder = card_holder.strip()
        if standard_price_uzs is not None:
            setting.standard_price_uzs = standard_price_uzs
        if premium_price_uzs is not None:
            setting.premium_price_uzs = premium_price_uzs
        if is_active is not None:
            setting.is_active = is_active

        await session.flush()
        await session.refresh(setting)
        return setting
