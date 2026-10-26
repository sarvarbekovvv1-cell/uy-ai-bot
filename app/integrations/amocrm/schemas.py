"""Pydantic schemas for amoCRM API models and webhooks."""

from typing import Any

from pydantic import BaseModel, Field


class AmoCRMTokenResponse(BaseModel):
    """OAuth 2.0 token response payload."""

    token_type: str = "Bearer"
    expires_in: int
    access_token: str
    refresh_token: str


class AmoCRMCustomFieldValue(BaseModel):
    """Field value item in amoCRM custom fields."""

    value: Any
    enum_id: int | None = None
    enum_code: str | None = None


class AmoCRMCustomField(BaseModel):
    """Custom field representation for amoCRM entities."""

    field_id: int | None = None
    field_name: str | None = None
    field_code: str | None = None
    values: list[AmoCRMCustomFieldValue]


class AmoCRMContactCreate(BaseModel):
    """Payload to create or update contact in amoCRM."""

    name: str
    first_name: str | None = None
    last_name: str | None = None
    responsible_user_id: int | None = None
    custom_fields_values: list[AmoCRMCustomField] = Field(default_factory=list)


class AmoCRMLeadCreate(BaseModel):
    """Payload to create lead in amoCRM."""

    name: str
    price: int = 0
    status_id: int | None = None
    pipeline_id: int | None = None
    responsible_user_id: int | None = None
    custom_fields_values: list[AmoCRMCustomField] = Field(default_factory=list)
    embedded_contacts: list[int] = Field(default_factory=list)


class AmoCRMLeadUpdate(BaseModel):
    """Payload to update existing lead in amoCRM."""

    id: int
    status_id: int | None = None
    pipeline_id: int | None = None
    price: int | None = None
    responsible_user_id: int | None = None
    custom_fields_values: list[AmoCRMCustomField] = Field(default_factory=list)


class AmoCRMNoteCreate(BaseModel):
    """Payload to add note to lead in amoCRM."""

    note_type: str = "common"
    text: str


class AmoCRMWebhookLeadItem(BaseModel):
    """Single lead item delivered in amoCRM webhook status updates."""

    id: int
    status_id: int | None = None
    pipeline_id: int | None = None
    old_status_id: int | None = None
    old_pipeline_id: int | None = None
    responsible_user_id: int | None = None


class AmoCRMWebhookPayload(BaseModel):
    """Parsed webhook payload from amoCRM."""

    leads_status: list[AmoCRMWebhookLeadItem] = Field(default_factory=list)
    leads_add: list[AmoCRMWebhookLeadItem] = Field(default_factory=list)
    leads_update: list[AmoCRMWebhookLeadItem] = Field(default_factory=list)
