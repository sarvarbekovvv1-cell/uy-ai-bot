"""amoCRM integration package for UyAI."""

from app.integrations.amocrm.auth import TokenManager
from app.integrations.amocrm.client import AmoCRMClient
from app.integrations.amocrm.constants import (
    EVENT_LEAD_CREATED,
    EVENT_NOTE_ADDED,
    EVENT_STAGE_UPDATED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_PROCESSING,
    STATUS_SUCCEEDED,
)
from app.integrations.amocrm.exceptions import (
    AmoCRMAuthError,
    AmoCRMDisabledError,
    AmoCRMError,
    AmoCRMPermanentError,
    AmoCRMRateLimitError,
    AmoCRMTemporaryError,
    AmoCRMValidationError,
)
from app.integrations.amocrm.mapper import AmoCRMMapper
from app.integrations.amocrm.provider import (
    AmoCRMProviderProtocol,
    FakeAmoCRMProvider,
    RealAmoCRMProvider,
)
from app.integrations.amocrm.service import AmoCRMService
from app.integrations.amocrm.worker import AmoCRMWorker

__all__ = [
    "TokenManager",
    "AmoCRMClient",
    "AmoCRMService",
    "AmoCRMWorker",
    "AmoCRMMapper",
    "AmoCRMProviderProtocol",
    "RealAmoCRMProvider",
    "FakeAmoCRMProvider",
    "AmoCRMError",
    "AmoCRMDisabledError",
    "AmoCRMAuthError",
    "AmoCRMRateLimitError",
    "AmoCRMValidationError",
    "AmoCRMTemporaryError",
    "AmoCRMPermanentError",
    "EVENT_LEAD_CREATED",
    "EVENT_STAGE_UPDATED",
    "EVENT_NOTE_ADDED",
    "STATUS_PENDING",
    "STATUS_PROCESSING",
    "STATUS_SUCCEEDED",
    "STATUS_FAILED",
]
