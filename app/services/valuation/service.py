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
            param_desc = (
                f"{input_data.district}, {input_data.rooms} xona, {input_data.total_area} m²"
            )
            if input_data.floor and input_data.total_floors:
                param_desc += f", {input_data.floor}/{input_data.total_floors}-qavat"

            if language == "ru":
                return ValuationExplanation(
                    summary=(
                        f"По параметрам объекта ({param_desc}) в базе данных и рыночной статистике "
                        "пока недостаточно данных для точной оценки."
                    ),
                    positive_factors=[],
                    negative_factors=["Недостаточное количество активных аналогов на рынке"],
                    missing_information=[
                        f"Близкие аналоги по площади ({input_data.total_area} м²) и локации",
                        "Региональная статистика цен",
                    ],
                    recommendation=(
                        "Рекомендуем уточнить параметры поиска или обратиться напрямую к брокеру."
                    ),
                )
            return ValuationExplanation(
                summary=(
                    f"Kiritilgan parametrlar ({param_desc}) bo‘yicha "
                    "bazada va bozor statistikasida aniq baholash uchun ma'lumotlar yetarli emas."
                ),
                positive_factors=[],
                negative_factors=["Bozorda o‘xshash faol e'lonlar sonining kamligi"],
                missing_information=[
                    f"Maydon ({input_data.total_area} m²) va qavat bo‘yicha yaqin faol e'lonlar",
                    "Hududiy bozor narx statistikasi",
                ],
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
            if result.valuation_method == "market_benchmark":
                method_desc = f"официальной рыночной статистике по району {input_data.district}"
            elif result.valuation_method == "district_stats":
                method_desc = (
                    f"статистике {result.sample_size} объявлений района {input_data.district}"
                )
            elif result.valuation_method == "regional_stats":
                method_desc = (
                    f"статистике {result.sample_size} объявлений региона {input_data.region}"
                )
            else:
                tier_desc = (
                    f"в районе {input_data.district}"
                    if result.comparison_tier in (1, 2)
                    else f"в регионе {input_data.region}"
                )
                method_desc = f"{result.comparable_count} аналогов {tier_desc}"

            factors_extra = [
                f
                for f in result.factors
                if any(k in f for k in ("omili", "ta'siri", "qulayligi", "likvidligi"))
            ]
            return ValuationExplanation(
                summary=(
                    f"Расчет выполнен на основе {method_desc}. "
                    f"Диапазон: {range_str}. Достоверность: {result.confidence}."
                ),
                positive_factors=[
                    f"Локация: {input_data.district}",
                    f"Количество комнат: {input_data.rooms}",
                ] + factors_extra,
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

        if result.valuation_method == "market_benchmark":
            method_desc = (
                f"{input_data.district} tumani bo‘yicha rasmiy bozor statistikasi ma'lumotlariga"
            )
        elif result.valuation_method == "district_stats":
            method_desc = (
                f"{input_data.district} tumanidagi {result.sample_size} ta "
                "e'lon statistikasi ma'lumotlariga"
            )
        elif result.valuation_method == "regional_stats":
            method_desc = (
                f"{input_data.region} hududidagi {result.sample_size} ta "
                "e'lon statistikasi ma'lumotlariga"
            )
        else:
            tier_desc = (
                f"{input_data.district} tumani"
                if result.comparison_tier in (1, 2)
                else f"{input_data.region} hududi"
            )
            method_desc = f"{tier_desc} bo‘yicha {result.comparable_count} ta o‘xshash e'longa"

        factors_extra = [
            f
            for f in result.factors
            if any(k in f for k in ("omili", "ta'siri", "qulayligi", "likvidligi"))
        ]
        return ValuationExplanation(
            summary=(
                f"Baholash {method_desc} "
                f"asoslandi. Bozor oralig‘i: {range_str}. Ishonchlilik: {result.confidence}."
            ),
            positive_factors=[
                f"Joylashuv: {input_data.district}",
                f"Xonalar soni: {input_data.rooms} xona",
            ] + factors_extra,
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
        """Perform end-to-end multi-method valuation of property.

        Cascade:
        Method A: Direct matching approved comparable listings (Tier 1-3).
        Method B: Database district or regional empirical price/m² statistics.
        Method C: Authoritative district-level benchmark statistics (Tashkent City).
        Method D: Insufficient data handling (no synthetic hallucinated prices).
        """
        # Step 1: Discover approved direct comparables
        comparables, tier = await self.comparable_service.find_comparables(session, input_data)

        # Step 2: Deterministic numeric valuation using direct comparables
        result = self.engine.calculate(input_data, comparables, tier)

        # Step 3: Multi-method fallback cascade when direct comparables are insufficient
        if result.insufficient_data:
            # Stage B: Database district or regional empirical price/m² statistics
            stat_m2, sample_count, stat_method = (
                await self.comparable_service.get_database_statistics(session, input_data)
            )
            if stat_m2 is not None and sample_count >= 2:
                source_desc = (
                    f"Bazada tasdiqlangan {sample_count} ta {input_data.district} "
                    "tumani e'lonlari statistikasi"
                    if stat_method == "district_stats"
                    else f"Bazada tasdiqlangan {sample_count} ta {input_data.region} "
                    "hududiy e'lonlari statistikasi"
                )
                result = self.engine.calculate_from_statistics(
                    input_data=input_data,
                    median_price_per_m2=stat_m2,
                    sample_size=sample_count,
                    valuation_method=stat_method,
                    source_description=source_desc,
                )
            else:
                # Stage C: Authoritative district-level benchmark statistics (Tashkent City)
                from app.services.valuation.district_benchmarks import (
                    get_district_market_benchmark,
                )

                bench_m2, bench_desc = get_district_market_benchmark(
                    district=input_data.district,
                    region=input_data.region,
                    listing_type=input_data.listing_type,
                    property_type=input_data.property_type,
                    currency=input_data.currency,
                )
                if bench_m2 is not None:
                    result = self.engine.calculate_from_statistics(
                        input_data=input_data,
                        median_price_per_m2=bench_m2,
                        sample_size=15,
                        valuation_method="market_benchmark",
                        source_description=bench_desc
                        or f"{input_data.district} tumani bozor statistikasi",
                    )
                else:
                    # Stage D: Truly insufficient data -> Do NOT invent fake prices
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
                valuation_method=result.valuation_method,
                source_description=result.source_description,
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
