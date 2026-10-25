"""Tests for FastAPI foundation and health endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient) -> None:
    """Verify GET / returns expected foundation status."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "UyAI"
    assert data["status"] == "running"


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient) -> None:
    """Verify GET /health returns status ok."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_db_connected(async_client: AsyncClient) -> None:
    """Verify GET /health/db returns connected status when database ping succeeds."""
    with patch(
        "app.api.routes.health.check_database_connection",
        new=AsyncMock(return_value=True),
    ):
        response = await async_client.get("/health/db")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "connected"}


@pytest.mark.asyncio
async def test_health_db_disconnected(async_client: AsyncClient) -> None:
    """Verify GET /health/db returns 503 service unavailable when database ping fails."""
    with patch(
        "app.api.routes.health.check_database_connection",
        new=AsyncMock(return_value=False),
    ):
        response = await async_client.get("/health/db")
        assert response.status_code == 503
        data = response.json()
        assert data == {"status": "error", "database": "disconnected"}
        # Ensure no secrets or tracebacks are leaked
        assert "password" not in response.text
        assert "Traceback" not in response.text
