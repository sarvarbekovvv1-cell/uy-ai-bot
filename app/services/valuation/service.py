"""Master orchestration service for UyAI Property Valuation."""

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.logging import get_logger
from app.schemas.valuation import (
    PropertyValuationInput,
    PropertyValuationResult,
    ValuationExplanation,
    ValuationSafeContext,
)
from app.services.valuation.comparable_service import ComparablePropertyService
from app.services.valuation.engine import ValuationEngine

if TYPE_CHECKING:
    from app.ai.interfaces import LLMProvider

logger = get_logger(__name__)


class ValuationService:
    """Orchestrates deterministic property valuation with optional AI explanation.

    CRITICAL ARCHITECTURAL CONTRACT:
    1. Valuation numbers (min, max, central, price/m2, confidence) are computed
       exclusively by the deterministic ValuationEngine.
    2. LLM/Gemini is strictly restricted to generating narrative explanations.
    3. If LLM/Gemini fails or times out, the valuation STILL SUCCEEDS with a
       localized template fallback.
    """

    def __init__(
        self,
        comparable_service: ComparablePropertyService | None = None,
        engine: ValuationEngine | None = None,
        llm_provider: "LLMProvider | None" = None,
    ) -> None:
        self.comparable_service = comparable_service or ComparablePropertyService()
        self.engine = engine or ValuationEngine()
        self.llm_provider = llm_provider

    @staticmethod
    def format_money(val: Decimal | None, currency: str) -> str:
        """Format money amount with thousands separator and currency."""
        if val is None:
            return "N/A"
        formatted_num = f"{int(val):,}".replace(",", " ")
        if currency == "USD":
            return f"${formatted_num}"
        return f"{formatted_num} {currency}"

    def build_fallback_explanation(
        self,
        input_data: PropertyValuationInput,
        result: PropertyValuationResult,
        language: str = "uz",
    ) -> ValuationExplanation:
        """Construct deterministic, localized fallback explanation when LLM is unavailable."""
        if result.insufficient_data:
            if language == "ru":
                return ValuationExplanation(
                    summary=(
                        f"Недостаточно данных для оценки объекта в районе {input_data.district}. "
                        "В базе найдено менее 2 одобренных аналогичных объявлений."
                    ),
                    positive_factors=[],
                    negative_factors=["Отсутствие достаточного количества активных аналогов"],
                    missing_information=[
                        "Активные объявления со схожими параметрами площади и комнатности"
                    ],
                    recommendation=(
                        "Рекомендуем уточнить параметры поиска или обратиться напрямую к брокеру."
                    ),
                )
            return ValuationExplanation(
                summary=(
                    f"{input_data.district} tumani bo‘yicha baholash uchun tasdiqlangan "
                    "o‘xshash e'lonlar yetarli emas (kamida 2 ta e'lon zarur)."
                ),
                positive_factors=[],
                negative_factors=["Bozorda o‘xshash faol e'lonlar sonining kamligi"],
                missing_information=["Maydon va xonalar soni bo‘yicha yaqin faol e'lonlar"],
                recommendation=(
                    "Parametrlarni kengaytirish yoki mutaxassis broker bilan maslahatlashish "
                    "tavsiya etiladi."
                ),
            )

        range_str = (
            f"{self.format_money(result.estimated_min_price, result.currency)} – "
            f"{self.format_money(result.estimated_max_price, result.currency)}"
        )

        if language == "ru":
            tier_desc = (
                f"в районе {input_data.district}"
                if result.comparison_tier in (1, 2)
                else f"в регионе {input_data.region}"
            )
            return ValuationExplanation(
                summary=(
                    f"Расчет выполнен на основе {result.comparable_count} аналогов {tier_desc}. "
                    f"Диапазон: {range_str}. Достоверность: {result.confidence}."
                ),
                positive_factors=[
                    f"Локация: {input_data.district}",
                    f"Количество комнат: {input_data.rooms}",
                ],
                negative_factors=[
                    "Рыночные колебания и индивидуальные особенности объекта",
                ],
                missing_information=[
                    "Точный этаж, вид из окна и качество отделки",
                ],
                recommendation=(
                    "Используйте данный диапазон как стартовый ориентир для переговоров."
                ),
            )

        tier_desc = (
            f"{input_data.district} tumani"
            if result.comparison_tier in (1, 2)
            else f"{input_data.region} hududi"
        )
        return ValuationExplanation(
            summary=(
                f"Baholash {tier_desc} bo‘yicha {result.comparable_count} ta o‘xshash e'longa "
                f"asoslandi. Bozor oralig‘i: {range_str}. Ishonchlilik: {result.confidence}."
            ),
            positive_factors=[
                f"Joylashuv: {input_data.district}",
                f"Xonalar soni: {input_data.rooms} xona",
            ],
            negative_factors=[
                "Bozor narxlarining mavsumiy tebranishlari",
            ],
            missing_information=[
                "Mulkning ichki holati, derazadan ko‘rinish va binoning aniq joylashuvi",
            ],
            recommendation=(
                "Ushbu narx oralig‘ini savdolashuvda dastlabki mo‘ljal sifatida qo‘llash "
                "tavsiya etiladi."
            ),
        )

    async def valuate_property(
        self,
        session: AsyncSession,
        input_data: PropertyValuationInput,
        language: str = "uz",
    ) -> PropertyValuationResult:
        """Perform end-to-end valuation of property."""
        # Step 1: Discover approved comparables
        comparables, tier = await self.comparable_service.find_comparables(session, input_data)

        # Step 2: Deterministic numeric valuation
        result = self.engine.calculate(input_data, comparables, tier)

        # Step 3: Handle insufficient data
        if result.insufficient_data:
            result.explanation = self.build_fallback_explanation(
                input_data, result, language=language
            )
            return result

        # Step 4: Optional AI narrative explanation
        if self.llm_provider:
            range_str = (
                f"{self.format_money(result.estimated_min_price, result.currency)} – "
                f"{self.format_money(result.estimated_max_price, result.currency)}"
            )
            central_str = self.format_money(result.estimated_price, result.currency)
            m2_str = (
                f"{result.median_price_per_m2} {result.currency}/m²"
                if result.median_price_per_m2
                else None
            )

            safe_context = ValuationSafeContext(
                listing_type=input_data.listing_type,
                property_type=input_data.property_type,
                region=input_data.region,
                district=input_data.district,
                rooms=input_data.rooms,
                total_area=input_data.total_area,
                condition=input_data.condition,
                floor=input_data.floor,
                total_floors=input_data.total_floors,
                currency=input_data.currency,
                estimated_price_range_str=range_str,
                central_price_str=central_str,
                median_price_per_m2_str=m2_str,
                confidence=result.confidence,
                comparable_count=result.comparable_count,
                comparison_tier=result.comparison_tier,
                factors=result.factors,
                warnings=result.warnings,
            )

            try:
                explanation = await self.llm_provider.explain_valuation(
                    safe_context,
                    language=language,
                )
                result.explanation = explanation
            except Exception as e:
                logger.warning(
                    "LLM valuation explanation failed (%s), fallback used",
                    type(e).__name__,
                )
                result.explanation = self.build_fallback_explanation(
                    input_data, result, language=language
                )
        else:
            result.explanation = self.build_fallback_explanation(
                input_data, result, language=language
            )

        return result
