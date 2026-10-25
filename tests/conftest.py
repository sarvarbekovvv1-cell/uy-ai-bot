"""Pytest configuration and shared fixtures."""

import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Ensure test environment settings
os.environ["APP_ENV"] = "testing"
os.environ["APP_DEBUG"] = "true"
os.environ["BOT_TOKEN"] = ""
os.environ["LOG_LEVEL"] = "INFO"

from app.config import get_settings
from app.main import app


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Provide asynchronous HTTP test client bound to FastAPI application."""
    get_settings.cache_clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
