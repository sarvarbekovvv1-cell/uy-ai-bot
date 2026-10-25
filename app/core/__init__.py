"""Core domain definitions and exceptions."""

from app.core.exceptions import (
    AuthorizationError,
    ConfigurationError,
    DatabaseConnectionError,
    EntityNotFoundError,
    IncompletePropertyError,
    InvalidPropertyStatusError,
    PropertyAccessDeniedError,
    PropertyNotFoundError,
    UyAIError,
)

__all__ = [
    "UyAIError",
    "ConfigurationError",
    "DatabaseConnectionError",
    "EntityNotFoundError",
    "AuthorizationError",
    "PropertyNotFoundError",
    "PropertyAccessDeniedError",
    "InvalidPropertyStatusError",
    "IncompletePropertyError",
]
