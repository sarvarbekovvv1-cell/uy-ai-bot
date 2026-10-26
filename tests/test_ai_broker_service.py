"""Unit and integration tests for AIBrokerService."""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.fake_provider import FakeLLMProvider
from app.ai.schemas import AIBrokerIntent
from app.core.exceptions import AIBrokerRateLimitError
from app.models.property import Property
from app.models.user import User
from app.services.ai_broker_service import AIBrokerService


@pytest.fixture
async def sample_user(db_session: AsyncSession) -> User:
    """Create test customer user in database."""
    user = User(
        telegram_id=987654321,
        username="test_ai_customer",
        first_name="Jasur",
        phone="+998901234567",
        language="uz",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def sample_properties(db_session: AsyncSession, sample_user: User) -> dict[str, Property]:
    """Create approved and unapproved properties for testing."""
    approved_prop = Property(
        owner_user_id=sample_user.id,
        listing_type="sale",
        property_type="apartment",
        title="Chilonzor 2 xonali shinam kvartira",
        description="Toza ta'mirlangan, mebellari bilan",
        price=Decimal("95000"),
        currency="USD",
        rooms=2,
        total_area=Decimal("65.0"),
        floor=3,
        total_floors=9,
        condition="euro",
        has_furniture=True,
        region="Toshkent",
        district="Chilonzor",
        address="Chilonzor 9-mavze",
        status="approved",
        cadastre_status="available",
    )
    unapproved_prop = Property(
        owner_user_id=sample_user.id,
        listing_type="sale",
        property_type="apartment",
        title="Chilonzor tasdiqlanmagan kvartira",
        description="Hali ko‘rib chiqilmagan",
        price=Decimal("90000"),
        currency="USD",
        rooms=2,
        total_area=Decimal("60.0"),
        floor=2,
        total_floors=5,
        condition="euro",
        region="Toshkent",
        district="Chilonzor",
        address="Chilonzor 9-mavze",
        status="pending",
        cadastre_status="available",
    )
    db_session.add_all([approved_prop, unapproved_prop])
    await db_session.commit()
    await db_session.refresh(approved_prop)
    await db_session.refresh(unapproved_prop)
    return {"approved": approved_prop, "unapproved": unapproved_prop}


@pytest.mark.asyncio
async def test_ai_broker_rate_limit(sample_user: User) -> None:
    """Verify rapid-fire consecutive requests raise AIBrokerRateLimitError."""
    service = AIBrokerService(provider=FakeLLMProvider())
    service._cooldown_seconds = 2.0

    # First call succeeds
    service.check_rate_limit(sample_user.id)

    # Immediate second call must fail with rate limit
    with pytest.raises(AIBrokerRateLimitError):
        service.check_rate_limit(sample_user.id)


def test_build_safe_property_context_pii_absence() -> None:
    """Verify built safe context contains public fields and strictly omits all owner/broker PII."""
    service = AIBrokerService(provider=FakeLLMProvider())
    prop = Property(
        id=42,
        owner_user_id=999,
        listing_type="sale",
        property_type="apartment",
        title="Chilonzor kvartira",
        description="Oddiy ta'mir",
        price=Decimal("80000"),
        currency="USD",
        rooms=2,
        total_area=Decimal("58"),
        floor=2,
        total_floors=4,
        condition="good",
        has_furniture=False,
        region="Toshkent",
        district="Chilonzor",
    )

    ctx_text = service.build_safe_property_context(prop)
    # Public fields present
    assert "ID: #42" in ctx_text
    assert "Price: 80000 USD" in ctx_text
    assert "Rooms: 2" in ctx_text
    assert "District: Chilonzor" in ctx_text

    # PII absent
    assert "999" not in ctx_text
    assert "owner_user_id" not in ctx_text
    assert "phone" not in ctx_text.lower()
    assert "telegram" not in ctx_text.lower()
    assert "notes" not in ctx_text.lower()


@pytest.mark.asyncio
async def test_search_intent_approved_only_enforcement(
    db_session: AsyncSession,
    sample_user: User,
    sample_properties: dict[str, Property],
) -> None:
    """Search intent must return only approved properties and ignore pending listings."""
    provider = FakeLLMProvider()
    provider.set_next_intent(
        AIBrokerIntent(
            intent="search_property",
            district="Chilonzor",
            rooms=2,
            max_price=Decimal("100000"),
            currency="USD",
        )
    )
    service = AIBrokerService(provider=provider)

    result = await service.process_message(
        session=db_session,
        user=sample_user,
        message_text="Chilonzordan 2 xonali uy kerak",
    )

    assert result.action == "search_results"
    assert len(result.properties) == 1
    assert result.properties[0].id == sample_properties["approved"].id
    # Unapproved property must NOT be returned
    assert all(p.id != sample_properties["unapproved"].id for p in result.properties)


@pytest.mark.asyncio
async def test_search_intent_zero_results_no_hallucination(
    db_session: AsyncSession,
    sample_user: User,
) -> None:
    """Zero DB search results must return clear not-found text, never fake listings."""
    provider = FakeLLMProvider()
    provider.set_next_intent(
        AIBrokerIntent(
            intent="search_property",
            district="NonExistentDistrict",
            rooms=5,
            max_price=Decimal("10000"),
        )
    )
    service = AIBrokerService(provider=provider)

    result = await service.process_message(
        session=db_session,
        user=sample_user,
        message_text="NonExistentDistrict 5 xonali 10 ming",
    )

    assert result.action == "search_results"
    assert len(result.properties) == 0
    assert "mos e'lon topilmadi" in result.text


@pytest.mark.asyncio
async def test_property_question_approved_vs_unapproved(
    db_session: AsyncSession,
    sample_user: User,
    sample_properties: dict[str, Property],
) -> None:
    """Answering questions on approved property succeeds; unapproved property is blocked."""
    provider = FakeLLMProvider()
    service = AIBrokerService(provider=provider)

    # Question on approved property
    approved_id = sample_properties["approved"].id
    provider.set_next_intent(
        AIBrokerIntent(
            intent="property_question",
            property_id=approved_id,
            question="narxi qancha",
        )
    )
    res_app = await service.process_message(
        session=db_session,
        user=sample_user,
        message_text=f"#{approved_id} narxi qancha?",
    )
    assert res_app.action == "property_answer"
    assert "95000" in res_app.text

    # Reset cooldown
    service._user_last_request.clear()

    # Question on unapproved property
    unapproved_id = sample_properties["unapproved"].id
    provider.set_next_intent(
        AIBrokerIntent(
            intent="property_question",
            property_id=unapproved_id,
            question="narxi qancha",
        )
    )
    res_unapp = await service.process_message(
        session=db_session,
        user=sample_user,
        message_text=f"#{unapproved_id} narxi qancha?",
    )
    assert res_unapp.action == "property_answer"
    assert "topilmadi" in res_unapp.text


@pytest.mark.asyncio
async def test_viewing_and_broker_routing(
    db_session: AsyncSession,
    sample_user: User,
    sample_properties: dict[str, Property],
) -> None:
    """Verify request_viewing and request_broker return routing actions with verified property."""
    provider = FakeLLMProvider()
    service = AIBrokerService(provider=provider)
    approved_id = sample_properties["approved"].id

    # Viewing routing
    provider.set_next_intent(AIBrokerIntent(intent="request_viewing", property_id=approved_id))
    res_view = await service.process_message(
        session=db_session,
        user=sample_user,
        message_text=f"#{approved_id} uyni ko‘rmoqchiman",
    )
    assert res_view.action == "route_viewing"
    assert res_view.property_id == approved_id

    # Reset cooldown
    service._user_last_request.clear()

    # Broker routing
    provider.set_next_intent(AIBrokerIntent(intent="request_broker", property_id=approved_id))
    res_broker = await service.process_message(
        session=db_session,
        user=sample_user,
        message_text=f"#{approved_id} bo‘yicha broker kerak",
    )
    assert res_broker.action == "route_broker"
    assert res_broker.property_id == approved_id
