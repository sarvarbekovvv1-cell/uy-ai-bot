"""Exception taxonomy for amoCRM integration.

Ensures raw HTTP client errors and internal tokens are never leaked to business handlers.
"""

from app.core.exceptions import UyAIError


class AmoCRMError(UyAIError):
    """Base exception for all amoCRM integration failures."""


class AmoCRMDisabledError(AmoCRMError):
    """Raised when amoCRM integration is disabled by feature flag."""


class AmoCRMAuthError(AmoCRMError):
    """Raised when OAuth authentication or token refresh fails."""


class AmoCRMRateLimitError(AmoCRMError):
    """Raised when amoCRM API rate limits (HTTP 429) are encountered."""

    def __init__(self, message: str = "Rate limit exceeded.", retry_after: float = 60.0) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class AmoCRMValidationError(AmoCRMError):
    """Raised on invalid request schema, malformed payload, or validation rejection (HTTP 400)."""


class AmoCRMTemporaryError(AmoCRMError):
    """Raised on transient network timeouts, 5xx server errors, or temporary unavailability."""


class AmoCRMPermanentError(AmoCRMError):
    """Raised when an unrecoverable failure occurs (e.g. invalid credentials, unmapped pipeline)."""
