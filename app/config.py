"""Centralized application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application settings
    app_name: str = Field(default="UyAI", alias="APP_NAME")
    app_env: Literal["development", "testing", "production"] = Field(
        default="development", alias="APP_ENV"
    )
    app_debug: bool = Field(default=False, alias="APP_DEBUG")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")

    # Telegram Bot configuration
    bot_token: str = Field(default="", alias="BOT_TOKEN")

    # Database configuration
    database_host: str = Field(default="localhost", alias="DATABASE_HOST")
    database_port: int = Field(default=5432, alias="DATABASE_PORT")
    database_name: str = Field(default="uyai_db", alias="DATABASE_NAME")
    database_user: str = Field(default="uyai_user", alias="DATABASE_USER")
    database_password: str = Field(default="uyai_password", alias="DATABASE_PASSWORD")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Gemini AI Broker
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-3.6-flash", alias="GEMINI_MODEL")
    ai_broker_enabled: bool = Field(default=False, alias="AI_BROKER_ENABLED")
    ai_request_timeout_seconds: float = Field(default=30.0, alias="AI_REQUEST_TIMEOUT_SECONDS")
    ai_max_history_messages: int = Field(default=6, alias="AI_MAX_HISTORY_MESSAGES")
    ai_max_search_results: int = Field(default=5, alias="AI_MAX_SEARCH_RESULTS")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        val_upper = value.upper()
        if val_upper not in valid_levels:
            raise ValueError(f"Invalid LOG_LEVEL '{value}'. Expected one of {valid_levels}")
        return val_upper

    @model_validator(mode="after")
    def assemble_and_validate(self) -> "Settings":
        # Compute database_url if not explicitly provided
        if not self.database_url:
            self.database_url = (
                f"postgresql+asyncpg://{self.database_user}:{self.database_password}@"
                f"{self.database_host}:{self.database_port}/{self.database_name}"
            )

        # In production, enforce non-empty credentials and secure tokens
        if self.app_env == "production":
            if not self.bot_token or self.bot_token.strip() == "":
                raise ValueError("BOT_TOKEN must be set in production environment.")
            if not self.database_password or self.database_password in ("uyai_password", ""):
                raise ValueError(
                    "DATABASE_PASSWORD must be configured with a secure value in production."
                )

        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
