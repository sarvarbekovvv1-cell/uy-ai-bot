"""Pydantic schemas for AI Broker intent parsing and safe property serialization."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AIBrokerIntent(BaseModel):
    """Structured intent representation extracted from user natural language query."""

    intent: Literal[
        "search_property",
        "property_question",
        "request_broker",
        "request_viewing",
        "favorites_help",
        "general_real_estate_help",
        "greeting",
        "unknown",
    ] = Field(description="Classified business intent category.")

    language: Literal["uz", "ru"] = Field(
        default="uz", description="Detected language of user input."
    )

    listing_type: Literal["sale", "rent"] | None = Field(
        default=None, description="Sale or rent listing classification."
    )

    property_type: Literal["apartment", "house", "commercial", "land"] | None = Field(
        default=None, description="Target real estate property type."
    )

    region: str | None = Field(default=None, description="Province or major region.")
    district: str | None = Field(default=None, description="City district (e.g. Chilonzor).")
    rooms: int | None = Field(default=None, description="Desired room count.")
    min_price: Decimal | None = Field(default=None, description="Minimum price boundary.")
    max_price: Decimal | None = Field(default=None, description="Maximum price boundary.")
    currency: Literal["USD", "UZS"] | None = Field(
        default=None, description="Currency denomination."
    )
    min_area: Decimal | None = Field(default=None, description="Minimum total area in sq.m.")
    max_area: Decimal | None = Field(default=None, description="Maximum total area in sq.m.")
    property_id: int | None = Field(
        default=None, description="Specific referenced property ID (e.g. 1)."
    )
    question: str | None = Field(default=None, description="Normalized question text.")
    needs_clarification: bool = Field(
        default=False, description="Flag indicating ambiguous request requiring question back."
    )
    clarification_question: str | None = Field(
        default=None, description="Clarification prompt for user."
    )
    needs_human_broker: bool = Field(
        default=False, description="Whether inquiry should escalate to human broker."
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score.")

    @field_validator("rooms")
    @classmethod
    def validate_rooms(cls, v: int | None) -> int | None:
        if v is not None and not (1 <= v <= 50):
            raise ValueError(f"Rooms count must be between 1 and 50, got {v}")
        return v

    @field_validator("min_price", "max_price")
    @classmethod
    def validate_prices(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v < Decimal("0"):
            raise ValueError(f"Price cannot be negative, got {v}")
        return v

    @field_validator("min_area", "max_area")
    @classmethod
    def validate_areas(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v <= Decimal("0"):
            raise ValueError(f"Area must be strictly positive, got {v}")
        return v

    @field_validator("property_id")
    @classmethod
    def validate_property_id(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError(f"Property ID must be positive integer, got {v}")
        return v


class PropertySafeContext(BaseModel):
    """Sanitized, public-only property context payload for LLM grounding.

    Strictly guarantees NO owner PII, customer PII, phone numbers,
    Telegram IDs, broker internal notes, or private cadastral records.
    """

    id: int
    listing_type: str
    property_type: str
    title: str
    description: str | None = None
    price: Decimal
    currency: str
    rooms: int
    total_area: Decimal
    floor: int | None = None
    total_floors: int | None = None
    condition: str | None = None
    has_furniture: bool = False
    region: str
    district: str
    address: str | None = None


class AIBrokerConversationMessage(BaseModel):
    """Single turn in a bounded short-term conversational context."""

    role: Literal["user", "model"]
    text: str
