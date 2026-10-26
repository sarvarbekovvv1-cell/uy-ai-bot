"""Comprehensive test suite for Phase 13 Production Hardening, Config & Services."""

import pytest
from httpx import AsyncClient

from app.config import Settings
from app.services.media_storage import LocalMediaStorage
from app.services.rate_limiter import SlidingWindowRateLimiter

# -----------------------------------------------------------------------------
# 1. Production Configuration Fail-Fast Validation Tests
# -----------------------------------------------------------------------------
PROD_PG_URL = "postgresql+asyncpg://uyai_user:strong_prod_pass@localhost:5432/uyai_db"


def test_production_config_rejects_debug_true():
    with pytest.raises(ValueError, match="APP_DEBUG must be False in production"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            APP_DEBUG=True,
            DATABASE_URL=PROD_PG_URL,
            BOT_TOKEN="mock_prod_bot_token_valid",
            DATABASE_PASSWORD="strong_prod_password_12345",
            ADMIN_SESSION_COOKIE_SECURE=True,
            ADMIN_SESSION_SECRET="a" * 32,
            MINIAPP_DEV_AUTH_ENABLED=False,
        )


def test_production_config_rejects_sqlite():
    with pytest.raises(ValueError, match="SQLite is prohibited in production"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            APP_DEBUG=False,
            DATABASE_URL="sqlite+aiosqlite:///production.db",
            BOT_TOKEN="mock_prod_bot_token_valid",
            DATABASE_PASSWORD="strong_prod_password_12345",
            ADMIN_SESSION_COOKIE_SECURE=True,
            ADMIN_SESSION_SECRET="a" * 32,
            MINIAPP_DEV_AUTH_ENABLED=False,
        )


def test_production_config_rejects_miniapp_dev_auth():
    with pytest.raises(ValueError, match="MINIAPP_DEV_AUTH_ENABLED must be False in production"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            APP_DEBUG=False,
            DATABASE_URL=PROD_PG_URL,
            MINIAPP_DEV_AUTH_ENABLED=True,
            BOT_TOKEN="mock_prod_bot_token_valid",
            DATABASE_PASSWORD="strong_prod_password_12345",
            ADMIN_SESSION_COOKIE_SECURE=True,
            ADMIN_SESSION_SECRET="a" * 32,
        )


def test_production_config_rejects_insecure_cookie():
    with pytest.raises(ValueError, match="ADMIN_SESSION_COOKIE_SECURE must be True in production"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            APP_DEBUG=False,
            DATABASE_URL=PROD_PG_URL,
            ADMIN_SESSION_COOKIE_SECURE=False,
            BOT_TOKEN="mock_prod_bot_token_valid",
            DATABASE_PASSWORD="strong_prod_password_12345",
            ADMIN_SESSION_SECRET="a" * 32,
            MINIAPP_DEV_AUTH_ENABLED=False,
        )


def test_production_config_rejects_short_session_secret():
    with pytest.raises(ValueError, match="ADMIN_SESSION_SECRET must be at least 32 characters"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            APP_DEBUG=False,
            DATABASE_URL=PROD_PG_URL,
            ADMIN_SESSION_COOKIE_SECURE=True,
            ADMIN_SESSION_SECRET="short_secret",
            BOT_TOKEN="mock_prod_bot_token_valid",
            DATABASE_PASSWORD="strong_prod_password_12345",
            MINIAPP_DEV_AUTH_ENABLED=False,
        )


def test_production_config_rejects_wildcard_cors():
    with pytest.raises(ValueError, match="Wildcard '\\*' CORS origins are strictly prohibited"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            APP_DEBUG=False,
            DATABASE_URL=PROD_PG_URL,
            ADMIN_ALLOWED_ORIGINS="*",
            ADMIN_SESSION_COOKIE_SECURE=True,
            ADMIN_SESSION_SECRET="a" * 32,
            BOT_TOKEN="mock_prod_bot_token_valid",
            DATABASE_PASSWORD="strong_prod_password_12345",
            MINIAPP_DEV_AUTH_ENABLED=False,
        )


def test_production_config_rejects_missing_gemini_key_when_ai_enabled():
    with pytest.raises(ValueError, match="GEMINI_API_KEY must be provided"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            APP_DEBUG=False,
            DATABASE_URL=PROD_PG_URL,
            AI_BROKER_ENABLED=True,
            GEMINI_API_KEY="",
            ADMIN_SESSION_COOKIE_SECURE=True,
            ADMIN_SESSION_SECRET="a" * 32,
            BOT_TOKEN="mock_prod_bot_token_valid",
            DATABASE_PASSWORD="strong_prod_password_12345",
            MINIAPP_DEV_AUTH_ENABLED=False,
        )


def test_production_config_valid_passes():
    s = Settings(
        _env_file=None,
        APP_ENV="production",
        APP_DEBUG=False,
        DATABASE_URL=PROD_PG_URL,
        BOT_TOKEN="mock_prod_bot_token_valid",
        DATABASE_PASSWORD="strong_prod_password_12345",
        ADMIN_SESSION_COOKIE_SECURE=True,
        ADMIN_SESSION_SECRET="a" * 32,
        MINIAPP_DEV_AUTH_ENABLED=False,
    )
    assert s.app_env == "production"
    assert s.app_debug is False
    assert s.admin_session_cookie_secure is True


# -----------------------------------------------------------------------------
# 2. Rate Limiter Tests
# -----------------------------------------------------------------------------
def test_sliding_window_rate_limiter():
    limiter = SlidingWindowRateLimiter()
    key = "test_ip_127.0.0.1"

    # Allow up to 3 requests in 10-second window
    assert limiter.is_allowed(key, max_requests=3, window_seconds=10)[0] is True
    assert limiter.is_allowed(key, max_requests=3, window_seconds=10)[0] is True
    assert limiter.is_allowed(key, max_requests=3, window_seconds=10)[0] is True

    # 4th request must be rejected
    allowed, retry_after = limiter.is_allowed(key, max_requests=3, window_seconds=10)
    assert allowed is False
    assert retry_after >= 1

    # Reset
    limiter.reset(key)
    assert limiter.is_allowed(key, max_requests=3, window_seconds=10)[0] is True


@pytest.mark.asyncio
async def test_rate_limiter_dependency_enforcement(async_client: AsyncClient, monkeypatch):
    from app.services.rate_limiter import rate_limiter

    rate_limiter.reset()
    monkeypatch.setattr("app.services.rate_limiter.FORCE_RATE_LIMIT_IN_TESTS", True)

    # Hit admin login endpoint 10 times (max is 10)
    for _ in range(10):
        resp = await async_client.post(
            "/api/admin/v1/auth/login",
            json={"username": "test_rl", "password": "wrong_password"},
        )
        assert resp.status_code in (401, 404)

    # 11th request must receive 429
    resp_limit = await async_client.post(
        "/api/admin/v1/auth/login",
        json={"username": "test_rl", "password": "wrong_password"},
    )
    assert resp_limit.status_code == 429
    assert "Retry-After" in resp_limit.headers
    rate_limiter.reset()


# -----------------------------------------------------------------------------
# 3. Media Storage Abstraction Tests
# -----------------------------------------------------------------------------
def test_media_storage_lifecycle(tmp_path):
    storage = LocalMediaStorage(storage_dir=str(tmp_path))

    # 1. Empty content rejected
    with pytest.raises(ValueError, match="empty"):
        storage.save_media(b"", "image/jpeg")

    # 2. Invalid magic bytes rejected
    with pytest.raises(ValueError, match="magic bytes"):
        storage.save_media(b"not_an_image", "image/jpeg")

    # 3. Valid JPEG
    valid_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb"
    uid = storage.save_media(valid_jpeg, "image/jpeg")
    assert uid.startswith("admin_media_")

    # 4. Retrieve
    retrieved = storage.get_media(uid)
    assert retrieved is not None
    data, mime = retrieved
    assert data == valid_jpeg
    assert mime == "image/jpeg"

    # 5. Non-existent returns None
    assert storage.get_media("non_existent_uid") is None

    # 6. Delete
    assert storage.delete_media(uid) is True
    assert storage.get_media(uid) is None


# -----------------------------------------------------------------------------
# 4. HTTP Security Headers & Health Endpoints Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_security_headers_and_request_id(async_client: AsyncClient):
    resp = await async_client.get("/")
    assert resp.status_code == 200
    assert "x-request-id" in resp.headers
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert resp.headers["x-frame-options"] == "SAMEORIGIN"

    # Mini App routes support Telegram Web embedding via CSP frame-ancestors
    miniapp_resp = await async_client.get("/api/miniapp/v1/properties")
    assert miniapp_resp.status_code in (200, 401)
    assert "frame-ancestors" in miniapp_resp.headers.get("content-security-policy", "")
    assert "x-frame-options" not in miniapp_resp.headers


@pytest.mark.asyncio
async def test_health_endpoints(async_client: AsyncClient):
    # Liveness
    resp = await async_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

    # Readiness
    db_resp = await async_client.get("/health/db")
    assert db_resp.status_code in (200, 503)
    assert "database" in db_resp.json()
