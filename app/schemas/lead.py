"""Pydantic schemas for lead and follow-up validation in Broker Cabinet."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.lead import (
    FOLLOWUP_TYPES,
    LEAD_SOURCES,
    LEAD_STAGES,
    LOST_REASONS,
)


class LeadCreateSchema(BaseModel):
    """Schema for validating lead creation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    customer_user_id: int
    property_id: int
    source: str = Field(min_length=2, max_length=50)
    broker_user_id: int | None = None
    source_request_id: int | None = None

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        if v not in LEAD_SOURCES:
            raise ValueError(f"Invalid lead source '{v}'. Must be one of {LEAD_SOURCES}")
        return v


class LeadStageUpdateSchema(BaseModel):
    """Schema for validating lead stage transition."""

    model_config = ConfigDict(str_strip_whitespace=True)

    stage: str

    @field_validator("stage")
    @classmethod
    def validate_stage(cls, v: str) -> str:
        if v not in LEAD_STAGES:
            raise ValueError(f"Invalid lead stage '{v}'. Must be one of {LEAD_STAGES}")
        return v


class LeadCloseSchema(BaseModel):
    """Schema for closing a lead (won or lost)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    stage: Literal["won", "lost"]
    close_reason: str | None = Field(default=None, max_length=100)

    @field_validator("close_reason")
    @classmethod
    def validate_close_reason(cls, v: str | None) -> str | None:
        if v is not None and v not in LOST_REASONS:
            raise ValueError(f"Invalid close reason '{v}'. Must be one of {LOST_REASONS}")
        return v


class FollowUpCreateSchema(BaseModel):
    """Schema for creating a follow-up task."""

    model_config = ConfigDict(str_strip_whitespace=True)

    task_type: str
    due_at: datetime
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, v: str) -> str:
        if v not in FOLLOWUP_TYPES:
            raise ValueError(f"Invalid follow-up task type '{v}'. Must be one of {FOLLOWUP_TYPES}")
        return v

    @field_validator("due_at")
    @classmethod
    def validate_due_at(cls, v: datetime) -> datetime:
        now = datetime.now(UTC)
        target = v if v.tzinfo is not None else v.replace(tzinfo=UTC)
        if target <= now:
            raise ValueError("Follow-up due date must be in the future.")
        return v


class LeadNoteCreateSchema(BaseModel):
    """Schema for creating an internal broker note."""

    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=2000)
