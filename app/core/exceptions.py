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


class AuthorizationError(UyAIError):
    """Raised when a user lacks required permissions."""
