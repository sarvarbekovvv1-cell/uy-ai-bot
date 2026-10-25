"""Deterministic real estate valuation engine for UyAI."""

import math
from decimal import ROUND_HALF_UP, Decimal

from app.models.property import Property
from app.schemas.valuation import (
    PropertyValuationInput,
    PropertyValuationResult,
    SafeComparableProperty,
)
from app.services.valuation.config import (
    CONDITION_ADJUSTMENTS,
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_MEDIUM_THRESHOLD,
    IQR_MULTIPLIER,
    MIN_COMPARABLES_REQUIRED,
    OUTLIER_MIN_SAMPLE_SIZE,
    RANGE_PERCENT_HIGH,
    RANGE_PERCENT_LOW,
    RANGE_PERCENT_MEDIUM,
    TOP_COMPARABLES_RETURN_LIMIT,
)


class ValuationEngine:
    """Authoritative deterministic calculator for property valuation ranges.

    CRITICAL SECURITY & INTEGRITY RULE:
    Authoritative prices are NEVER generated or altered by LLM/Gemini.
    All mathematical calculations use strictly Decimal arithmetic.
    """

    @staticmethod
    def round_price(val: Decimal, currency: str, is_rent: bool = False) -> Decimal:
        """Deterministically round valuation figures to clean market intervals."""
        if val <= Decimal("0"):
            return Decimal("0")

        if currency == "USD":
            if is_rent or val < Decimal("10000"):
                # Round to nearest 50
                step = Decimal("50")
            elif val >= Decimal("50000"):
                # Round to nearest 1,000
                step = Decimal("1000")
            else:
                # Round to nearest 500
                step = Decimal("500")
            units = (val / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            return units * step

        # UZS rounding
        if is_rent or val < Decimal("10000000"):  # 10M UZS
            step = Decimal("100000")  # nearest 100k
        elif val >= Decimal("100000000"):  # 100M UZS
            step = Decimal("1000000")  # nearest 1M
        else:
            step = Decimal("500000")  # nearest 500k

        units = (val / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return units * step

    @staticmethod
    def compute_median(values: list[Decimal]) -> Decimal:
        """Compute the exact median of a list of Decimal values."""
        if not values:
            return Decimal("0")
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        mid = n // 2
        if n % 2 == 1:
            return sorted_vals[mid]
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / Decimal("2")

    @classmethod
    def filter_outliers(
        cls,
        items: list[tuple[Property, Decimal, float]],
    ) -> list[tuple[Property, Decimal, float]]:
        """Filter price per m² outliers using the Interquartile Range (IQR) method.

        Requires at least OUTLIER_MIN_SAMPLE_SIZE samples before trimming.
        """
        if len(items) < OUTLIER_MIN_SAMPLE_SIZE:
            return items

        # Sort by price_per_m2
        sorted_items = sorted(items, key=lambda x: x[1])
        prices = [x[1] for x in sorted_items]
        n = len(prices)

        # Approximate 25th and 75th percentiles
        q1_idx = int(math.floor(0.25 * (n - 1)))
        q3_idx = int(math.ceil(0.75 * (n - 1)))
        q1 = prices[q1_idx]
        q3 = prices[q3_idx]
        iqr = q3 - q1

        lower_bound = q1 - (IQR_MULTIPLIER * iqr)
        upper_bound = q3 + (IQR_MULTIPLIER * iqr)

        filtered = [item for item in sorted_items if lower_bound <= item[1] <= upper_bound]

        # Prevent over-filtering
        if len(filtered) < 2:
            return items
        return filtered

    def calculate(
        self,
        input_data: PropertyValuationInput,
        comparables: list[tuple[Property, float]],
        tier: int,
    ) -> PropertyValuationResult:
        """Calculate authoritative valuation range based on approved comparables."""
        currency = input_data.currency
        is_rent = input_data.listing_type == "rent"

        # Sanitize and extract price_per_m2
        valid_items: list[tuple[Property, Decimal, float]] = []
        for prop, sim in comparables:
            if prop.status != "approved":
                continue
            if prop.currency != currency:
                continue
            if prop.listing_type != input_data.listing_type:
                continue
            if prop.price <= Decimal("0") or prop.total_area <= Decimal("0"):
                continue
            if input_data.property_id and prop.id == input_data.property_id:
                continue

            price_m2 = prop.price / prop.total_area
            valid_items.append((prop, price_m2, sim))

        # Check evidence threshold
        if len(valid_items) < MIN_COMPARABLES_REQUIRED:
            return PropertyValuationResult(
                estimated_price=None,
                estimated_min_price=None,
                estimated_max_price=None,
                currency=currency,
                confidence="low",
                comparable_count=len(valid_items),
                median_price_per_m2=None,
                comparison_tier=tier,
                factors=["Yetarli taqqoslama e'lonlar mavjud emas."],
                warnings=[
                    "Bozor tahlili uchun kamida 2 ta tasdiqlangan o‘xshash e'lon talab qilinadi."
                ],
                insufficient_data=True,
                comparable_properties=[],
            )

        # Apply robust outlier filtering
        clean_items = self.filter_outliers(valid_items)

        # Compute price metrics
        clean_prices_m2 = [item[1] for item in clean_items]
        clean_total_prices = [item[0].price for item in clean_items]
        count = len(clean_items)

        # ---------------------------------------------------------
        # ADVERSARIAL DISPERSION & TWO-COMPARABLE CHECKS
        # ---------------------------------------------------------
        min_p_m2 = min(clean_prices_m2)
        max_p_m2 = max(clean_prices_m2)
        warnings: list[str] = []
        factors: list[str] = []

        # Extreme disagreement between 2 comparables (e.g. $50k vs $150k)
        if count == 2 and min_p_m2 > Decimal("0"):
            dispersion_ratio = max_p_m2 / min_p_m2
            if dispersion_ratio >= Decimal("2.0"):
                return PropertyValuationResult(
                    estimated_price=None,
                    estimated_min_price=None,
                    estimated_max_price=None,
                    currency=currency,
                    confidence="low",
                    comparable_count=count,
                    median_price_per_m2=None,
                    comparison_tier=tier,
                    factors=["Mavjud taqqoslama e'lonlar o‘rtasida o‘ta yuqori tafovut aniqlandi."],
                    warnings=[
                        "Mavjud 2 ta e'lon narxlari o‘rtasida keskin farq (2 barobardan ortiq) "
                        "mavjudligi sababli ishonchli baholash imkonsiz."
                    ],
                    insufficient_data=True,
                    comparable_properties=[],
                )
            if dispersion_ratio >= Decimal("1.4"):
                warnings.append(
                    "Taqqoslama 2 ta e'lon narxlari o‘rtasida sezilarli tafovut mavjud."
                )

        median_m2 = self.compute_median(clean_prices_m2)

        # ---------------------------------------------------------
        # SALE VS RENTAL VALUATION ALGORITHM
        # ---------------------------------------------------------
        if is_rent:
            # Rental economics: utility and room capacity drive rent with diminishing area returns
            median_monthly_rent = self.compute_median(clean_total_prices)
            # Area-adjusted hybrid model: 50% unit median rent + 50% area-based rent
            linear_rent = median_m2 * input_data.total_area
            base_estimate = (median_monthly_rent * Decimal("0.5")) + (linear_rent * Decimal("0.5"))
            factors.append(
                "Ijara baholash: xonalar soni va maydon mutanosibligi asosida hisoblandi."
            )
        else:
            # Sale economics: market price per square meter
            base_estimate = median_m2 * input_data.total_area

        # Apply conservative condition adjustment
        if input_data.condition and input_data.condition in CONDITION_ADJUSTMENTS:
            adj = CONDITION_ADJUSTMENTS[input_data.condition]
            base_estimate = base_estimate * (Decimal("1") + adj)
            pct = int(adj * 100)
            sign = "+" if pct > 0 else ""
            factors.append(f"Mulk holati ({input_data.condition}) hisobga olindi: {sign}{pct}%")

        # ---------------------------------------------------------
        # MULTI-FACTOR CONFIDENCE CLASSIFICATION
        # ---------------------------------------------------------
        if tier == 3:
            confidence = "low"
            warnings.append(
                "Tuman miqyosida e'lonlar yetarli bo‘lmagani sababli hudud/shahar miqyosidagi "
                "o‘xshash e'lonlar tahlil qilindi."
            )
        elif count >= CONFIDENCE_HIGH_THRESHOLD:
            confidence = "high"
        elif count >= CONFIDENCE_MEDIUM_THRESHOLD:
            confidence = "medium"
        else:
            confidence = "low"
            warnings.append(
                "Taqqoslama e'lonlar soni kamligi sababli baholash oraliq aniqligi pastroq."
            )

        # Penalize high price dispersion across comparables
        if median_m2 > Decimal("0"):
            relative_dispersion = (max_p_m2 - min_p_m2) / median_m2
            if relative_dispersion > Decimal("0.70"):
                if confidence != "low":
                    warnings.append(
                        "Taqqoslama e'lonlar narxlarida o‘ta yuqori tarqoqlik (dispersiya) mavjud."
                    )
                confidence = "low"
            elif relative_dispersion > Decimal("0.45"):
                if confidence == "high":
                    confidence = "medium"
                    warnings.append(
                        "Taqqoslama e'lonlar narxlarida sezilarli tarqoqlik kuzatildi."
                    )

        # Property type heterogeneity check: Houses vary widely by plot and construction
        if input_data.property_type == "house":
            if confidence == "high":
                confidence = "medium"
            warnings.append(
                "Hovli/uchastka mulklari yer maydoni va holatiga qarab keng narx oralig‘iga ega."
            )

        # Range spread around central estimate
        if confidence == "high":
            spread = RANGE_PERCENT_HIGH
        elif confidence == "medium":
            spread = RANGE_PERCENT_MEDIUM
        else:
            spread = RANGE_PERCENT_LOW

        min_val = base_estimate * (Decimal("1") - spread)
        max_val = base_estimate * (Decimal("1") + spread)

        # Deterministic rounding
        rounded_est = self.round_price(base_estimate, currency, is_rent=is_rent)
        rounded_min = self.round_price(min_val, currency, is_rent=is_rent)
        rounded_max = self.round_price(max_val, currency, is_rent=is_rent)

        # Guarantee range ordering: min <= est <= max
        if rounded_min > rounded_est:
            rounded_min = rounded_est
        if rounded_max < rounded_est:
            rounded_max = rounded_est

        # Build factors summary
        factors.append(f"{count} ta tasdiqlangan o‘xshash e'lon tahlil qilindi.")
        factors.append(f"Median narx: {median_m2.quantize(Decimal('0.01'))} {currency}/m²")
        if tier == 1:
            factors.append(f"{input_data.district} tumani bo‘yicha to‘g‘ridan-to‘g‘ri moslik.")
        elif tier == 2:
            factors.append(f"{input_data.district} tumani bo‘yicha kengaytirilgan qidiruv.")

        # Build safe comparable objects
        clean_items.sort(key=lambda x: x[2], reverse=True)
        safe_comps: list[SafeComparableProperty] = []
        for prop, p_m2, sim in clean_items[:TOP_COMPARABLES_RETURN_LIMIT]:
            safe_comps.append(
                SafeComparableProperty(
                    id=prop.id,
                    title=prop.title or f"{prop.rooms} xonali {prop.property_type}",
                    district=prop.district,
                    region=prop.region,
                    rooms=prop.rooms,
                    total_area=prop.total_area,
                    price=prop.price,
                    currency=prop.currency,
                    price_per_m2=p_m2.quantize(Decimal("0.01")),
                    condition=prop.condition,
                    floor=prop.floor,
                    total_floors=prop.total_floors,
                    similarity_score=round(sim, 2),
                )
            )

        return PropertyValuationResult(
            estimated_price=rounded_est,
            estimated_min_price=rounded_min,
            estimated_max_price=rounded_max,
            currency=currency,
            confidence=confidence,
            comparable_count=count,
            median_price_per_m2=median_m2.quantize(Decimal("0.01")),
            comparison_tier=tier,
            factors=factors,
            warnings=warnings,
            insufficient_data=False,
            comparable_properties=safe_comps,
        )
