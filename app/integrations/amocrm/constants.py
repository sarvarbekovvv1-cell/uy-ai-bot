"""Constants for amoCRM integration and synchronization."""

# amoCRM API Endpoints (v4)
OAUTH_TOKEN_ENDPOINT = "/oauth2/access_token"
CONTACTS_ENDPOINT = "/api/v4/contacts"
LEADS_ENDPOINT = "/api/v4/leads"
PIPELINES_ENDPOINT = "/api/v4/leads/pipelines"
USERS_ENDPOINT = "/api/v4/users"

# Transactional Outbox Event Types
EVENT_LEAD_CREATED = "lead_created"
EVENT_STAGE_UPDATED = "stage_updated"
EVENT_NOTE_ADDED = "note_added"

# Outbox Statuses
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"

# Default Status IDs in standard amoCRM pipeline if not configured
# Stage mapping fallback constants
# amoCRM universal system status IDs:
# 142 = "Успешно реализовано" (Won)
# 143 = "Закрыто и не реализовано" (Lost)
# Intermediate pipeline stages are account-specific and MUST be configured
# via AMOCRM_STAGE_MAPPING_JSON.
DEFAULT_STAGE_TO_STATUS: dict[str, int] = {
    "won": 142,
    "lost": 143,
}

# Inverted status to stage mapping for webhooks
DEFAULT_STATUS_TO_STAGE: dict[int, str] = {
    142: "won",
    143: "lost",
}

# Maximum retries before dead-letter failure
DEFAULT_MAX_RETRIES = 5
INITIAL_BACKOFF_SECONDS = 30
MAX_BACKOFF_SECONDS = 3600
STUCK_PROCESSING_TIMEOUT_MINUTES = 10
