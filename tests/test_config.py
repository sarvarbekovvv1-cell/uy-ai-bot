"""Tests for centralized application configuration."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_default_configuration_loads() -> None:
    """Verify that default settings load cleanly without missing required fields."""
    settings = Settings(
        APP_ENV="testing",
        BOT_TOKEN="",
    )
    assert settings.app_name == "UyAI"
    assert settings.app_env == "testing"
    assert settings.app_port == 8000
    assert settings.database_url is not None
    assert "postgresql+asyncpg://" in settings.database_url


def test_custom_database_url_assembly() -> None:
    """Verify database URL is constructed from components if not explicitly provided."""
    settings = Settings(
        APP_ENV="testing",
        DATABASE_HOST="db.internal",
        DATABASE_PORT=5433,
        DATABASE_NAME="custom_uyai",
        DATABASE_USER="custom_user",
        DATABASE_PASSWORD="secure_custom_password",
    )
    assert (
        settings.database_url
        == "postgresql+asyncpg://custom_user:secure_custom_password@db.internal:5433/custom_uyai"
    )


def test_invalid_log_level_rejected() -> None:
    """Verify that an invalid log level raises a validation error."""
    with pytest.raises(ValidationError):
        Settings(LOG_LEVEL="INVALID_LEVEL")


def test_production_environment_requires_bot_token() -> None:
    """Verify that production environment fails clearly when BOT_TOKEN is empty."""
    with pytest.raises(ValidationError, match="BOT_TOKEN must be set"):
        Settings(
            APP_ENV="production",
            BOT_TOKEN="",
            DATABASE_PASSWORD="very_secure_production_password",
        )


def test_production_environment_rejects_default_password() -> None:
    """Verify that production environment rejects default or insecure database password."""
    with pytest.raises(ValidationError, match="DATABASE_PASSWORD must be configured"):
        Settings(
            APP_ENV="production",
            BOT_TOKEN="123456789:ABCdefGhIJKlmNoPQRstuVWXyz",
            DATABASE_PASSWORD="uyai_password",
        )


def test_alembic_configuration_loads() -> None:
    """Verify that alembic.ini and migrations directory load properly."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    assert script.dir == "migrations"
