"""Property search filters schema."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class PropertySearchFilters(BaseModel):
    """Domain filter parameters for querying approved properties."""

    listing_type: Literal["sale", "rent"]
    property_type: str | None = None
    region: str | None = None
    district: str | None = None
    rooms: int | None = Field(default=None, ge=1)
    min_rooms: int | None = Field(default=None, ge=1)
    min_price: Decimal | None = Field(default=None, ge=Decimal(0))
    max_price: Decimal | None = Field(default=None, gt=Decimal(0))
    currency: Literal["USD", "UZS"] | None = None
    min_area: Decimal | None = Field(default=None, gt=Decimal(0))

    @model_validator(mode="after")
    def validate_search_filters(self) -> "PropertySearchFilters":
        """Validate price range and normalize text fields."""
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError("min_price cannot be greater than max_price")

        if (self.min_price is not None or self.max_price is not None) and not self.currency:
            raise ValueError("currency is required when price filter is specified")

        if self.property_type and self.property_type.strip().lower() in {
            "all",
            "hamma",
            "barchasi",
        }:
            self.property_type = None

        if self.region:
            self.region = self.region.strip()

        if self.district:
            self.district = self.district.strip()

        return self
