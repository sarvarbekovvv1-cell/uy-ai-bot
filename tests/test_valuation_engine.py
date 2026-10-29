"""Unit tests for deterministic ValuationEngine math, outliers, and rounding."""

from decimal import Decimal

from app.models.property import Property
from app.schemas.valuation import PropertyValuationInput
from app.services.valuation.engine import ValuationEngine


def create_mock_property(
    prop_id: int,
    price: Decimal,
    total_area: Decimal,
    rooms: int = 2,
    district: str = "Chilonzor",
    status: str = "approved",
    listing_type: str = "sale",
    currency: str = "USD",
    condition: str = "renovated",
) -> Property:
    """Helper to instantiate mock Property model for testing."""
    prop = Property(
        id=prop_id,
        owner_user_id=1,
        listing_type=listing_type,
        property_type="apartment",
        title=f"Property {prop_id}",
        region="Toshkent shahri",
        district=district,
        address=f"Street {prop_id}",
        rooms=rooms,
        total_area=total_area,
        condition=condition,
        price=price,
        currency=currency,
        status=status,
    )
    return prop


def test_zero_comparables_returns_insufficient_data() -> None:
    """Verify zero comparables produces insufficient_data without crashing."""
    engine = ValuationEngine()
    inp = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        total_area=Decimal("60"),
        rooms=2,
        currency="USD",
    )
    result = engine.calculate(inp, comparables=[], tier=1)

    assert result.insufficient_data is True
    assert result.estimated_price is None
    assert result.estimated_min_price is None
    assert result.estimated_max_price is None
    assert result.comparable_count == 0
    assert result.confidence == "low"
    assert len(result.warnings) > 0


def test_one_comparable_below_minimum_threshold() -> None:
    """Verify single comparable does not produce false confidence (below threshold of 2)."""
    engine = ValuationEngine()
    inp = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        total_area=Decimal("60"),
        rooms=2,
        currency="USD",
    )
    comp = create_mock_property(1, Decimal("90000"), Decimal("60"))
    result = engine.calculate(inp, comparables=[(comp, 1.0)], tier=1)

    assert result.insufficient_data is True
    assert result.estimated_price is None
    assert result.comparable_count == 1


def test_outlier_filtering_with_extreme_listing() -> None:
    """Verify extreme price outlier does not distort the central estimate.

    Prices per m2: 1700, 1750, 1800, 1780, 10000.
    10000 is an extreme outlier and must be removed by IQR filtering.
    """
    engine = ValuationEngine()
    inp = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        total_area=Decimal("50"),
        rooms=2,
        currency="USD",
    )
    comps = [
        (create_mock_property(1, Decimal("85000"), Decimal("50")), 0.95),  # 1700 / m2
        (create_mock_property(2, Decimal("87500"), Decimal("50")), 0.95),  # 1750 / m2
        (create_mock_property(3, Decimal("90000"), Decimal("50")), 0.95),  # 1800 / m2
        (create_mock_property(4, Decimal("89000"), Decimal("50")), 0.95),  # 1780 / m2
        (create_mock_property(5, Decimal("500000"), Decimal("50")), 0.95),  # 10000 / m2 (outlier!)
    ]

    result = engine.calculate(inp, comps, tier=1)

    assert result.insufficient_data is False
    assert result.comparable_count == 4  # 5th outlier was removed!
    # Expected median of [1700, 1750, 1780, 1800] = (1750 + 1780) / 2 = 1765 / m2
    assert result.median_price_per_m2 == Decimal("1765.00")
    # Base estimate for 50 m2 is 50 * 1765 = $88,250 -> rounded to nearest 1,000 = $88,000
    assert result.estimated_price is not None
    assert Decimal("85000") <= result.estimated_price <= Decimal("92000")
    # Crucially, the estimate is NOT distorted into the hundreds of thousands
    assert result.estimated_price < Decimal("100000")


def test_strictly_decimal_money_calculations() -> None:
    """Verify money calculations use Decimal and do not introduce binary float inaccuracies."""
    engine = ValuationEngine()
    inp = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        total_area=Decimal("70.33"),
        rooms=3,
        currency="USD",
    )
    comps = [
        (create_mock_property(1, Decimal("105500.50"), Decimal("70.33")), 1.0),
        (create_mock_property(2, Decimal("108000.75"), Decimal("70.33")), 1.0),
    ]

    result = engine.calculate(inp, comps, tier=1)
    assert isinstance(result.estimated_price, Decimal)
    assert isinstance(result.estimated_min_price, Decimal)
    assert isinstance(result.estimated_max_price, Decimal)
    assert isinstance(result.median_price_per_m2, Decimal)


def test_confidence_tiers_and_thresholds() -> None:
    """Verify confidence classification: low (2-3), medium (4-6), high (7+)."""
    engine = ValuationEngine()
    inp = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        total_area=Decimal("50"),
        rooms=2,
        currency="USD",
    )

    # 2 comps -> low confidence
    comps_2 = [
        (create_mock_property(1, Decimal("80000"), Decimal("50")), 1.0),
        (create_mock_property(2, Decimal("82000"), Decimal("50")), 1.0),
    ]
    res_2 = engine.calculate(inp, comps_2, tier=1)
    assert res_2.confidence == "low"

    # 4 comps -> medium confidence
    comps_4 = comps_2 + [
        (create_mock_property(3, Decimal("81000"), Decimal("50")), 1.0),
        (create_mock_property(4, Decimal("83000"), Decimal("50")), 1.0),
    ]
    res_4 = engine.calculate(inp, comps_4, tier=1)
    assert res_4.confidence == "medium"

    # 7 comps -> high confidence
    comps_7 = comps_4 + [
        (create_mock_property(5, Decimal("80500"), Decimal("50")), 1.0),
        (create_mock_property(6, Decimal("81500"), Decimal("50")), 1.0),
        (create_mock_property(7, Decimal("82500"), Decimal("50")), 1.0),
    ]
    res_7 = engine.calculate(inp, comps_7, tier=1)
    assert res_7.confidence == "high"


def test_tier_3_regional_fallback_caps_confidence_at_low() -> None:
    """Verify Tier 3 regional fallback caps confidence at 'low' and adds a warning."""
    engine = ValuationEngine()
    inp = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Bektemir",
        total_area=Decimal("50"),
        rooms=2,
        currency="USD",
    )
    # 7 comps from region
    comps_7 = [(create_mock_property(i, Decimal("70000"), Decimal("50")), 0.8) for i in range(1, 8)]
    res = engine.calculate(inp, comps_7, tier=3)

    assert res.confidence == "low"
    assert any("shahar" in w.lower() or "hudud" in w.lower() for w in res.warnings)


def test_condition_adjustments() -> None:
    """Verify condition adjustments (renovated +3%, needs_renovation -5%)."""
    engine = ValuationEngine()
    comps = [
        (create_mock_property(1, Decimal("100000"), Decimal("50")), 1.0),  # 2000/m2
        (create_mock_property(2, Decimal("100000"), Decimal("50")), 1.0),  # 2000/m2
    ]

    inp_renovated = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        total_area=Decimal("50"),
        rooms=2,
        condition="renovated",
        currency="USD",
    )
    res_renovated = engine.calculate(inp_renovated, comps, tier=1)

    inp_repair = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        total_area=Decimal("50"),
        rooms=2,
        condition="needs_renovation",
        currency="USD",
    )
    res_repair = engine.calculate(inp_repair, comps, tier=1)

    assert res_renovated.estimated_price is not None
    assert res_repair.estimated_price is not None
    assert res_renovated.estimated_price > res_repair.estimated_price


def test_deterministic_rounding_rules() -> None:
    """Verify deterministic rounding for USD sale, USD rent, and UZS."""
    # USD sale >= $50k rounded to nearest $1000
    res1 = ValuationEngine.round_price(Decimal("97438.27"), "USD", is_rent=False)
    assert res1 == Decimal("97000")
    res2 = ValuationEngine.round_price(Decimal("97650.00"), "USD", is_rent=False)
    assert res2 == Decimal("98000")

    # USD rent rounded to nearest $50
    assert ValuationEngine.round_price(Decimal("635"), "USD", is_rent=True) == Decimal("650")
    assert ValuationEngine.round_price(Decimal("610"), "USD", is_rent=True) == Decimal("600")

    # UZS >= 100M rounded to nearest 1M
    res_uzs1 = ValuationEngine.round_price(Decimal("123456789"), "UZS", is_rent=False)
    assert res_uzs1 == Decimal("123000000")
    res_uzs2 = ValuationEngine.round_price(Decimal("123600000"), "UZS", is_rent=False)
    assert res_uzs2 == Decimal("124000000")


def test_rental_valuation_calculation() -> None:
    """Verify rental valuation uses monthly rent per m2 with area adjustment."""
    engine = ValuationEngine()
    inp = PropertyValuationInput(
        listing_type="rent",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        total_area=Decimal("50"),
        rooms=2,
        currency="USD",
    )
    # Rent comparables: $500/month for 50m2 ($10/m2)
    comps = [
        (create_mock_property(1, Decimal("500"), Decimal("50"), listing_type="rent"), 1.0),
        (create_mock_property(2, Decimal("550"), Decimal("50"), listing_type="rent"), 1.0),
    ]

    result = engine.calculate(inp, comps, tier=1)
    assert result.insufficient_data is False
    assert result.estimated_price is not None
    # Median is $525 -> rounded to nearest $50 = $550 or $500
    assert Decimal("450") <= result.estimated_price <= Decimal("600")
    assert result.estimated_min_price <= result.estimated_price <= result.estimated_max_price


def test_two_comparable_extreme_disagreement_produces_insufficient_data() -> None:
    """Verify 2 comparables with extreme conflict (e.g. $50k vs $150k) return insufficient_data."""
    engine = ValuationEngine()
    inp = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        total_area=Decimal("50"),
        rooms=2,
        currency="USD",
    )
    comps = [
        (create_mock_property(1, Decimal("50000"), Decimal("50")), 1.0),  # 1000 / m2
        (create_mock_property(2, Decimal("150000"), Decimal("50")), 1.0),  # 3000 / m2 (ratio 3.0x!)
    ]
    result = engine.calculate(inp, comps, tier=1)

    assert result.insufficient_data is True
    assert result.estimated_price is None
    assert result.confidence == "low"
    assert any("farq" in w.lower() or "keskin" in w.lower() for w in result.warnings)


def test_two_comparable_moderate_disagreement_adds_warning() -> None:
    """Verify 2 comparables with moderate difference (1.5x) produce low confidence with warning."""
    engine = ValuationEngine()
    inp = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        total_area=Decimal("50"),
        rooms=2,
        currency="USD",
    )
    comps = [
        (create_mock_property(1, Decimal("50000"), Decimal("50")), 1.0),  # 1000 / m2
        (create_mock_property(2, Decimal("75000"), Decimal("50")), 1.0),  # 1500 / m2 (ratio 1.5x)
    ]
    result = engine.calculate(inp, comps, tier=1)

    assert result.insufficient_data is False
    assert result.confidence == "low"
    assert any("tafovut" in w.lower() for w in result.warnings)


def test_many_dispersed_comparables_cannot_produce_high_confidence() -> None:
    """Verify 7 comparables with extreme price dispersion cannot produce high confidence."""
    engine = ValuationEngine()
    inp = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        total_area=Decimal("50"),
        rooms=2,
        currency="USD",
    )
    # 7 comps with wild spread from $600/m2 to $3500/m2
    prices = [30000, 35000, 45000, 80000, 130000, 160000, 175000]
    comps = [
        (create_mock_property(i, Decimal(str(p)), Decimal("50")), 1.0)
        for i, p in enumerate(prices, start=1)
    ]
    result = engine.calculate(inp, comps, tier=1)

    assert result.insufficient_data is False
    # Despite 7 comparables, confidence must NOT be 'high' due to high dispersion!
    assert result.confidence in ("medium", "low")
    assert any("dispersiya" in w.lower() or "tarqoqlik" in w.lower() for w in result.warnings)


def test_house_valuation_caps_confidence_and_warns() -> None:
    """Verify private house valuation caps confidence at medium and adds heterogeneity warning."""
    engine = ValuationEngine()
    inp = PropertyValuationInput(
        listing_type="sale",
        property_type="house",
        region="Toshkent shahri",
        district="Yunusobod",
        total_area=Decimal("150"),
        rooms=5,
        currency="USD",
    )
    comps = [(create_mock_property(i, Decimal("150000"), Decimal("150")), 1.0) for i in range(1, 8)]
    result = engine.calculate(inp, comps, tier=1)

    assert result.insufficient_data is False
    # Even with 7 comps, house confidence is capped at 'medium'
    assert result.confidence == "medium"
    assert any("hovli" in w.lower() or "uchastka" in w.lower() for w in result.warnings)


def test_iqr_outliers_exact_sample_cases() -> None:
    """Verify exact adversarial sample sets for IQR outlier behavior."""
    engine = ValuationEngine()

    # Case 1: [1000, 1000, 1000, 1000, 10000] -> 10000 filtered
    items1 = [
        (create_mock_property(1, Decimal("50000"), Decimal("50")), Decimal("1000"), 1.0),
        (create_mock_property(2, Decimal("50000"), Decimal("50")), Decimal("1000"), 1.0),
        (create_mock_property(3, Decimal("50000"), Decimal("50")), Decimal("1000"), 1.0),
        (create_mock_property(4, Decimal("50000"), Decimal("50")), Decimal("1000"), 1.0),
        (create_mock_property(5, Decimal("500000"), Decimal("50")), Decimal("10000"), 1.0),
    ]
    filtered1 = engine.filter_outliers(items1)
    assert len(filtered1) == 4
    assert all(x[1] == Decimal("1000") for x in filtered1)

    # Case 2: [1000, 1100, 1200] -> sample count 3 < min 4 -> no trimming
    items2 = [
        (create_mock_property(1, Decimal("50000"), Decimal("50")), Decimal("1000"), 1.0),
        (create_mock_property(2, Decimal("55000"), Decimal("50")), Decimal("1100"), 1.0),
        (create_mock_property(3, Decimal("60000"), Decimal("50")), Decimal("1200"), 1.0),
    ]
    filtered2 = engine.filter_outliers(items2)
    assert len(filtered2) == 3


def test_calculate_from_statistics_floor_adjustments() -> None:
    """Verify statistical engine floor adjustments:

    - Middle floor (2/9): +2%
    - 1st floor (1/9): -4%
    - Top floor (9/9): -4%
    """
    engine = ValuationEngine()
    base_inp = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Yunusobod",
        total_area=Decimal("56"),
        rooms=2,
        condition="renovated",
        currency="USD",
    )

    # 1. Middle floor (2/9)
    inp_mid = base_inp.model_copy(update={"floor": 2, "total_floors": 9})
    res_mid = engine.calculate_from_statistics(
        input_data=inp_mid,
        median_price_per_m2=Decimal("1000"),
        sample_size=15,
        valuation_method="market_benchmark",
        source_description="Yunusobod tumani rasmiy bozor benchmarki",
    )
    assert res_mid.insufficient_data is False
    assert res_mid.estimated_price is not None
    # Base: 56 * 1000 = 56,000. Floor 2/9 gives +2%: 56,000 * 1.02 = 57,120 -> rounded: 57,000
    assert any("O‘rta qavat qulayligi (+2%)" in f for f in res_mid.factors)

    # 2. Ground floor (1/9)
    inp_ground = base_inp.model_copy(update={"floor": 1, "total_floors": 9})
    res_ground = engine.calculate_from_statistics(
        input_data=inp_ground,
        median_price_per_m2=Decimal("1000"),
        sample_size=15,
        valuation_method="market_benchmark",
        source_description="Yunusobod tumani rasmiy bozor benchmarki",
    )
    # Ground floor gives -4%
    assert any("Birinchi qavat omili (-4%)" in f for f in res_ground.factors)
    assert res_ground.estimated_price < res_mid.estimated_price

    # 3. Top floor (9/9)
    inp_top = base_inp.model_copy(update={"floor": 9, "total_floors": 9})
    res_top = engine.calculate_from_statistics(
        input_data=inp_top,
        median_price_per_m2=Decimal("1000"),
        sample_size=15,
        valuation_method="market_benchmark",
        source_description="Yunusobod tumani rasmiy bozor benchmarki",
    )
    # Top floor gives -4%
    assert any("Oxirgi qavat omili (-4%)" in f for f in res_top.factors)
    assert res_top.estimated_price < res_mid.estimated_price

