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


class LeadNotFoundError(EntityNotFoundError):
    """Raised when a requested lead cannot be found."""


class LeadPermissionError(AuthorizationError):
    """Raised when a user lacks permission to access or manage a lead."""


class InvalidLeadTransitionError(UyAIError):
    """Raised when an illegal lead stage transition is attempted."""


class DuplicateLeadError(UyAIError):
    """Raised when an active duplicate lead already exists for customer + property."""


class LeadAlreadyAssignedError(UyAIError):
    """Raised when attempting to assign a lead that is already claimed by another broker."""


class LeadValidationError(UyAIError):
    """Raised when lead input validation fails."""


class FollowUpNotFoundError(EntityNotFoundError):
    """Raised when a requested follow-up task cannot be found."""


class AIBrokerError(UyAIError):
    """Base exception for AI Broker operations."""


class AIBrokerProviderError(AIBrokerError):
    """Raised when the LLM provider fails to generate a response."""


class AIBrokerTimeoutError(AIBrokerError):
    """Raised when the LLM request times out."""


class AIBrokerValidationError(AIBrokerError):
    """Raised when structured LLM output fails schema validation."""


class AIBrokerRateLimitError(AIBrokerError):
    """Raised when user exceeds the AI Broker request cooldown."""
