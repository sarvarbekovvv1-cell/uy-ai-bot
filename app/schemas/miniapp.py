"""Public data schemas for Telegram Mini App API."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MiniAppUser(BaseModel):
    """Authenticated user profile for Mini App."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    language: str = "uz"
    phone: str | None = None


class MiniAppPropertyMedia(BaseModel):
    """Public media item representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    media_type: str
    sort_order: int
    url: str


class MiniAppPropertySummary(BaseModel):
    """Compact property summary for list cards and search results."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_type: str
    property_type: str
    title: str
    region: str
    district: str
    rooms: int
    total_area: Decimal
    price: Decimal
    currency: str
    condition: str
    floor: int | None = None
    total_floors: int | None = None
    is_favorite: bool = False
    thumbnail_url: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None


class MiniAppPropertyDetail(BaseModel):
    """Full public details for an approved property."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_type: str
    property_type: str
    title: str
    description: str | None = None
    region: str
    district: str
    address: str
    rooms: int
    total_area: Decimal
    living_area: Decimal | None = None
    floor: int | None = None
    total_floors: int | None = None
    condition: str
    construction_type: str | None = None
    has_furniture: bool = False
    cadastre_status: str = "unknown"
    price: Decimal
    currency: str
    negotiable: bool = False
    is_favorite: bool = False
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    media: list[MiniAppPropertyMedia] = Field(default_factory=list)
    created_at: datetime


class MiniAppPropertyListResponse(BaseModel):
    """Paginated response for property search and listing."""

    items: list[MiniAppPropertySummary]
    total_count: int
    page: int
    page_size: int
    total_pages: int


class MiniAppMapProperty(BaseModel):
    """Optimized payload for map markers with valid coordinates."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    latitude: Decimal
    longitude: Decimal
    price: Decimal
    currency: str
    rooms: int
    property_type: str
    listing_type: str
    title: str
    district: str
    thumbnail_url: str | None = None


class MiniAppFavoriteResponse(BaseModel):
    """Response after adding or removing a favorite."""

    success: bool
    property_id: int
    is_favorite: bool


class MiniAppViewingRequestInput(BaseModel):
    """Input payload to request a property viewing."""

    preferred_date: date
    preferred_time: str = Field(min_length=1, max_length=50)
    customer_comment: str | None = Field(default=None, max_length=500)


class MiniAppViewingRequestResponse(BaseModel):
    """Response returned upon creating a viewing request."""

    id: int
    property_id: int
    request_type: str
    status: str
    preferred_date: date
    preferred_time: str
    created_at: datetime


class MiniAppBrokerContactInput(BaseModel):
    """Input payload to request broker contact regarding a property."""

    customer_comment: str | None = Field(default=None, max_length=500)


class MiniAppBrokerContactResponse(BaseModel):
    """Response returned upon requesting broker contact."""

    id: int
    property_id: int
    request_type: str
    status: str
    created_at: datetime


class MiniAppErrorDetail(BaseModel):
    """Uniform error response structure."""

    code: str
    message: str
    details: dict[str, Any] | None = None


class MiniAppErrorResponse(BaseModel):
    """Envelope for API error responses."""

    error: MiniAppErrorDetail
