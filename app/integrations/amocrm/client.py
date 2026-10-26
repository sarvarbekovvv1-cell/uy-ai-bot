"""Async HTTP client for amoCRM API v4."""

import urllib.parse
from typing import Any

import httpx

from app.config import Settings
from app.integrations.amocrm.auth import TokenManager
from app.integrations.amocrm.constants import (
    CONTACTS_ENDPOINT,
    LEADS_ENDPOINT,
    PIPELINES_ENDPOINT,
)
from app.integrations.amocrm.exceptions import (
    AmoCRMAuthError,
    AmoCRMDisabledError,
    AmoCRMPermanentError,
    AmoCRMRateLimitError,
    AmoCRMTemporaryError,
    AmoCRMValidationError,
)
from app.logging import get_logger

logger = get_logger(__name__)


class AmoCRMClient:
    """Production async HTTP client for communicating with amoCRM API v4.

    Features:
    - Automatic Bearer token injection and transparent single-retry 401 handling.
    - Connection pooling and keepalive.
    - Rate limit (HTTP 429) detection and Retry-After parsing.
    - Safe error sanitization without logging tokens or authorization headers.
    """

    def __init__(
        self,
        settings: Settings,
        token_manager: TokenManager | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.token_manager = token_manager or TokenManager(settings=settings)
        self._custom_client = http_client
        self._internal_client: httpx.AsyncClient | None = None

    def _validate_base_url(self, base_url: str) -> None:
        """Validate amoCRM base URL against allowed hosts to prevent SSRF."""
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme not in ("https", "http"):
            raise AmoCRMPermanentError(f"Invalid amoCRM base URL scheme: '{parsed.scheme}'")

        hostname = (parsed.hostname or "").lower()
        if not hostname:
            raise AmoCRMPermanentError("Invalid amoCRM base URL: missing hostname.")

        if self.settings.app_env != "production" and hostname in (
            "localhost",
            "127.0.0.1",
            "::1",
            "testserver",
            "test",
        ):
            return

        if parsed.scheme != "https":
            raise AmoCRMPermanentError("amoCRM base URL must use HTTPS in production.")

        allowed_suffixes = (".amocrm.ru", ".amocrm.com", ".kommo.com")
        if not any(hostname == s.lstrip(".") or hostname.endswith(s) for s in allowed_suffixes):
            raise AmoCRMPermanentError(
                f"amoCRM base URL host '{hostname}' is not a trusted amoCRM/Kommo domain."
            )

    async def _get_client(self) -> httpx.AsyncClient:
        if self._custom_client is not None:
            return self._custom_client
        if self._internal_client is None or self._internal_client.is_closed:
            timeout_sec = self.settings.amocrm_request_timeout_seconds
            self._internal_client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=timeout_sec,
                    read=timeout_sec,
                    write=timeout_sec,
                    pool=timeout_sec,
                ),
                follow_redirects=False,
                headers={"Accept": "application/json"},
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._internal_client

    async def close(self) -> None:
        """Close internal HTTP client session."""
        if self._internal_client is not None and not self._internal_client.is_closed:
            await self._internal_client.aclose()

    async def request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json_data: Any = None,
        retry_on_401: bool = True,
    ) -> dict[str, Any]:
        """Send authenticated request to amoCRM API v4 with single 401 refresh retry."""
        if not self.settings.amocrm_enabled:
            raise AmoCRMDisabledError("amoCRM integration is disabled.")

        base_url = self.settings.get_effective_amocrm_base_url()
        if not base_url:
            raise AmoCRMPermanentError("amoCRM base URL is not configured.")
        self._validate_base_url(base_url)

        url = f"{base_url}{endpoint}"
        client = await self._get_client()

        token = await self.token_manager.get_valid_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "UyAI-Broker/1.0",
        }

        try:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=headers,
            )

            # Handle 401 Unauthorized -> Refresh and retry once
            if response.status_code == 401 and retry_on_401:
                logger.warning(
                    "amoCRM returned 401 Unauthorized. Forcing token refresh and retrying once."
                )
                new_token = await self.token_manager.force_refresh()
                headers["Authorization"] = f"Bearer {new_token}"
                return await self.request(
                    method=method,
                    endpoint=endpoint,
                    params=params,
                    json_data=json_data,
                    retry_on_401=False,
                )

            # Handle 429 Too Many Requests
            if response.status_code == 429:
                retry_after_str = response.headers.get("Retry-After", "60")
                try:
                    retry_after = float(retry_after_str)
                except ValueError:
                    retry_after = 60.0
                # Clamp between 1.0 and 3600.0 seconds
                retry_after = min(max(retry_after, 1.0), 3600.0)
                logger.warning("amoCRM rate limit hit. Retry-After: %.1fs", retry_after)
                raise AmoCRMRateLimitError(
                    f"amoCRM rate limit exceeded (HTTP 429). Retry after {retry_after}s.",
                    retry_after=retry_after,
                )

            # Handle 400 Bad Request / 422 Unprocessable
            if response.status_code in (400, 422):
                logger.error(
                    "amoCRM validation error HTTP %d on %s", response.status_code, endpoint
                )
                try:
                    err_json = response.json()
                    detail = str(err_json.get("detail") or err_json.get("title") or err_json)
                except Exception:
                    detail = response.text[:200]
                raise AmoCRMValidationError(
                    f"amoCRM rejected request (HTTP {response.status_code}): {detail}"
                )

            # Handle 403 Forbidden / 404 Not Found
            if response.status_code in (403, 404):
                raise AmoCRMPermanentError(
                    f"amoCRM permanent failure (HTTP {response.status_code}) on {endpoint}"
                )

            # Handle 5xx Server Error
            if response.status_code >= 500:
                raise AmoCRMTemporaryError(
                    f"amoCRM server error (HTTP {response.status_code}) on {endpoint}"
                )

            # If 204 No Content
            if response.status_code == 204:
                return {}

            return response.json()

        except httpx.TimeoutException as e:
            raise AmoCRMTemporaryError(f"amoCRM request timed out on {endpoint}") from e
        except httpx.NetworkError as e:
            raise AmoCRMTemporaryError(
                f"amoCRM network error on {endpoint}: {type(e).__name__}"
            ) from e
        except (
            AmoCRMDisabledError,
            AmoCRMAuthError,
            AmoCRMRateLimitError,
            AmoCRMValidationError,
            AmoCRMPermanentError,
            AmoCRMTemporaryError,
        ):
            raise
        except Exception as e:
            raise AmoCRMTemporaryError(
                f"Unexpected error calling amoCRM: {type(e).__name__}"
            ) from e

    async def find_contact_by_phone(self, phone: str) -> str | None:
        """Search existing contact by phone query to reconcile crash windows."""
        try:
            data = await self.request("GET", CONTACTS_ENDPOINT, params={"query": phone})
            embedded = data.get("_embedded", {})
            contacts = embedded.get("contacts", [])
            if contacts and contacts[0].get("id"):
                return str(contacts[0]["id"])
        except Exception as e:
            logger.debug("Failed to query contact by phone: %s", e)
        return None

    async def find_lead_by_title(self, title: str) -> str | None:
        """Search existing lead by title query to reconcile crash windows."""
        try:
            data = await self.request("GET", LEADS_ENDPOINT, params={"query": title})
            embedded = data.get("_embedded", {})
            leads = embedded.get("leads", [])
            if leads and leads[0].get("id"):
                return str(leads[0]["id"])
        except Exception as e:
            logger.debug("Failed to query lead by title: %s", e)
        return None

    async def create_contact(self, contact_payload: dict[str, Any]) -> str:
        """Create new contact in amoCRM. Returns external contact ID string."""
        # amoCRM v4 accepts batch: array of contacts
        payload = [contact_payload]
        data = await self.request("POST", CONTACTS_ENDPOINT, json_data=payload)
        embedded = data.get("_embedded", {})
        contacts = embedded.get("contacts", [])
        if not contacts or not contacts[0].get("id"):
            raise AmoCRMValidationError("amoCRM contact creation did not return an ID.")
        return str(contacts[0]["id"])

    async def create_lead(self, lead_payload: dict[str, Any]) -> str:
        """Create new lead in amoCRM. Returns external lead ID string."""
        payload = [lead_payload]
        data = await self.request("POST", LEADS_ENDPOINT, json_data=payload)
        embedded = data.get("_embedded", {})
        leads = embedded.get("leads", [])
        if not leads or not leads[0].get("id"):
            raise AmoCRMValidationError("amoCRM lead creation did not return an ID.")
        return str(leads[0]["id"])

    async def update_lead(self, external_lead_id: str, update_payload: dict[str, Any]) -> None:
        """Update existing lead in amoCRM."""
        endpoint = f"{LEADS_ENDPOINT}/{external_lead_id}"
        await self.request("PATCH", endpoint, json_data=update_payload)

    async def add_lead_note(self, external_lead_id: str, note_text: str) -> None:
        """Attach note to existing lead in amoCRM."""
        endpoint = f"{LEADS_ENDPOINT}/{external_lead_id}/notes"
        payload = [{"note_type": "common", "params": {"text": note_text}}]
        await self.request("POST", endpoint, json_data=payload)

    async def get_pipeline_statuses(self, pipeline_id: int | None = None) -> dict[str, int]:
        """Fetch pipeline statuses from amoCRM."""
        endpoint = f"{PIPELINES_ENDPOINT}/{pipeline_id}" if pipeline_id else PIPELINES_ENDPOINT
        data = await self.request("GET", endpoint)
        statuses: dict[str, int] = {}
        # Parse statuses if present
        if "_embedded" in data and "statuses" in data["_embedded"]:
            for item in data["_embedded"]["statuses"]:
                statuses[item.get("name", "")] = int(item["id"])
        return statuses
