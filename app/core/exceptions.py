"""Core application exceptions."""


class UyAIError(Exception):
    """Base exception for all domain errors within UyAI."""

    def __init__(self, message: str = "An internal application error occurred.") -> None:
        super().__init__(message)
        self.message = message


class ConfigurationError(UyAIError):
    """Raised when configuration validation or environment resolution fails."""


class DatabaseConnectionError(UyAIError):
    """Raised when connecting or pinging the database fails."""


class EntityNotFoundError(UyAIError):
    """Raised when a requested entity does not exist."""


class PropertyNotFoundError(EntityNotFoundError):
    """Raised when a requested property cannot be found."""


class PropertyAccessDeniedError(UyAIError):
    """Raised when a user attempts an unauthorized action on a property."""


class InvalidPropertyStatusError(UyAIError):
    """Raised when an illegal property status transition is attempted."""


class IncompletePropertyError(UyAIError):
    """Raised when mandatory property listing fields or photos are missing."""


class AuthorizationError(UyAIError):
    """Raised when a user lacks required permissions."""


class ViewingRequestNotFoundError(EntityNotFoundError):
    """Raised when a requested viewing request cannot be found."""


class InvalidViewingTransitionError(UyAIError):
    """Raised when an illegal viewing request status transition is attempted."""


class ViewingPermissionError(AuthorizationError):
    """Raised when a user lacks permission to view or manage a viewing request."""


class PropertyUnavailableError(UyAIError):
    """Raised when an action is attempted on an unavailable (non-approved) property."""


class ViewingValidationError(UyAIError):
    """Raised when viewing request input validation fails."""


class DuplicateViewingRequestError(UyAIError):
    """Raised when an active duplicate viewing request already exists."""
