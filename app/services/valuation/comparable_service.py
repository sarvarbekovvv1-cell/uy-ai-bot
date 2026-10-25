"""Service for discovering and ranking approved comparable properties."""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.property import Property
from app.schemas.valuation import PropertyValuationInput
from app.services.valuation.config import (
    MAX_CANDIDATES_FETCH,
    MIN_COMPARABLES_REQUIRED,
    TIER1_AREA_TOLERANCE,
    TIER1_ROOM_TOLERANCE,
    TIER2_AREA_TOLERANCE,
    TIER2_ROOM_TOLERANCE,
    TIER3_AREA_TOLERANCE,
    TIER3_ROOM_TOLERANCE,
)


class ComparablePropertyService:
    """Discovers and ranks customer-valid approved comparable property listings."""

    @staticmethod
    def calculate_similarity(subject: PropertyValuationInput, comp: Property) -> float:
        """Calculate deterministic similarity score between subject and comparable (0.0 to 1.0)."""
        area_diff = float(abs(comp.total_area - subject.total_area) / subject.total_area)
        room_diff = float(abs(comp.rooms - subject.rooms) * Decimal("0.1"))

        district_match = comp.district.strip().lower() == subject.district.strip().lower()
        district_penalty = 0.0 if district_match else 0.25

        condition_match = subject.condition and comp.condition == subject.condition
        condition_penalty = 0.0 if condition_match else 0.05

        penalty = area_diff + room_diff + district_penalty + condition_penalty
        return max(0.05, min(1.0, 1.0 - penalty))

    async def find_comparables(
        self,
        session: AsyncSession,
        subject: PropertyValuationInput,
    ) -> tuple[list[tuple[Property, float]], int]:
        """Find approved comparable listings through fallback tiers (Tier 1 -> Tier 2 -> Tier 3).

        CRITICAL SECURITY & INVENTORY RULES:
        1. Only Property.status == 'approved' listings are eligible.
        2. Draft, submitted, under_review, rejected, archived, sold, or rented properties
           are strictly excluded.
        3. Subject property itself is excluded if subject.property_id is specified.
        4. Listing types (sale vs rent) and currencies (USD vs UZS) are never mixed.
        """
        # Base filter conditions applied to all tiers
        base_conditions = [
            Property.status == "approved",
            Property.listing_type == subject.listing_type,
            Property.property_type == subject.property_type,
            Property.currency == subject.currency,
            Property.price > 0,
            Property.total_area > 0,
        ]

        if subject.property_id:
            base_conditions.append(Property.id != subject.property_id)

        # Tier 1: Exact district, narrow room & area tolerance
        tier1_conditions = list(base_conditions)
        if subject.region:
            tier1_conditions.append(
                func.lower(Property.region) == subject.region.strip().lower()
            )
        tier1_conditions.append(func.lower(Property.district) == subject.district.strip().lower())

        min_r1 = max(1, subject.rooms - TIER1_ROOM_TOLERANCE)
        max_r1 = subject.rooms + TIER1_ROOM_TOLERANCE
        tier1_conditions.append(Property.rooms >= min_r1)
        tier1_conditions.append(Property.rooms <= max_r1)

        min_a1 = subject.total_area * (Decimal("1") - TIER1_AREA_TOLERANCE)
        max_a1 = subject.total_area * (Decimal("1") + TIER1_AREA_TOLERANCE)
        tier1_conditions.append(Property.total_area >= min_a1)
        tier1_conditions.append(Property.total_area <= max_a1)

        stmt1 = (
            select(Property)
            .options(selectinload(Property.media))
            .where(*tier1_conditions)
            .limit(MAX_CANDIDATES_FETCH)
        )
        result1 = (await session.execute(stmt1)).scalars().all()
        if len(result1) >= MIN_COMPARABLES_REQUIRED:
            scored1 = [(p, self.calculate_similarity(subject, p)) for p in result1]
            return scored1, 1

        # Tier 2: Same district, wider room & area tolerance
        tier2_conditions = list(base_conditions)
        if subject.region:
            tier2_conditions.append(
                func.lower(Property.region) == subject.region.strip().lower()
            )
        tier2_conditions.append(func.lower(Property.district) == subject.district.strip().lower())

        min_r2 = max(1, subject.rooms - TIER2_ROOM_TOLERANCE)
        max_r2 = subject.rooms + TIER2_ROOM_TOLERANCE
        tier2_conditions.append(Property.rooms >= min_r2)
        tier2_conditions.append(Property.rooms <= max_r2)

        min_a2 = subject.total_area * (Decimal("1") - TIER2_AREA_TOLERANCE)
        max_a2 = subject.total_area * (Decimal("1") + TIER2_AREA_TOLERANCE)
        tier2_conditions.append(Property.total_area >= min_a2)
        tier2_conditions.append(Property.total_area <= max_a2)

        stmt2 = (
            select(Property)
            .options(selectinload(Property.media))
            .where(*tier2_conditions)
            .limit(MAX_CANDIDATES_FETCH)
        )
        result2 = (await session.execute(stmt2)).scalars().all()
        if len(result2) >= MIN_COMPARABLES_REQUIRED:
            scored2 = [(p, self.calculate_similarity(subject, p)) for p in result2]
            return scored2, 2

        # Tier 3: Same region, broader room & area tolerance
        tier3_conditions = list(base_conditions)
        if subject.region:
            tier3_conditions.append(
                func.lower(Property.region) == subject.region.strip().lower()
            )

        min_r3 = max(1, subject.rooms - TIER3_ROOM_TOLERANCE)
        max_r3 = subject.rooms + TIER3_ROOM_TOLERANCE
        tier3_conditions.append(Property.rooms >= min_r3)
        tier3_conditions.append(Property.rooms <= max_r3)

        min_a3 = subject.total_area * (Decimal("1") - TIER3_AREA_TOLERANCE)
        max_a3 = subject.total_area * (Decimal("1") + TIER3_AREA_TOLERANCE)
        tier3_conditions.append(Property.total_area >= min_a3)
        tier3_conditions.append(Property.total_area <= max_a3)

        stmt3 = (
            select(Property)
            .options(selectinload(Property.media))
            .where(*tier3_conditions)
            .limit(MAX_CANDIDATES_FETCH)
        )
        result3 = (await session.execute(stmt3)).scalars().all()
        scored3 = [(p, self.calculate_similarity(subject, p)) for p in result3]
        return scored3, 3
