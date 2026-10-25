"""Official Google GenAI SDK integration for UyAI AI Broker."""

import asyncio
import json
import time

from google import genai
from google.genai import types
from pydantic import ValidationError

from app.ai.interfaces import LLMProvider
from app.ai.prompts import (
    GROUNDED_PROPERTY_RESPONSE_SYSTEM_PROMPT,
    INTENT_EXTRACTION_SYSTEM_PROMPT,
    VALUATION_EXPLANATION_SYSTEM_PROMPT,
)
from app.ai.schemas import AIBrokerIntent
from app.config import Settings, get_settings
from app.core.exceptions import (
    AIBrokerProviderError,
    AIBrokerTimeoutError,
    AIBrokerValidationError,
)
from app.logging import get_logger
from app.schemas.valuation import ValuationExplanation, ValuationSafeContext

logger = get_logger(__name__)


class GeminiLLMProvider(LLMProvider):
    """Production LLM provider using Google's official google-genai SDK."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.api_key = self.settings.gemini_api_key
        self.model_name = self.settings.gemini_model
        self.timeout = self.settings.ai_request_timeout_seconds

        # Initialize the official GenAI client if API key is provided
        self._client: genai.Client | None = None
        if self.api_key:
            self._client = genai.Client(api_key=self.api_key)

    @property
    def client(self) -> genai.Client:
        """Return initialized GenAI client or raise error."""
        if not self._client:
            raise AIBrokerProviderError("GEMINI_API_KEY is not configured.")
        return self._client

    async def parse_intent(
        self,
        user_message: str,
        history: list[dict[str, str]] | None = None,
        language: str = "uz",
    ) -> AIBrokerIntent:
        """Parse user query into validated AIBrokerIntent using Gemini structured JSON output."""
        start_time = time.monotonic()
        system_instruction = INTENT_EXTRACTION_SYSTEM_PROMPT

        # Build contents including history
        prompt_parts: list[str] = []
        if history:
            prompt_parts.append("CONVERSATION RECENT HISTORY:")
            for turn in history[-self.settings.ai_max_history_messages :]:
                role = turn.get("role", "user")
                text = turn.get("text", "")
                prompt_parts.append(f"{role.upper()}: {text}")
            prompt_parts.append("---")

        prompt_parts.append(f"CURRENT USER MESSAGE ({language}):\n{user_message}")
        full_content = "\n".join(prompt_parts)

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=AIBrokerIntent,
            temperature=0.1,
            max_output_tokens=1024,
        )

        # Retry once on transient network errors
        attempts = 2
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                response = await asyncio.wait_for(
                    self.client.aio.models.generate_content(
                        model=self.model_name,
                        contents=full_content,
                        config=config,
                    ),
                    timeout=self.timeout,
                )

                latency = time.monotonic() - start_time
                logger.info(
                    "Gemini parse_intent succeeded (model=%s, latency=%.3fs, attempt=%d)",
                    self.model_name,
                    latency,
                    attempt + 1,
                )

                raw_text = response.text or "{}"
                # Clean up any potential markdown fences
                cleaned_json = raw_text.strip()
                if cleaned_json.startswith("```json"):
                    cleaned_json = cleaned_json[7:]
                if cleaned_json.startswith("```"):
                    cleaned_json = cleaned_json[3:]
                if cleaned_json.endswith("```"):
                    cleaned_json = cleaned_json[:-3]
                cleaned_json = cleaned_json.strip()

                try:
                    data = json.loads(cleaned_json)
                    return AIBrokerIntent.model_validate(data)
                except (json.JSONDecodeError, ValidationError) as val_err:
                    logger.warning(
                        "Gemini returned invalid structured output: %s", str(val_err)
                    )
                    raise AIBrokerValidationError(
                        f"Failed to validate Gemini intent response: {val_err}"
                    ) from val_err

            except TimeoutError as te:
                logger.error("Gemini API call timed out after %.1fs", self.timeout)
                raise AIBrokerTimeoutError("Gemini request timed out.") from te
            except AIBrokerValidationError:
                raise
            except Exception as e:
                last_error = e
                logger.warning(
                    "Transient error calling Gemini parse_intent (attempt=%d): %s",
                    attempt + 1,
                    type(e).__name__,
                )
                if attempt < attempts - 1:
                    await asyncio.sleep(0.5)

        raise AIBrokerProviderError(
            f"Failed to parse intent with Gemini: {type(last_error).__name__}"
        ) from last_error

    async def generate_grounded_response(
        self,
        query: str,
        context: str,
        language: str = "uz",
    ) -> str:
        """Generate concise factual response strictly grounded in supplied property context."""
        start_time = time.monotonic()
        system_instruction = GROUNDED_PROPERTY_RESPONSE_SYSTEM_PROMPT.format(language=language)

        full_content = (
            f"VERIFIED_CONTEXT:\n{context}\n\n"
            f"USER_QUERY ({language}):\n{query}\n\n"
            "INSTRUCTION: Answer using ONLY verified context above. If missing, say not specified."
        )

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2,
            max_output_tokens=512,
        )

        try:
            response = await asyncio.wait_for(
                self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=full_content,
                    config=config,
                ),
                timeout=self.timeout,
            )

            latency = time.monotonic() - start_time
            logger.info(
                "Gemini generate_grounded_response succeeded (model=%s, latency=%.3fs)",
                self.model_name,
                latency,
            )
            return (response.text or "").strip()

        except TimeoutError as te:
            logger.error("Gemini grounded response timed out after %.1fs", self.timeout)
            raise AIBrokerTimeoutError("Gemini request timed out.") from te
        except Exception as e:
            logger.error(
                "Gemini grounded response failed: %s",
                type(e).__name__,
            )
            raise AIBrokerProviderError(
                f"Failed to generate grounded response: {type(e).__name__}"
            ) from e

    async def explain_valuation(
        self,
        context: ValuationSafeContext,
        language: str = "uz",
    ) -> ValuationExplanation:
        """Generate safe, structured narrative explanation for deterministic valuation result."""
        start_time = time.monotonic()
        system_instruction = VALUATION_EXPLANATION_SYSTEM_PROMPT.format(language=language)

        full_content = (
            f"DETERMINISTIC_VALUATION_CONTEXT:\n"
            f"Listing type: {context.listing_type}\n"
            f"Property type: {context.property_type}\n"
            f"Location: {context.region}, {context.district}\n"
            f"Rooms: {context.rooms}, Area: {context.total_area} m2\n"
            f"Condition: {context.condition or 'not specified'}\n"
            f"Authoritative Price Range: {context.estimated_price_range_str}\n"
            f"Authoritative Central Price: {context.central_price_str}\n"
            f"Median Price/m2: {context.median_price_per_m2_str or 'N/A'}\n"
            f"Confidence: {context.confidence}\n"
            f"Comparable Count: {context.comparable_count}\n"
            f"Comparison Tier: {context.comparison_tier}\n"
            f"Key Factors: {', '.join(context.factors)}\n"
            f"Reliability Warnings: {', '.join(context.warnings)}\n\n"
            f"INSTRUCTION: Explain this already-calculated valuation in {language}. "
            "Do NOT alter numbers or ranges. Conform strictly to the JSON schema."
        )

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2,
            response_mime_type="application/json",
            response_schema=ValuationExplanation,
            max_output_tokens=1024,
        )

        attempts = 3
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                response = await asyncio.wait_for(
                    self.client.aio.models.generate_content(
                        model=self.model_name,
                        contents=full_content,
                        config=config,
                    ),
                    timeout=self.timeout,
                )

                latency = time.monotonic() - start_time
                logger.info(
                    "Gemini explain_valuation succeeded (model=%s, latency=%.3fs, attempt=%d)",
                    self.model_name,
                    latency,
                    attempt + 1,
                )

                raw_text = response.text or "{}"
                cleaned_json = raw_text.strip()
                if cleaned_json.startswith("```json"):
                    cleaned_json = cleaned_json[7:]
                if cleaned_json.startswith("```"):
                    cleaned_json = cleaned_json[3:]
                if cleaned_json.endswith("```"):
                    cleaned_json = cleaned_json[:-3]
                cleaned_json = cleaned_json.strip()

                parsed_data = json.loads(cleaned_json)
                return ValuationExplanation.model_validate(parsed_data)

            except TimeoutError as te:
                logger.error("Gemini explain_valuation timed out after %.1fs", self.timeout)
                raise AIBrokerTimeoutError("Gemini request timed out.") from te
            except (json.JSONDecodeError, ValidationError) as parse_err:
                logger.error(
                    "Gemini explain_valuation failed schema/JSON validation: %s",
                    parse_err,
                )
                msg = "Failed to parse valuation JSON response."
                raise AIBrokerValidationError(msg) from parse_err
            except Exception as e:
                last_error = e
                logger.warning(
                    "Transient error calling Gemini explain_valuation (attempt=%d): %s",
                    attempt + 1,
                    type(e).__name__,
                )
                if attempt < attempts - 1:
                    await asyncio.sleep(1.0)

        logger.error(
            "Gemini explain_valuation failed after %d attempts: %s",
            attempts,
            type(last_error).__name__,
        )
        raise AIBrokerProviderError(
            f"Failed to generate valuation explanation: {type(last_error).__name__}"
        ) from last_error
