"""Pydantic schemas for viewing requests and appointment validation."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.viewing_request import VIEWING_OUTCOMES


class ViewingRequestCreate(BaseModel):
    """Schema for creating a viewing request."""

    model_config = ConfigDict(str_strip_whitespace=True)

    property_id: int
    preferred_date: date
    preferred_time: str = Field(min_length=2, max_length=20)
    customer_comment: str | None = Field(default=None, max_length=1000)


class BrokerContactCreate(BaseModel):
    """Schema for creating a broker contact request."""

    model_config = ConfigDict(str_strip_whitespace=True)

    property_id: int
    customer_comment: str | None = Field(default=None, max_length=1000)


class ViewingRejectSchema(BaseModel):
    """Schema for broker rejecting a request."""

    model_config = ConfigDict(str_strip_whitespace=True)

    reason: str = Field(min_length=3, max_length=1000)


class ViewingCompleteSchema(BaseModel):
    """Schema for broker completing a viewing."""

    model_config = ConfigDict(str_strip_whitespace=True)

    outcome: str

    @field_validator("outcome")
    @classmethod
    def validate_outcome(cls, v: str) -> str:
        """Validate outcome is in canonical allowed outcomes."""
        if v not in VIEWING_OUTCOMES:
            raise ValueError(f"Invalid outcome '{v}'. Must be one of {VIEWING_OUTCOMES}")
        return v
