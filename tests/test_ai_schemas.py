"""Unit tests for AI Broker Pydantic schemas, validation, and safe property context."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.ai.schemas import (
    AIBrokerConversationMessage,
    AIBrokerIntent,
    PropertySafeContext,
)


def test_ai_broker_intent_valid_search() -> None:
    """Test valid property search intent with all real estate filters."""
    intent = AIBrokerIntent(
        intent="search_property",
        language="uz",
        listing_type="sale",
        property_type="apartment",
        district="Chilonzor",
        rooms=2,
        min_price=Decimal("50000"),
        max_price=Decimal("100000"),
        currency="USD",
        min_area=Decimal("45"),
        max_area=Decimal("90"),
        confidence=0.95,
    )
    assert intent.intent == "search_property"
    assert intent.district == "Chilonzor"
    assert intent.rooms == 2
    assert intent.max_price == Decimal("100000")
    assert intent.currency == "USD"


def test_ai_broker_intent_property_question() -> None:
    """Test valid property question intent."""
    intent = AIBrokerIntent(
        intent="property_question",
        property_id=1,
        question="narxi qancha",
        language="uz",
    )
    assert intent.intent == "property_question"
    assert intent.property_id == 1
    assert intent.question == "narxi qancha"


def test_ai_broker_intent_all_valid_intents() -> None:
    """Verify all canonical intent types are accepted."""
    valid_intents = [
        "search_property",
        "property_question",
        "request_broker",
        "request_viewing",
        "favorites_help",
        "general_real_estate_help",
        "greeting",
        "unknown",
    ]
    for intent_name in valid_intents:
        obj = AIBrokerIntent(intent=intent_name)
        assert obj.intent == intent_name


def test_ai_broker_intent_invalid_intent_rejected() -> None:
    """Arbitrary model actions must be rejected by Pydantic validation."""
    with pytest.raises(ValidationError):
        AIBrokerIntent.model_validate({"intent": "arbitrary_custom_action"})


def test_ai_broker_intent_negative_price_rejected() -> None:
    """Negative prices must fail Pydantic validation."""
    with pytest.raises(ValidationError, match="Price cannot be negative"):
        AIBrokerIntent(intent="search_property", min_price=Decimal("-100"))

    with pytest.raises(ValidationError, match="Price cannot be negative"):
        AIBrokerIntent(intent="search_property", max_price=Decimal("-500"))


def test_ai_broker_intent_invalid_rooms_rejected() -> None:
    """Impossible room counts (<1 or >50) must fail validation."""
    with pytest.raises(ValidationError, match="Rooms count must be between 1 and 50"):
        AIBrokerIntent(intent="search_property", rooms=0)

    with pytest.raises(ValidationError, match="Rooms count must be between 1 and 50"):
        AIBrokerIntent(intent="search_property", rooms=55)


def test_ai_broker_intent_invalid_area_rejected() -> None:
    """Zero or negative area must fail validation."""
    with pytest.raises(ValidationError, match="Area must be strictly positive"):
        AIBrokerIntent(intent="search_property", min_area=Decimal("0"))

    with pytest.raises(ValidationError, match="Area must be strictly positive"):
        AIBrokerIntent(intent="search_property", min_area=Decimal("-10"))


def test_ai_broker_intent_invalid_property_id_rejected() -> None:
    """Non-positive property IDs must fail validation."""
    with pytest.raises(ValidationError, match="Property ID must be positive integer"):
        AIBrokerIntent(intent="property_question", property_id=0)

    with pytest.raises(ValidationError, match="Property ID must be positive integer"):
        AIBrokerIntent(intent="property_question", property_id=-5)


def test_property_safe_context_schema() -> None:
    """Verify PropertySafeContext contains public fields and refuses non-standard fields."""
    ctx = PropertySafeContext(
        id=1,
        listing_type="sale",
        property_type="apartment",
        title="Yangi kvartira",
        description="Toza ta'mirlangan",
        price=Decimal("85000"),
        currency="USD",
        rooms=3,
        total_area=Decimal("78.5"),
        floor=4,
        total_floors=9,
        condition="euro",
        has_furniture=True,
        region="Toshkent",
        district="Yunusobod",
        address="Amir Temur ko'chasi",
    )
    data = ctx.model_dump()
    assert data["id"] == 1
    assert data["price"] == Decimal("85000")
    # Verify absence of private PII keys
    assert "owner_user_id" not in data
    assert "owner_phone" not in data
    assert "customer_phone" not in data
    assert "telegram_id" not in data
    assert "notes" not in data


def test_ai_broker_conversation_message() -> None:
    """Verify conversational message payload validation."""
    msg = AIBrokerConversationMessage(role="user", text="Salom")
    assert msg.role == "user"
    assert msg.text == "Salom"

    msg_model = AIBrokerConversationMessage(role="model", text="Qanday uy kerak?")
    assert msg_model.role == "model"

    with pytest.raises(ValidationError):
        AIBrokerConversationMessage(role="system", text="Not allowed role")
