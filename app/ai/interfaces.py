"""Abstract interfaces for LLM providers."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from app.ai.schemas import AIBrokerIntent

if TYPE_CHECKING:
    from app.schemas.valuation import ValuationExplanation, ValuationSafeContext


class LLMProvider(ABC):
    """Abstract base class for LLM inference providers."""

    @abstractmethod
    async def parse_intent(
        self,
        user_message: str,
        history: list[dict[str, str]] | None = None,
        language: str = "uz",
    ) -> AIBrokerIntent:
        """Extract structured real estate intent from natural language input."""
        pass

    @abstractmethod
    async def generate_grounded_response(
        self,
        query: str,
        context: str,
        language: str = "uz",
    ) -> str:
        """Generate a concise, strictly grounded response based on verified application context."""
        pass

    @abstractmethod
    async def explain_valuation(
        self,
        context: "ValuationSafeContext",
        language: str = "uz",
    ) -> "ValuationExplanation":
        """Generate safe, structured explanation for deterministic valuation result."""
        pass
