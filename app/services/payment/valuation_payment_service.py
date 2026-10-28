"""High-level orchestration service for monetized property valuations."""

from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.logging import get_logger
from app.models.valuation_order import ValuationOrder
from app.repositories.valuation_order_repository import ValuationOrderRepository
from app.schemas.valuation import PropertyValuationInput, PropertyValuationResult
from app.services.payment.click_service import ClickPaymentService
from app.services.payment.payme_service import PaymePaymentService
from app.services.valuation.service import ValuationService

logger = get_logger(__name__)


class ValuationPaymentService:
    """Coordinates pricing, order creation, payment link generation, and fulfillment."""

    def __init__(
        self,
        settings: Settings | None = None,
        order_repo: ValuationOrderRepository | None = None,
        valuation_service: ValuationService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.order_repo = order_repo or ValuationOrderRepository()
        self.valuation_service = valuation_service
        self.click_service = ClickPaymentService(self.settings)
        self.payme_service = PaymePaymentService(self.settings)

    def get_service_price(self) -> Decimal:
        """Return configured valuation service price in UZS."""
        return Decimal(self.settings.valuation_price_uzs)

    def is_service_ready(self) -> bool:
        """Verify whether pricing and at least one payment provider are configured."""
        price_valid = self.get_service_price() > Decimal("0")
        provider_ready = self.click_service.is_configured() or self.payme_service.is_configured()
        return price_valid and provider_ready

    async def create_valuation_order(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        telegram_id: int,
        property_input: PropertyValuationInput,
    ) -> ValuationOrder:
        """Create a new valuation order with server-calculated price."""
        price_uzs = self.get_service_price()
        if price_uzs <= Decimal("0"):
            msg = "Valuation service price is not configured."
            raise ValueError(msg)

        input_dict = property_input.model_dump(mode="json")
        order = await self.order_repo.create_order(
            session,
            user_id=user_id,
            telegram_id=telegram_id,
            property_input=input_dict,
            amount_uzs=price_uzs,
            currency="UZS",
        )
        return order

    def get_payment_links(self, order: ValuationOrder) -> dict[str, str | None]:
        """Generate checkout links for all configured providers."""
        return {
            "click": self.click_service.generate_payment_url(order.order_id, order.amount_uzs),
            "payme": self.payme_service.generate_payment_url(order.order_id, order.amount_uzs),
        }

    async def fulfill_order_and_valuate(
        self,
        session: AsyncSession,
        order_id: str,
        *,
        bot: Any = None,
    ) -> PropertyValuationResult | None:
        """Execute property valuation for a verified paid order, record result, and notify user."""
        order = await self.order_repo.get_by_order_id(session, order_id)
        if not order:
            logger.error("Order %s not found for fulfillment", order_id)
            return None

        if order.payment_status != "paid":
            logger.warning("Attempted to fulfill unpaid order %s", order_id)
            return None

        if order.valuation_status == "completed" and order.valuation_result:
            logger.info("Order %s already completed, returning existing result", order_id)
            return PropertyValuationResult.model_validate(order.valuation_result)

        # Mark as processing
        await self.order_repo.set_valuation_result(
            session,
            order_id,
            valuation_status="processing",
        )

        # Execute valuation
        val_input = PropertyValuationInput.model_validate(order.property_input)
        val_service = self.valuation_service
        if val_service is None:
            from app.bot.handlers.valuation import get_valuation_service

            val_service = get_valuation_service()

        lang = "uz"
        if order.user and order.user.language:
            lang = order.user.language

        try:
            val_result = await val_service.valuate_property(
                session,
                val_input,
                language=lang,
            )
            result_dict = val_result.model_dump(mode="json")

            await self.order_repo.set_valuation_result(
                session,
                order_id,
                valuation_status="completed",
                valuation_result=result_dict,
            )

            # Proactively notify Telegram customer if bot instance is available
            if bot and order.telegram_id:
                try:
                    from app.bot.handlers.valuation import (
                        format_valuation_result_card,
                        get_valuation_actions_keyboard,
                    )

                    card_text = format_valuation_result_card(val_input, val_result, lang)
                    markup = get_valuation_actions_keyboard(
                        has_comps=bool(val_result.comparable_properties),
                        listing_type=val_input.listing_type,
                        lang=lang,
                    )
                    success_header = (
                        "✅ <b>To‘lov muvaffaqiyatli qabul qilindi!</b>\n\n"
                        if lang == "uz"
                        else (
                            "✅ <b>Оплата успешно принята!</b>\n\n"
                            if lang == "ru"
                            else "✅ <b>Payment successfully received!</b>\n\n"
                        )
                    )
                    await bot.send_message(
                        order.telegram_id,
                        f"{success_header}{card_text}",
                        reply_markup=markup,
                    )
                except Exception as notify_err:
                    logger.warning(
                        "Could not send proactive telegram valuation message: %s",
                        notify_err,
                    )

            return val_result

        except Exception as exc:
            logger.error("Valuation execution failed for order %s: %s", order_id, exc)
            await self.order_repo.set_valuation_result(
                session,
                order_id,
                valuation_status="failed",
                error_message=str(exc),
            )
            return None
