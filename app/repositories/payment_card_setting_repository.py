"""Repository for managing payment card and pricing tier settings."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.payment_card_setting import PaymentCardSetting


class PaymentCardSettingRepository:
    """Provides atomic retrieval and updates for P2P card monetization configuration."""

    async def get_setting(self, session: AsyncSession) -> PaymentCardSetting:
        """Get the payment card setting, creating default row from config if none exists."""
        stmt = select(PaymentCardSetting).order_by(PaymentCardSetting.id.asc()).limit(1)
        res = await session.execute(stmt)
        setting = res.scalar_one_or_none()

        if not setting:
            config = get_settings()
            card_num = config.valuation_card_number or ""
            card_hld = config.valuation_cardholder or ""
            basic_p = Decimal(str(config.valuation_price_basic_uzs or 50000))
            std_p = Decimal(str(config.valuation_price_standard_uzs or 65000))
            prem_p = Decimal(str(config.valuation_price_premium_uzs or 90000))

            setting = PaymentCardSetting(
                card_number=card_num,
                card_holder=card_hld,
                basic_price_uzs=basic_p,
                standard_price_uzs=std_p,
                premium_price_uzs=prem_p,
                is_active=bool(card_num and card_hld),
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
        basic_price_uzs: Decimal | None = None,
        standard_price_uzs: Decimal | None = None,
        premium_price_uzs: Decimal | None = None,
        is_active: bool | None = None,
    ) -> PaymentCardSetting:
        """Update payment card settings and pricing tiers."""
        setting = await self.get_setting(session)

        if card_number is not None:
            setting.card_number = card_number.strip()
        if card_holder is not None:
            setting.card_holder = card_holder.strip()
        if basic_price_uzs is not None:
            setting.basic_price_uzs = basic_price_uzs
        if standard_price_uzs is not None:
            setting.standard_price_uzs = standard_price_uzs
        if premium_price_uzs is not None:
            setting.premium_price_uzs = premium_price_uzs
        if is_active is not None:
            setting.is_active = is_active

        await session.flush()
        await session.refresh(setting)
        return setting
