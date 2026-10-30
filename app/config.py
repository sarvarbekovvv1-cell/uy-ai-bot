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

    # Telegram Mini App Configuration
    miniapp_url: str = Field(default="", alias="MINIAPP_URL")
    miniapp_allowed_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173",
        alias="MINIAPP_ALLOWED_ORIGINS",
    )
    telegram_init_data_max_age_seconds: int = Field(
        default=86400, alias="TELEGRAM_INIT_DATA_MAX_AGE_SECONDS"
    )
    miniapp_dev_auth_enabled: bool = Field(default=False, alias="MINIAPP_DEV_AUTH_ENABLED")

    # amoCRM Integration Configuration
    amocrm_enabled: bool = Field(default=False, alias="AMOCRM_ENABLED")
    amocrm_base_url: str = Field(default="", alias="AMOCRM_BASE_URL")
    amocrm_subdomain: str = Field(default="", alias="AMOCRM_SUBDOMAIN")
    amocrm_client_id: str = Field(default="", alias="AMOCRM_CLIENT_ID")
    amocrm_client_secret: str = Field(default="", alias="AMOCRM_CLIENT_SECRET")
    amocrm_redirect_uri: str = Field(default="", alias="AMOCRM_REDIRECT_URI")
    amocrm_access_token: str = Field(default="", alias="AMOCRM_ACCESS_TOKEN")
    amocrm_refresh_token: str = Field(default="", alias="AMOCRM_REFRESH_TOKEN")
    amocrm_pipeline_id: int | None = Field(default=None, alias="AMOCRM_PIPELINE_ID")
    amocrm_default_responsible_user_id: int | None = Field(
        default=None, alias="AMOCRM_DEFAULT_RESPONSIBLE_USER_ID"
    )
    amocrm_request_timeout_seconds: float = Field(
        default=10.0, alias="AMOCRM_REQUEST_TIMEOUT_SECONDS"
    )
    amocrm_max_retries: int = Field(default=5, alias="AMOCRM_MAX_RETRIES")
    amocrm_webhook_secret: str = Field(default="", alias="AMOCRM_WEBHOOK_SECRET")
    amocrm_stage_mapping_json: str = Field(default="", alias="AMOCRM_STAGE_MAPPING_JSON")
    amocrm_broker_mapping_json: str = Field(default="", alias="AMOCRM_BROKER_MAPPING_JSON")

    # Admin Panel Configuration
    admin_url: str = Field(default="http://localhost:5174", alias="ADMIN_URL")
    admin_allowed_origins: str = Field(
        default="http://localhost:5174,http://127.0.0.1:5174", alias="ADMIN_ALLOWED_ORIGINS"
    )
    admin_session_max_age_seconds: int = Field(default=28800, alias="ADMIN_SESSION_MAX_AGE_SECONDS")
    admin_session_cookie_name: str = Field(
        default="uyai_admin_session", alias="ADMIN_SESSION_COOKIE_NAME"
    )
    admin_session_cookie_secure: bool = Field(default=False, alias="ADMIN_SESSION_COOKIE_SECURE")
    admin_session_secret: str = Field(default="", alias="ADMIN_SESSION_SECRET")

    # Persistent Media Storage Configuration
    media_storage_dir: str = Field(default=".cache/media", alias="MEDIA_STORAGE_DIR")

    # System & Broker Configuration
    broker_phone: str = Field(default="+998 71 200 00 00", alias="BROKER_PHONE")

    # Payment & Monetization Configuration
    valuation_price_uzs: int = Field(default=0, alias="VALUATION_PRICE_UZS")
    valuation_card_number: str = Field(default="", alias="VALUATION_CARD_NUMBER")
    valuation_cardholder: str = Field(default="", alias="VALUATION_CARDHOLDER")
    valuation_price_basic_uzs: int = Field(default=50000, alias="VALUATION_PRICE_BASIC_UZS")
    valuation_price_standard_uzs: int = Field(default=65000, alias="VALUATION_PRICE_STANDARD_UZS")
    valuation_price_premium_uzs: int = Field(default=90000, alias="VALUATION_PRICE_PREMIUM_UZS")
    click_service_id: str = Field(default="", alias="CLICK_SERVICE_ID")
    click_merchant_id: str = Field(default="", alias="CLICK_MERCHANT_ID")
    click_secret_key: str = Field(default="", alias="CLICK_SECRET_KEY")
    click_merchant_user_id: str = Field(default="", alias="CLICK_MERCHANT_USER_ID")
    payme_merchant_id: str = Field(default="", alias="PAYME_MERCHANT_ID")
    payme_secret_key: str = Field(default="", alias="PAYME_SECRET_KEY")
    payme_test_mode: bool = Field(default=True, alias="PAYME_TEST_MODE")
    payment_return_url: str = Field(default="", alias="PAYMENT_RETURN_URL")

    def get_admin_allowed_origins(self) -> list[str]:
        """Return list of allowed CORS origins for Admin Panel."""
        if not self.admin_allowed_origins:
            return []
        raw = self.admin_allowed_origins.strip()
        if raw.startswith("[") and raw.endswith("]"):
            try:
                import json

                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(o).strip() for o in parsed if str(o).strip()]
            except Exception:
                pass
        return [o.strip() for o in raw.split(",") if o.strip()]

    def get_miniapp_allowed_origins(self) -> list[str]:
        """Return list of allowed CORS origins for Mini App."""
        if not self.miniapp_allowed_origins:
            return []
        raw = self.miniapp_allowed_origins.strip()
        if raw.startswith("[") and raw.endswith("]"):
            try:
                import json

                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(o).strip() for o in parsed if str(o).strip()]
            except Exception:
                pass
        return [o.strip() for o in raw.split(",") if o.strip()]

    def get_effective_amocrm_base_url(self) -> str:
        """Return canonical amoCRM base URL without trailing slash."""
        if self.amocrm_base_url and self.amocrm_base_url.strip():
            return self.amocrm_base_url.strip().rstrip("/")
        if self.amocrm_subdomain and self.amocrm_subdomain.strip():
            return f"https://{self.amocrm_subdomain.strip()}.amocrm.ru"
        return ""

    def get_amocrm_stage_mapping(self) -> dict[str, int]:
        """Return mapping of internal Lead stage to amoCRM status_id."""
        if not self.amocrm_stage_mapping_json or not self.amocrm_stage_mapping_json.strip():
            return {}
        try:
            import json

            raw = json.loads(self.amocrm_stage_mapping_json)
            if isinstance(raw, dict):
                return {str(k): int(v) for k, v in raw.items()}
        except Exception:
            pass
        return {}

    def get_amocrm_broker_mapping(self) -> dict[int, int]:
        """Return mapping of local broker user_id to amoCRM responsible_user_id."""
        if not self.amocrm_broker_mapping_json or not self.amocrm_broker_mapping_json.strip():
            return {}
        try:
            import json

            raw = json.loads(self.amocrm_broker_mapping_json)
            if isinstance(raw, dict):
                return {int(k): int(v) for k, v in raw.items()}
        except Exception:
            pass
        return {}

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
        import os

        # Support cloud PaaS standard PORT environment variable
        if "PORT" in os.environ and os.environ["PORT"].strip():
            try:
                self.app_port = int(os.environ["PORT"].strip())
            except ValueError:
                pass

        # Normalize database_url protocol for asyncpg if provided
        if self.database_url:
            db_url = self.database_url.strip()
            if db_url.startswith("postgres://"):
                db_url = "postgresql+asyncpg://" + db_url[len("postgres://"):]
            elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+asyncpg://"):
                db_url = "postgresql+asyncpg://" + db_url[len("postgresql://"):]
            self.database_url = db_url

        # Compute database_url if not explicitly provided
        if not self.database_url:
            self.database_url = (
                f"postgresql+asyncpg://{self.database_user}:{self.database_password}@"
                f"{self.database_host}:{self.database_port}/{self.database_name}"
            )

        # In production, enforce fail-fast security constraints
        if self.app_env == "production":
            if not self.bot_token or self.bot_token.strip() == "":
                raise ValueError("BOT_TOKEN must be set in production environment.")

            if not self.database_password or self.database_password in ("uyai_password", ""):
                raise ValueError(
                    "DATABASE_PASSWORD must be configured with a secure value in production."
                )

            if self.app_debug:
                raise ValueError("APP_DEBUG must be False in production.")

            if "sqlite" in (self.database_url or "").lower():
                raise ValueError("SQLite is prohibited in production. Configure PostgreSQL.")

            if self.miniapp_dev_auth_enabled:
                raise ValueError("MINIAPP_DEV_AUTH_ENABLED must be False in production.")

            if not self.admin_session_cookie_secure:
                raise ValueError("ADMIN_SESSION_COOKIE_SECURE must be True in production.")

            if len(self.admin_session_secret.strip()) < 32:
                raise ValueError(
                    "ADMIN_SESSION_SECRET must be at least 32 characters long in production."
                )

            if "*" in self.admin_allowed_origins or "*" in self.miniapp_allowed_origins:
                raise ValueError("Wildcard '*' CORS origins are strictly prohibited.")

            if self.ai_broker_enabled and not self.gemini_api_key.strip():
                raise ValueError("GEMINI_API_KEY must be provided when AI_BROKER_ENABLED is True.")

            if self.amocrm_enabled:
                if not self.amocrm_client_id or not self.amocrm_client_secret:
                    raise ValueError(
                        "AMOCRM_CLIENT_ID and AMOCRM_CLIENT_SECRET are required "
                        "when AMOCRM_ENABLED is True."
                    )
                if not self.amocrm_subdomain and not self.amocrm_base_url:
                    raise ValueError(
                        "AMOCRM_SUBDOMAIN or AMOCRM_BASE_URL is required "
                        "when AMOCRM_ENABLED is True."
                    )

        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
