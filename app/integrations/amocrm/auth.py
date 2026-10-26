"""OAuth 2.0 token management and single-flight refresh for amoCRM."""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings
from app.integrations.amocrm.constants import OAUTH_TOKEN_ENDPOINT
from app.integrations.amocrm.exceptions import (
    AmoCRMAuthError,
    AmoCRMDisabledError,
    AmoCRMTemporaryError,
)
from app.logging import get_logger

logger = get_logger(__name__)

CACHE_DIR = Path(".cache")
TOKEN_CACHE_FILE = CACHE_DIR / "amocrm_tokens.json"


class TokenManager:
    """Thread-safe and coroutine-safe OAuth 2.0 token manager for amoCRM.

    Features:
    - Single-flight refresh via asyncio.Lock prevents concurrent refresh storms.
    - 60-second proactive expiration buffer prevents mid-flight 401s.
    - Token storage in local runtime cache (.cache/amocrm_tokens.json) with fallback to settings.
    - Zero secret leakage in logs or exceptions.
    """

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
        cache_file: Path | None = None,
    ) -> None:
        self.settings = settings
        self._http_client = client
        self._lock = asyncio.Lock()
        self._cache_file = (
            cache_file
            if cache_file is not None
            else (TOKEN_CACHE_FILE if settings.app_env != "testing" else None)
        )

        # In-memory token state
        self._access_token: str = settings.amocrm_access_token or ""
        self._refresh_token: str = settings.amocrm_refresh_token or ""
        self._expires_at: float = 0.0

        # Load persisted tokens from local cache if available
        self._load_cached_tokens()

    def _load_cached_tokens(self) -> None:
        """Load rotated tokens from local gitignored cache if present."""
        if self._cache_file and self._cache_file.exists():
            try:
                data = json.loads(self._cache_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    if data.get("refresh_token"):
                        self._refresh_token = data["refresh_token"]
                    if data.get("access_token"):
                        self._access_token = data["access_token"]
                    if data.get("expires_at"):
                        self._expires_at = float(data["expires_at"])
            except Exception as e:
                logger.warning("Failed to load amoCRM tokens from cache: %s", type(e).__name__)

    def _save_cached_tokens(self) -> None:
        """Persist rotated tokens to local cache file atomically with restricted permissions."""
        if not self._cache_file:
            return
        try:
            parent = self._cache_file.parent
            parent.mkdir(parents=True, exist_ok=True)
            try:
                parent.chmod(0o700)
            except OSError:
                pass

            data = {
                "access_token": self._access_token,
                "refresh_token": self._refresh_token,
                "expires_at": self._expires_at,
                "updated_at": time.time(),
            }
            content = json.dumps(data)

            # Atomic write via temporary file in the same directory
            tmp_path = parent / f"{self._cache_file.name}.tmp.{os.getpid()}"
            fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                with open(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                    f.flush()
                    os.fsync(fd)
            except Exception:
                try:
                    os.unlink(str(tmp_path))
                except OSError:
                    pass
                raise

            os.replace(str(tmp_path), str(self._cache_file))
            try:
                self._cache_file.chmod(0o600)
            except OSError:
                pass
        except Exception as e:
            logger.warning("Failed to persist amoCRM tokens to cache: %s", type(e).__name__)

    @property
    def has_credentials(self) -> bool:
        """Check if minimum required credentials to authenticate exist."""
        return bool(
            self.settings.get_effective_amocrm_base_url()
            and self.settings.amocrm_client_id
            and self.settings.amocrm_client_secret
            and (self._refresh_token or self._access_token)
        )

    def is_access_token_valid(self) -> bool:
        """Check if current access token is present and not expired."""
        if not self._access_token:
            return False
        # If expires_at is set, check freshness with 60-second buffer
        if self._expires_at > 0:
            return time.time() < (self._expires_at - 60.0)
        # If expires_at is not tracked but token was loaded from settings, consider valid until 401
        return True

    async def get_valid_access_token(self) -> str:
        """Return valid access token, performing single-flight refresh if necessary."""
        if not self.settings.amocrm_enabled:
            raise AmoCRMDisabledError("amoCRM integration is disabled.")

        if self.is_access_token_valid():
            return self._access_token

        # Acquire lock to ensure only one refresh runs
        async with self._lock:
            # Re-check inside lock
            if self.is_access_token_valid():
                return self._access_token

            return await self._execute_token_refresh()

    async def force_refresh(self) -> str:
        """Force immediate refresh (e.g. after remote 401 Unauthorized response)."""
        async with self._lock:
            return await self._execute_token_refresh()

    async def _execute_token_refresh(self) -> str:
        """Execute token refresh request against amoCRM OAuth endpoint."""
        base_url = self.settings.get_effective_amocrm_base_url()
        if not base_url:
            raise AmoCRMAuthError("amoCRM base URL is not configured.")

        client_id = self.settings.amocrm_client_id
        client_secret = self.settings.amocrm_client_secret
        redirect_uri = self.settings.amocrm_redirect_uri or base_url

        if not client_id or not client_secret or not self._refresh_token:
            raise AmoCRMAuthError(
                "Missing required OAuth credentials (client_id, client_secret, or refresh_token)."
            )

        url = f"{base_url}{OAUTH_TOKEN_ENDPOINT}"
        payload: dict[str, Any] = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "redirect_uri": redirect_uri,
        }

        should_close = False
        client = self._http_client
        if client is None:
            client = httpx.AsyncClient(timeout=self.settings.amocrm_request_timeout_seconds)
            should_close = True

        try:
            logger.info("Executing amoCRM OAuth token refresh")
            response = await client.post(url, json=payload)
            if response.status_code == 400 or response.status_code == 401:
                logger.error("amoCRM token refresh rejected: HTTP %d", response.status_code)
                raise AmoCRMAuthError(
                    f"Token refresh rejected by amoCRM: HTTP {response.status_code}"
                )
            if response.status_code >= 500:
                raise AmoCRMTemporaryError(
                    f"amoCRM OAuth server error: HTTP {response.status_code}"
                )
            response.raise_for_status()

            data = response.json()
            new_access_token = data.get("access_token")
            new_refresh_token = data.get("refresh_token")
            expires_in = int(data.get("expires_in", 86400))

            if not new_access_token:
                raise AmoCRMAuthError("Response from amoCRM OAuth did not contain access_token.")

            self._access_token = new_access_token
            if new_refresh_token:
                self._refresh_token = new_refresh_token
            self._expires_at = time.time() + expires_in

            self._save_cached_tokens()
            logger.info(
                "Successfully refreshed and cached amoCRM access token (expires in %ds)",
                expires_in,
            )
            return self._access_token

        except httpx.TimeoutException as e:
            raise AmoCRMTemporaryError(
                f"amoCRM OAuth token refresh timed out: {type(e).__name__}"
            ) from e
        except httpx.NetworkError as e:
            raise AmoCRMTemporaryError(
                f"Network error during amoCRM token refresh: {type(e).__name__}"
            ) from e
        except (AmoCRMAuthError, AmoCRMTemporaryError):
            raise
        except Exception as e:
            raise AmoCRMAuthError(
                f"Unexpected error during amoCRM token refresh: {type(e).__name__}"
            ) from e
        finally:
            if should_close:
                await client.aclose()
