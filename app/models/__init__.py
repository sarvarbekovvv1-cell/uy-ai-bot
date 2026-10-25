"""SQLAlchemy database models for UyAI."""

from app.models.favorite import Favorite
from app.models.property import (
    CADASTRE_STATUSES,
    LISTING_TYPES,
    PROPERTY_CONDITIONS,
    PROPERTY_STATUSES,
    PROPERTY_TYPES,
    SUPPORTED_CURRENCIES,
    Property,
)
from app.models.property_media import PropertyMedia
from app.models.role import DEFAULT_CUSTOMER_ROLE, SYSTEM_ROLES, Role, UserRole
from app.models.user import User

__all__ = [
    "User",
    "Role",
    "UserRole",
    "SYSTEM_ROLES",
    "DEFAULT_CUSTOMER_ROLE",
    "Property",
    "PropertyMedia",
    "Favorite",
    "LISTING_TYPES",
    "PROPERTY_TYPES",
    "PROPERTY_CONDITIONS",
    "CADASTRE_STATUSES",
    "PROPERTY_STATUSES",
    "SUPPORTED_CURRENCIES",
]
