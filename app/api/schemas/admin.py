"""Pydantic schemas for the Admin / Manager API namespace."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Auth Schemas
# -----------------------------------------------------------------------------
class StaffLoginRequest(BaseModel):
    model_config = {"extra": "forbid"}

    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=128)


class UpdateUsernameRequest(BaseModel):
    model_config = {"extra": "forbid"}

    new_username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")


class UpdatePasswordRequest(BaseModel):
    model_config = {"extra": "forbid"}

    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)
    new_password_confirm: str = Field(..., min_length=8, max_length=128)


class StaffUserResponse(BaseModel):
    id: int
    username: str
    first_name: str | None = None
    last_name: str | None = None
    roles: list[str]
    permissions: list[str]
    csrf_token: str | None = None


# -----------------------------------------------------------------------------
# Dashboard Schemas
# -----------------------------------------------------------------------------
class DashboardMetricsResponse(BaseModel):
    total_users: int = 0
    active_properties: int = 0
    pending_moderation_properties: int = 0
    active_leads: int = 0
    new_leads_count: int = 0
    won_leads: int = 0
    lost_leads: int = 0
    total_viewings: int = 0
    crm_pending_events: int = 0
    crm_failed_events: int = 0
    crm_succeeded_events: int = 0
    ai_broker_enabled: bool = False

    # Frontend compatibility fields
    total_properties: int = 0
    approved_properties: int = 0
    total_leads: int = 0
    pending_viewings: int = 0


# -----------------------------------------------------------------------------
# Property Schemas
# -----------------------------------------------------------------------------
class AdminPropertyMediaItem(BaseModel):
    id: int
    file_type: str
    safe_url: str
    is_main: bool


class AdminPropertyOwnerInfo(BaseModel):
    id: int
    name: str
    phone: str | None = None


class AdminPropertyItem(BaseModel):
    id: int
    title: str | None = None
    property_type: str
    listing_type: str
    status: str
    region: str | None = None
    district: str | None = None
    price: Decimal | None = None
    currency: str = "USD"
    rooms: int | None = None
    total_area: Decimal | None = None
    created_at: datetime
    submitted_at: datetime | None = None
    rejection_reason: str | None = None


class AdminPropertyDetail(AdminPropertyItem):
    description: str | None = None
    address: str | None = None
    condition: str | None = None
    has_furniture: bool = False
    cadastre_status: str | None = None
    media: list[AdminPropertyMediaItem] = Field(default_factory=list)
    owner: AdminPropertyOwnerInfo | None = None


class PropertyModerationRequest(BaseModel):
    model_config = {"extra": "forbid"}

    reason: str | None = Field(default=None, max_length=500)


# -----------------------------------------------------------------------------
# User Schemas
# -----------------------------------------------------------------------------
class AdminUserItem(BaseModel):
    id: int
    telegram_id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    phone: str | None = None
    language: str
    is_active: bool
    roles: list[str]
    created_at: datetime


class UserRoleUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    roles: list[str] = Field(..., min_length=1)


# -----------------------------------------------------------------------------
# Broker Schemas
# -----------------------------------------------------------------------------
class AdminBrokerItem(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    role: str
    active_leads_count: int = 0
    viewings_count: int = 0
    won_leads_count: int = 0
    lost_leads_count: int = 0


# -----------------------------------------------------------------------------
# Lead Schemas
# -----------------------------------------------------------------------------
class AdminLeadNoteItem(BaseModel):
    id: int
    author_name: str
    note_text: str
    created_at: datetime


class AdminLeadEventItem(BaseModel):
    id: int
    event_type: str
    from_stage: str | None = None
    to_stage: str | None = None
    actor_name: str | None = None
    created_at: datetime


class AdminLeadItem(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    customer_phone: str | None = None
    property_id: int | None = None
    property_title: str | None = None
    stage: str
    source: str
    broker_id: int | None = None
    broker_name: str | None = None
    created_at: datetime
    updated_at: datetime
    amo_crm_lead_id: str | None = None


class AdminLeadDetail(AdminLeadItem):
    notes: list[AdminLeadNoteItem] = Field(default_factory=list)
    events: list[AdminLeadEventItem] = Field(default_factory=list)


class LeadStageUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    target_stage: str
    close_reason: str | None = None


class LeadAssignRequest(BaseModel):
    model_config = {"extra": "forbid"}

    broker_user_id: int


class LeadNoteCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    note_text: str = Field(..., min_length=1, max_length=2000)


# -----------------------------------------------------------------------------
# Viewing Request Schemas
# -----------------------------------------------------------------------------
class AdminViewingItem(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    property_id: int
    property_title: str
    broker_id: int | None = None
    broker_name: str | None = None
    preferred_date: date | None = None
    preferred_time: str | None = None
    status: str
    outcome: str | None = None
    customer_comment: str | None = None
    created_at: datetime


class ViewingActionRequest(BaseModel):
    model_config = {"extra": "forbid"}

    outcome: str | None = None
    notes: str | None = None


# -----------------------------------------------------------------------------
# CRM Outbox Schemas
# -----------------------------------------------------------------------------
class AdminCRMSyncEventItem(BaseModel):
    id: int
    event_type: str
    entity_type: str
    entity_id: int
    status: str
    attempt_count: int
    next_attempt_at: datetime
    last_error_safe: str | None = None
    created_at: datetime
    processed_at: datetime | None = None


class AdminCRMEntityLinkItem(BaseModel):
    id: int
    provider: str
    local_entity_type: str
    local_entity_id: int
    external_entity_type: str
    external_entity_id: str
    created_at: datetime


# -----------------------------------------------------------------------------
# Audit Log Schemas
# -----------------------------------------------------------------------------
class AdminAuditEventItem(BaseModel):
    id: int
    actor_id: int | None = None
    actor_name: str | None = None
    action: str
    entity_type: str
    entity_id: int | None = None
    metadata_json: str | None = None
    ip_address: str | None = None
    created_at: datetime


# -----------------------------------------------------------------------------
# Common Pagination & Response Wrapper
# -----------------------------------------------------------------------------
class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
