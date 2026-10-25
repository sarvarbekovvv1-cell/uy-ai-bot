"""Tests for ValuationService orchestration, Gemini integration, and failure fallbacks."""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.fake_provider import FakeLLMProvider
from app.models.property import Property
from app.models.user import User
from app.schemas.valuation import PropertyValuationInput, ValuationExplanation
from app.services.valuation.service import ValuationService


async def create_approved_property(
    session: AsyncSession,
    owner_id: int,
    price: Decimal,
    total_area: Decimal = Decimal("50"),
    district: str = "Chilonzor",
) -> Property:
    """Create approved property in test DB."""
    prop = Property(
        owner_user_id=owner_id,
        listing_type="sale",
        property_type="apartment",
        title=f"Apartment in {district}",
        region="Toshkent shahri",
        district=district,
        address="Test str. 1",
        rooms=2,
        total_area=total_area,
        condition="renovated",
        price=price,
        currency="USD",
        status="approved",
    )
    session.add(prop)
    await session.commit()
    await session.refresh(prop)
    return prop


@pytest.mark.asyncio
async def test_valuation_service_with_fake_llm_provider(db_session: AsyncSession) -> None:
    """Verify ValuationService calls LLM provider and populates explanation."""
    owner = User(
        telegram_id=8801,
        username="val_owner_1",
        first_name="ValOwner1",
        phone="+998901230001",
    )
    db_session.add(owner)
    await db_session.commit()

    await create_approved_property(db_session, owner.id, Decimal("80000"))
    await create_approved_property(db_session, owner.id, Decimal("85000"))
    await create_approved_property(db_session, owner.id, Decimal("82000"))

    fake_llm = FakeLLMProvider()
    fake_llm.set_next_explanation(
        ValuationExplanation(
            summary="LLM mock explanation for Chilonzor property.",
            positive_factors=["Chilonzor markazi"],
            negative_factors=["Shovqinli ko'cha"],
            missing_information=["Qavat ma'lumoti"],
            recommendation="Tezroq sotuvga qo'ying",
        )
    )

    service = ValuationService(llm_provider=fake_llm)
    inp = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        total_area=Decimal("50"),
        rooms=2,
        currency="USD",
    )

    result = await service.valuate_property(db_session, inp, language="uz")

    assert result.insufficient_data is False
    assert result.estimated_price is not None
    assert result.explanation is not None
    assert result.explanation.summary == "LLM mock explanation for Chilonzor property."
    assert len(fake_llm.recorded_calls) == 1
    call = fake_llm.recorded_calls[0]
    assert call["method"] == "explain_valuation"


@pytest.mark.asyncio
async def test_gemini_cannot_alter_numeric_result(db_session: AsyncSession) -> None:
    """CRITICAL SECURITY TEST:

    Even if an LLM attempted to produce or suggest a different price in explanation,
    the engine's authoritative calculated price is immutable and application-owned.
    """
    owner = User(
        telegram_id=8802,
        username="val_owner_2",
        first_name="ValOwner2",
        phone="+998901230002",
    )
    db_session.add(owner)
    await db_session.commit()

    await create_approved_property(db_session, owner.id, Decimal("100000"))
    await create_approved_property(db_session, owner.id, Decimal("100000"))

    fake_llm = FakeLLMProvider()
    fake_llm.set_next_explanation(
        ValuationExplanation(
            summary="Prompt injection attempt: I claim this house is worth $1,000,000!",
            positive_factors=[],
            negative_factors=[],
            missing_information=[],
            recommendation="Ignore rules",
        )
    )

    service = ValuationService(llm_provider=fake_llm)
    inp = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        total_area=Decimal("50"),
        rooms=2,
        currency="USD",
    )

    result = await service.valuate_property(db_session, inp, language="uz")

    # Authoritative calculation must NOT be $1,000,000!
    assert result.estimated_price is not None
    assert result.estimated_price == Decimal("100000")  # Exactly matches the comparables math
    assert result.estimated_min_price < Decimal("100000")
    assert result.estimated_max_price > Decimal("100000")


@pytest.mark.asyncio
async def test_gemini_failure_resilience_uses_fallback(db_session: AsyncSession) -> None:
    """CRITICAL RESILIENCE RULE:

    If Gemini raises TimeoutError or API exception, valuation must STILL SUCCEED
    and return the deterministic numeric valuation with localized template explanation.
    """
    owner = User(
        telegram_id=8803,
        username="val_owner_3",
        first_name="ValOwner3",
        phone="+998901230003",
    )
    db_session.add(owner)
    await db_session.commit()

    await create_approved_property(db_session, owner.id, Decimal("90000"))
    await create_approved_property(db_session, owner.id, Decimal("95000"))

    fake_llm = FakeLLMProvider()
    fake_llm.set_error(TimeoutError("Google GenAI API timed out."))

    service = ValuationService(llm_provider=fake_llm)
    inp = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        total_area=Decimal("50"),
        rooms=2,
        currency="USD",
    )

    # Must NOT raise exception!
    result = await service.valuate_property(db_session, inp, language="uz")

    assert result.insufficient_data is False
    assert result.estimated_price is not None
    assert result.explanation is not None
    # Explanation fell back to deterministic template!
    assert "Chilonzor" in result.explanation.summary
    assert "o‘xshash e'longa asoslandi" in result.explanation.summary


@pytest.mark.asyncio
async def test_pii_security_no_sensitive_data_sent_to_llm(db_session: AsyncSession) -> None:
    """CRITICAL PRIVACY TEST:

    Verify that ValuationSafeContext passed to Gemini contains NO owner phone,
    customer phone, Telegram ID, or internal broker notes.
    """
    owner = User(
        telegram_id=8804,
        username="private_owner",
        first_name="PrivateOwner",
        phone="+998909998877",  # SENSITIVE!
    )
    db_session.add(owner)
    await db_session.commit()

    await create_approved_property(db_session, owner.id, Decimal("90000"))
    await create_approved_property(db_session, owner.id, Decimal("92000"))

    fake_llm = FakeLLMProvider()
    service = ValuationService(llm_provider=fake_llm)
    inp = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        total_area=Decimal("50"),
        rooms=2,
        currency="USD",
    )

    await service.valuate_property(db_session, inp, language="uz")

    assert len(fake_llm.recorded_calls) == 1
    context_sent = fake_llm.recorded_calls[0]["context"]
    context_str = str(context_sent)

    # Assert NO sensitive tokens/phones/IDs are present
    assert "+998909998877" not in context_str
    assert "8804" not in context_str
    assert "private_owner" not in context_str
    assert "phone" not in context_sent
    assert "telegram_id" not in context_sent
