"""Abstract interfaces for LLM providers."""

from abc import ABC, abstractmethod

from app.ai.schemas import AIBrokerIntent


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
