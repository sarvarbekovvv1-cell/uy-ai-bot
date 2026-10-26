"""Unit tests for amoCRM OAuth 2.0 token management and concurrency control."""

import asyncio
import time
from unittest.mock import AsyncMock

import httpx
import pytest

from app.config import Settings
from app.integrations.amocrm.auth import TokenManager
from app.integrations.amocrm.client import AmoCRMClient
from app.integrations.amocrm.exceptions import (
    AmoCRMAuthError,
    AmoCRMDisabledError,
    AmoCRMPermanentError,
    AmoCRMRateLimitError,
    AmoCRMTemporaryError,
)


@pytest.fixture
def amocrm_settings() -> Settings:
    """Provide Settings configured for amoCRM testing."""
    return Settings(
        AMOCRM_ENABLED=True,
        AMOCRM_BASE_URL="https://test-agency.amocrm.ru",
        AMOCRM_CLIENT_ID="mock_client_id_123",
        AMOCRM_CLIENT_SECRET="mock_client_secret_xyz",
        AMOCRM_REFRESH_TOKEN="mock_refresh_token_abc",
        AMOCRM_ACCESS_TOKEN="initial_mock_access_token",
    )


@pytest.mark.asyncio
async def test_token_freshness_and_validity(amocrm_settings: Settings) -> None:
    """Test valid initial token does not trigger unnecessary refresh."""
    manager = TokenManager(settings=amocrm_settings)
    manager._expires_at = time.time() + 3600  # valid for 1 hour

    token = await manager.get_valid_access_token()
    assert token == "initial_mock_access_token"


@pytest.mark.asyncio
async def test_token_proactive_refresh_when_near_expiry(amocrm_settings: Settings) -> None:
    """Test token refreshes proactively when within 60s expiration buffer."""
    manager = TokenManager(settings=amocrm_settings)
    manager._expires_at = time.time() + 30.0  # within 60s buffer

    mock_resp = {
        "token_type": "Bearer",
        "expires_in": 86400,
        "access_token": "new_refreshed_access_token",
        "refresh_token": "new_rotated_refresh_token",
    }

    mock_client = AsyncMock()
    mock_response = httpx.Response(
        200, json=mock_resp, request=httpx.Request("POST", "https://test")
    )
    mock_client.post.return_value = mock_response
    manager._http_client = mock_client

    token = await manager.get_valid_access_token()
    assert token == "new_refreshed_access_token"
    assert manager._refresh_token == "new_rotated_refresh_token"
    mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_concurrent_refresh_single_flight(amocrm_settings: Settings) -> None:
    """Test that multiple concurrent coroutines execute only a single refresh network request."""
    manager = TokenManager(settings=amocrm_settings)
    manager._expires_at = 0.0  # Expired
    manager._access_token = ""

    mock_resp = {
        "token_type": "Bearer",
        "expires_in": 86400,
        "access_token": "single_flight_access_token",
        "refresh_token": "single_flight_refresh_token",
    }

    call_count = 0

    async def mock_post(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)  # Simulate network latency
        return httpx.Response(200, json=mock_resp, request=httpx.Request("POST", "https://test"))

    mock_client = AsyncMock()
    mock_client.post.side_effect = mock_post
    manager._http_client = mock_client

    # Fire 5 concurrent refresh requests
    tasks = [manager.get_valid_access_token() for _ in range(5)]
    tokens = await asyncio.gather(*tasks)

    assert all(t == "single_flight_access_token" for t in tokens)
    assert call_count == 1  # Exactly ONE HTTP POST executed due to asyncio.Lock


@pytest.mark.asyncio
async def test_refresh_rejection_raises_auth_error(amocrm_settings: Settings) -> None:
    """Test 400/401 from OAuth endpoint raises AmoCRMAuthError."""
    manager = TokenManager(settings=amocrm_settings)
    manager._access_token = ""

    mock_client = AsyncMock()
    mock_client.post.return_value = httpx.Response(
        400, json={"error": "invalid_grant"}, request=httpx.Request("POST", "https://test")
    )
    manager._http_client = mock_client

    with pytest.raises(AmoCRMAuthError) as exc_info:
        await manager.force_refresh()
    assert "Token refresh rejected" in str(exc_info.value)


@pytest.mark.asyncio
async def test_refresh_5xx_raises_temporary_error(amocrm_settings: Settings) -> None:
    """Test 5xx from OAuth endpoint raises AmoCRMTemporaryError."""
    manager = TokenManager(settings=amocrm_settings)
    manager._access_token = ""

    mock_client = AsyncMock()
    mock_client.post.return_value = httpx.Response(
        502, text="Bad Gateway", request=httpx.Request("POST", "https://test")
    )
    manager._http_client = mock_client

    with pytest.raises(AmoCRMTemporaryError) as exc_info:
        await manager.force_refresh()
    assert "amoCRM OAuth server error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_token_manager_disabled_raises_error() -> None:
    """Test that disabled setting raises AmoCRMDisabledError."""
    settings = Settings(AMOCRM_ENABLED=False)
    manager = TokenManager(settings=settings)
    with pytest.raises(AmoCRMDisabledError):
        await manager.get_valid_access_token()


def test_token_cache_atomic_and_permissions(tmp_path) -> None:
    """Test that persisting tokens creates file with restricted 0o600 permissions."""
    import stat

    cache_file = tmp_path / "subdir" / "tokens.json"
    settings = Settings(
        AMOCRM_ENABLED=True,
        AMOCRM_BASE_URL="https://test.amocrm.ru",
        AMOCRM_CLIENT_ID="cid",
        AMOCRM_CLIENT_SECRET="csec",
        AMOCRM_REFRESH_TOKEN="refr_123",
        AMOCRM_ACCESS_TOKEN="acc_123",
    )
    manager = TokenManager(settings=settings, cache_file=cache_file)
    manager._expires_at = time.time() + 3600
    manager._save_cached_tokens()

    assert cache_file.exists()
    # Check file mode
    mode = stat.S_IMODE(cache_file.stat().st_mode)
    assert mode == 0o600


@pytest.mark.asyncio
async def test_zero_secret_leak_in_exceptions() -> None:
    """Test Canary secrets (client_secret, refresh_token) are never leaked in exception messages."""
    canary_secret = "CANARY_SECRET_XYZ_9999"
    canary_token = "CANARY_REFRESH_TOKEN_8888"
    settings = Settings(
        AMOCRM_ENABLED=True,
        AMOCRM_BASE_URL="https://test.amocrm.ru",
        AMOCRM_CLIENT_ID="mock_cid",
        AMOCRM_CLIENT_SECRET=canary_secret,
        AMOCRM_REFRESH_TOKEN=canary_token,
        AMOCRM_ACCESS_TOKEN="",
    )
    manager = TokenManager(settings=settings)

    mock_client = AsyncMock()
    mock_client.post.return_value = httpx.Response(
        400, json={"error": "invalid_grant"}, request=httpx.Request("POST", "https://test")
    )
    manager._http_client = mock_client

    with pytest.raises(AmoCRMAuthError) as exc_info:
        await manager.force_refresh()

    msg = str(exc_info.value)
    assert canary_secret not in msg
    assert canary_token not in msg


@pytest.mark.asyncio
async def test_client_blocks_ssrf_and_untrusted_domains() -> None:
    """Test client blocks SSRF attempts and untrusted domains in production environment."""
    # Untrusted domain in production
    settings = Settings(
        _env_file=None,
        APP_ENV="production",
        APP_DEBUG=False,
        BOT_TOKEN="test-prod-bot-token",
        DATABASE_PASSWORD="secure_strong_password_123",
        DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/db",
        ADMIN_SESSION_COOKIE_SECURE=True,
        ADMIN_SESSION_SECRET="a" * 32,
        AMOCRM_ENABLED=True,
        AMOCRM_CLIENT_ID="mock_client_id",
        AMOCRM_CLIENT_SECRET="mock_client_secret",
        AMOCRM_BASE_URL="https://malicious-attacker.com",
        AMOCRM_ACCESS_TOKEN="mock_token",
    )
    client = AmoCRMClient(settings=settings)
    with pytest.raises(AmoCRMPermanentError) as exc_info:
        await client.request("GET", "/api/v4/leads")
    assert "not a trusted amoCRM/Kommo domain" in str(exc_info.value)

    # Valid domain passes validation
    valid_settings = Settings(
        _env_file=None,
        APP_ENV="production",
        APP_DEBUG=False,
        BOT_TOKEN="test-prod-bot-token",
        DATABASE_PASSWORD="secure_strong_password_123",
        DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/db",
        ADMIN_SESSION_COOKIE_SECURE=True,
        ADMIN_SESSION_SECRET="a" * 32,
        AMOCRM_ENABLED=True,
        AMOCRM_CLIENT_ID="mock_client_id",
        AMOCRM_CLIENT_SECRET="mock_client_secret",
        AMOCRM_BASE_URL="https://mycompany.amocrm.ru",
        AMOCRM_ACCESS_TOKEN="mock_token",
    )
    valid_client = AmoCRMClient(settings=valid_settings)
    # validate_base_url should not raise
    valid_client._validate_base_url(valid_settings.get_effective_amocrm_base_url())


@pytest.mark.asyncio
async def test_client_clamps_retry_after(amocrm_settings: Settings) -> None:
    """Test client parses and safely clamps Retry-After headers to [1.0, 3600.0]s."""
    mock_client = AsyncMock()
    # Return 429 with extreme Retry-After 999999
    mock_client.request.return_value = httpx.Response(
        429,
        headers={"Retry-After": "999999"},
        request=httpx.Request("GET", "https://test.amocrm.ru"),
    )
    client = AmoCRMClient(settings=amocrm_settings, http_client=mock_client)

    with pytest.raises(AmoCRMRateLimitError) as exc_info:
        await client.request("GET", "/api/v4/leads")
    assert exc_info.value.retry_after == 3600.0  # Clamped to max

    # Return 429 with negative Retry-After -10
    mock_client.request.return_value = httpx.Response(
        429,
        headers={"Retry-After": "-10"},
        request=httpx.Request("GET", "https://test.amocrm.ru"),
    )
    with pytest.raises(AmoCRMRateLimitError) as exc_info2:
        await client.request("GET", "/api/v4/leads")
    assert exc_info2.value.retry_after == 1.0  # Clamped to min
