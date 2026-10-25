"""Unit tests for AI LLM providers: FakeLLMProvider and GeminiLLMProvider."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.fake_provider import FakeLLMProvider
from app.ai.gemini_provider import GeminiLLMProvider
from app.ai.schemas import AIBrokerIntent
from app.config import Settings
from app.core.exceptions import (
    AIBrokerProviderError,
    AIBrokerTimeoutError,
    AIBrokerValidationError,
)


@pytest.mark.asyncio
async def test_fake_llm_provider_queue() -> None:
    """Verify FakeLLMProvider respects enqueued intents and responses."""
    provider = FakeLLMProvider()
    expected_intent = AIBrokerIntent(
        intent="search_property",
        district="Yunusobod",
        rooms=3,
        max_price=Decimal("90000"),
        currency="USD",
    )
    provider.set_next_intent(expected_intent)
    provider.set_next_response("Test grounded answer")

    intent = await provider.parse_intent("Any query")
    assert intent == expected_intent

    resp = await provider.generate_grounded_response("Any question", "Context")
    assert resp == "Test grounded answer"


@pytest.mark.asyncio
async def test_fake_llm_provider_simulated_error() -> None:
    """Verify FakeLLMProvider raises configured exceptions."""
    provider = FakeLLMProvider()
    provider.set_error(RuntimeError("Simulated LLM outage"))

    with pytest.raises(RuntimeError, match="Simulated LLM outage"):
        await provider.parse_intent("Test query")


@pytest.mark.asyncio
async def test_fake_llm_provider_heuristics() -> None:
    """Verify FakeLLMProvider heuristic parsing for realistic queries."""
    provider = FakeLLMProvider()

    # Uzbek search
    intent1 = await provider.parse_intent(
        "Chilonzordan 2 xonali 100 ming dollargacha kvartira kerak", language="uz"
    )
    assert intent1.intent == "search_property"
    assert intent1.district == "Chilonzor"
    assert intent1.rooms == 2
    assert intent1.max_price == Decimal("100000")
    assert intent1.currency == "USD"

    # Russian search
    intent2 = await provider.parse_intent(
        "Мне нужна 2-комнатная квартира в Чиланзаре до 80 тысяч долларов", language="ru"
    )
    assert intent2.intent == "search_property"
    assert intent2.rooms == 2
    assert intent2.max_price == Decimal("80000")
    assert intent2.language == "ru"

    # Property question
    intent3 = await provider.parse_intent("#1 uy narxi qancha?", language="uz")
    assert intent3.intent == "property_question"
    assert intent3.property_id == 1

    # Viewing request
    intent4 = await provider.parse_intent("#1 uyni ko‘rmoqchiman", language="uz")
    assert intent4.intent == "request_viewing"
    assert intent4.property_id == 1

    # Broker request
    intent5 = await provider.parse_intent("Broker bilan gaplashmoqchiman", language="uz")
    assert intent5.intent == "request_broker"

    # Greeting
    intent6 = await provider.parse_intent("Assalomu alaykum", language="uz")
    assert intent6.intent == "greeting"


def test_gemini_provider_unconfigured_key() -> None:
    """Initializing client without key must raise AIBrokerProviderError."""
    settings = Settings(GEMINI_API_KEY="")
    provider = GeminiLLMProvider(settings=settings)
    with pytest.raises(AIBrokerProviderError, match="GEMINI_API_KEY is not configured"):
        _ = provider.client


@pytest.mark.asyncio
async def test_gemini_provider_parse_intent_success() -> None:
    """Mock Gemini client SDK returning valid structured JSON."""
    settings = Settings(
        GEMINI_API_KEY="test_key",
        GEMINI_MODEL="gemini-2.5-flash",
        AI_REQUEST_TIMEOUT_SECONDS=5.0,
    )
    provider = GeminiLLMProvider(settings=settings)

    mock_client = MagicMock()
    mock_aio = MagicMock()
    mock_models = MagicMock()

    json_payload = (
        '{"intent": "search_property", "language": "uz", "district": "Chilonzor", '
        '"rooms": 2, "max_price": 100000, "currency": "USD"}'
    )
    mock_response = MagicMock(text=f"```json\n{json_payload}\n```")
    mock_models.generate_content = AsyncMock(return_value=mock_response)
    mock_aio.models = mock_models
    mock_client.aio = mock_aio

    provider._client = mock_client

    intent = await provider.parse_intent("Chilonzordan 2 xonali uy kerak")
    assert intent.intent == "search_property"
    assert intent.district == "Chilonzor"
    assert intent.rooms == 2
    assert intent.max_price == Decimal("100000")


@pytest.mark.asyncio
async def test_gemini_provider_parse_intent_timeout() -> None:
    """Mock Gemini call timing out and raising AIBrokerTimeoutError."""
    settings = Settings(
        GEMINI_API_KEY="test_key",
        GEMINI_MODEL="gemini-2.5-flash",
        AI_REQUEST_TIMEOUT_SECONDS=0.01,
    )
    provider = GeminiLLMProvider(settings=settings)

    mock_client = MagicMock()
    mock_aio = MagicMock()
    mock_models = MagicMock()

    async def slow_call(*args, **kwargs):  # noqa: ARG001
        import asyncio

        await asyncio.sleep(0.5)

    mock_models.generate_content = AsyncMock(side_effect=slow_call)
    mock_aio.models = mock_models
    mock_client.aio = mock_aio
    provider._client = mock_client

    with pytest.raises(AIBrokerTimeoutError, match="timed out"):
        await provider.parse_intent("Any query")


@pytest.mark.asyncio
async def test_gemini_provider_invalid_json_validation_error() -> None:
    """Invalid JSON response raises AIBrokerValidationError."""
    settings = Settings(GEMINI_API_KEY="test_key")
    provider = GeminiLLMProvider(settings=settings)

    mock_client = MagicMock()
    mock_aio = MagicMock()
    mock_models = MagicMock()
    mock_models.generate_content = AsyncMock(return_value=MagicMock(text="Not a json response"))
    mock_aio.models = mock_models
    mock_client.aio = mock_aio
    provider._client = mock_client

    with pytest.raises(AIBrokerValidationError):
        await provider.parse_intent("Any query")


@pytest.mark.asyncio
async def test_gemini_provider_retry_on_transient_error() -> None:
    """Verify provider retries on first transient error and succeeds on second attempt."""
    settings = Settings(GEMINI_API_KEY="test_key", AI_REQUEST_TIMEOUT_SECONDS=5.0)
    provider = GeminiLLMProvider(settings=settings)

    mock_client = MagicMock()
    mock_aio = MagicMock()
    mock_models = MagicMock()

    valid_json = '{"intent": "greeting", "language": "uz"}'
    mock_models.generate_content = AsyncMock(
        side_effect=[
            ConnectionResetError("Transient network failure"),
            MagicMock(text=valid_json),
        ]
    )
    mock_aio.models = mock_models
    mock_client.aio = mock_aio
    provider._client = mock_client

    intent = await provider.parse_intent("Salom")
    assert intent.intent == "greeting"
    assert mock_models.generate_content.call_count == 2


@pytest.mark.asyncio
async def test_gemini_provider_generate_grounded_response() -> None:
    """Mock grounded response generation."""
    settings = Settings(GEMINI_API_KEY="test_key", AI_REQUEST_TIMEOUT_SECONDS=5.0)
    provider = GeminiLLMProvider(settings=settings)

    mock_client = MagicMock()
    mock_aio = MagicMock()
    mock_models = MagicMock()
    mock_models.generate_content = AsyncMock(
        return_value=MagicMock(text="Ushbu uy 3-qavatda joylashgan.")
    )
    mock_aio.models = mock_models
    mock_client.aio = mock_aio
    provider._client = mock_client

    resp = await provider.generate_grounded_response(
        query="#1 qaysi qavatda?",
        context="Floor: 3 / 9",
        language="uz",
    )
    assert resp == "Ushbu uy 3-qavatda joylashgan."
