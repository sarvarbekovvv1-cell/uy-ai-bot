"""Centralized configuration constants for UyAI Property Valuation Engine."""

from decimal import Decimal

# Minimum comparable listings required for an authoritative estimate
MIN_COMPARABLES_REQUIRED: int = 2

# Confidence classification sample size thresholds
CONFIDENCE_LOW_THRESHOLD: int = 2
CONFIDENCE_MEDIUM_THRESHOLD: int = 4
CONFIDENCE_HIGH_THRESHOLD: int = 7

# Comparable matching tiers: Area tolerances
TIER1_AREA_TOLERANCE: Decimal = Decimal("0.20")  # ±20%
TIER2_AREA_TOLERANCE: Decimal = Decimal("0.35")  # ±35%
TIER3_AREA_TOLERANCE: Decimal = Decimal("0.40")  # ±40%

# Comparable matching tiers: Room count tolerances
TIER1_ROOM_TOLERANCE: int = 1  # ±1 room
TIER2_ROOM_TOLERANCE: int = 2  # ±2 rooms
TIER3_ROOM_TOLERANCE: int = 2  # ±2 rooms

# Database candidate query upper bound
MAX_CANDIDATES_FETCH: int = 50

# Maximum number of top comparable listings returned to the user
TOP_COMPARABLES_RETURN_LIMIT: int = 5

# Outlier detection minimum sample size
OUTLIER_MIN_SAMPLE_SIZE: int = 4
IQR_MULTIPLIER: Decimal = Decimal("1.5")

# Conservative condition adjustments relative to median
CONDITION_ADJUSTMENTS: dict[str, Decimal] = {
    "new": Decimal("0.04"),             # +4%
    "renovated": Decimal("0.03"),       # +3%
    "needs_renovation": Decimal("-0.05"),  # -5%
    "shell": Decimal("-0.08"),          # -8%
}

# Range spreads around central estimate based on confidence
RANGE_PERCENT_HIGH: Decimal = Decimal("0.06")     # ±6%
RANGE_PERCENT_MEDIUM: Decimal = Decimal("0.10")   # ±10%
RANGE_PERCENT_LOW: Decimal = Decimal("0.15")      # ±15%
