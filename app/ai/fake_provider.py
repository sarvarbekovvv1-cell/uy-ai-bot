"""Deterministic Fake LLM Provider for unit, integration, and E2E testing."""

import re
from decimal import Decimal
from typing import Any

from app.ai.interfaces import LLMProvider
from app.ai.schemas import AIBrokerIntent


class FakeLLMProvider(LLMProvider):
    """Test double that simulates LLM provider responses without network calls."""

    def __init__(self) -> None:
        self.intent_queue: list[AIBrokerIntent] = []
        self.response_queue: list[str] = []
        self.error_to_raise: Exception | None = None
        self.recorded_calls: list[dict[str, Any]] = []

    def set_next_intent(self, intent: AIBrokerIntent) -> None:
        """Enqueue a specific intent to be returned on next parse_intent call."""
        self.intent_queue.append(intent)

    def set_next_response(self, text: str) -> None:
        """Enqueue a specific text response for generate_grounded_response."""
        self.response_queue.append(text)

    def set_error(self, err: Exception | None) -> None:
        """Configure provider to raise an exception on next invocation."""
        self.error_to_raise = err

    async def parse_intent(
        self,
        user_message: str,
        history: list[dict[str, str]] | None = None,
        language: str = "uz",
    ) -> AIBrokerIntent:
        """Return enqueued or heuristically extracted intent for testing."""
        self.recorded_calls.append(
            {
                "method": "parse_intent",
                "message": user_message,
                "history": history,
                "lang": language,
            }
        )

        if self.error_to_raise:
            err = self.error_to_raise
            self.error_to_raise = None
            raise err

        if self.intent_queue:
            return self.intent_queue.pop(0)

        # Heuristic test fallback parser
        msg_lower = user_message.lower()

        # Prompt injection checks
        if "oldingi ko‘rsatmalarni unut" in msg_lower or "forget instructions" in msg_lower:
            return AIBrokerIntent(
                intent="general_real_estate_help",
                language=language,
                question="Prompt injection test",
            )

        # Property viewing request: e.g. "#1 uyni ko‘rmoqchiman"
        viewing_match = re.search(
            r"#?(\d+)\s*(?:-?\s*uyn?i?\s+ko[‘']?rmoqchiman|посмотреть)", msg_lower
        )
        if viewing_match or ("ko‘rmoqchiman" in msg_lower and "#" in msg_lower):
            m = re.search(r"(\d+)", user_message)
            prop_id = int(m.group(1)) if m else 1
            return AIBrokerIntent(
                intent="request_viewing",
                property_id=prop_id,
                language=language,
            )

        # Broker request
        is_broker_ask = (
            "broker bilan" in msg_lower
            or "свяжите меня с брокером" in msg_lower
            or ("broker" in msg_lower and "gaplash" in msg_lower)
        )
        if is_broker_ask:
            m = re.search(r"#(\d+)", user_message)
            prop_id = int(m.group(1)) if m else None
            return AIBrokerIntent(
                intent="request_broker",
                property_id=prop_id,
                language=language,
            )

        # Favorites help
        if "saqlagan" in msg_lower or "избранное" in msg_lower or "saqlangan" in msg_lower:
            return AIBrokerIntent(
                intent="favorites_help",
                language=language,
            )

        # Specific property question
        prop_q_match = re.search(r"#?(\d+)", user_message)
        has_prop_question = any(
            w in msg_lower for w in ["narxi", "qavat", "haqida", "цена", "сколько"]
        )
        if prop_q_match and has_prop_question:
            prop_id = int(prop_q_match.group(1))
            return AIBrokerIntent(
                intent="property_question",
                property_id=prop_id,
                question=user_message,
                language=language,
            )

        # Greetings
        if any(g in msg_lower for g in ["salom", "assalomu", "привет", "здравствуйте"]):
            return AIBrokerIntent(intent="greeting", language=language)

        # Natural language search parsing
        is_search = False
        district = None
        rooms = None
        max_price = None
        currency = None
        listing_type = "sale"

        if "ijara" in msg_lower or "аренд" in msg_lower or "снять" in msg_lower:
            listing_type = "rent"
            is_search = True

        if "chilonzor" in msg_lower or "чиланзар" in msg_lower:
            district = "Chilonzor"
            is_search = True
        elif "yunusobod" in msg_lower or "юнусабад" in msg_lower:
            district = "Yunusobod"
            is_search = True

        # Rooms
        rooms_match = re.search(r"(\d+)\s*[-_]?\s*(?:xona|xonali|комнат)", msg_lower)
        if rooms_match:
            rooms = int(rooms_match.group(1))
            is_search = True

        # Price
        if "100 ming" in msg_lower or "100000" in msg_lower or "100 k" in msg_lower:
            max_price = Decimal("100000")
            is_search = True
        elif "80" in msg_lower and ("тысяч" in msg_lower or "ming" in msg_lower):
            max_price = Decimal("80000")
            is_search = True
        elif "500" in msg_lower:
            max_price = Decimal("500")
            is_search = True

        if "dollar" in msg_lower or "$" in msg_lower:
            currency = "USD"
        elif "so‘m" in msg_lower or "som" in msg_lower or "сум" in msg_lower:
            currency = "UZS"

        # Multi-turn context accumulation if user provided refinements
        if history:
            for turn in history:
                text = turn.get("text", "").lower()
                if not district and ("chilonzor" in text or "чиланзар" in text):
                    district = "Chilonzor"
                if rooms is None:
                    rm = re.search(r"(\d+)\s*[-_]?\s*(?:xona|xonali|комнат)", text)
                    if rm:
                        rooms = int(rm.group(1))
                if max_price is None:
                    if "100 ming" in text or "100000" in text:
                        max_price = Decimal("100000")
                        currency = "USD"
                    elif "80" in text:
                        max_price = Decimal("80000")
                        currency = "USD"

        is_russian = any(c in msg_lower for c in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя")
        if is_search or district or rooms or max_price:
            return AIBrokerIntent(
                intent="search_property",
                language="ru" if is_russian else "uz",
                listing_type=listing_type,
                property_type="apartment",
                district=district,
                rooms=rooms,
                max_price=max_price,
                currency=currency or ("USD" if max_price else None),
            )

        return AIBrokerIntent(intent="unknown", language=language)

    async def generate_grounded_response(
        self,
        query: str,
        context: str,
        language: str = "uz",
    ) -> str:
        """Return enqueued or grounded test response."""
        self.recorded_calls.append(
            {
                "method": "generate_grounded_response",
                "query": query,
                "context": context,
                "lang": language,
            }
        )

        if self.error_to_raise:
            err = self.error_to_raise
            self.error_to_raise = None
            raise err

        if self.response_queue:
            return self.response_queue.pop(0)

        # Context-aware extraction for testing
        if "price:" in context.lower():
            match = re.search(r"price:\s*([\d\.]+)\s*(\w+)", context, re.IGNORECASE)
            if match:
                p_val, p_curr = match.group(1), match.group(2)
                if language == "ru":
                    return f"Цена данного объекта составляет {p_val} {p_curr}."
                return f"Ushbu ko‘chmas mulk narxi {p_val} {p_curr}."

        if language == "ru":
            return "Объект соответствует вашему запросу."
        return "Ko‘chmas mulk ma'lumotlari tasdiqlangan bazadan olindi."
