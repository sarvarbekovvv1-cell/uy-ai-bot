"""FastAPI application entrypoint and lifespan management."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.config import get_settings
from app.database.session import close_db_engine
from app.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan events."""
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("Starting %s in %s mode", settings.app_name, settings.app_env)
    yield
    logger.info("Shutting down %s", settings.app_name)
    await close_db_engine()


def create_application() -> FastAPI:
    """Application factory for FastAPI."""
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug,
        lifespan=lifespan,
    )

    # Configure CORS narrowly for Telegram Mini App
    allowed_origins = [o.strip() for o in settings.miniapp_allowed_origins.split(",") if o.strip()]
    if settings.miniapp_url and settings.miniapp_url not in allowed_origins:
        allowed_origins.append(settings.miniapp_url)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Security headers middleware
    @application.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # Global safe error handler - prevents leaking stack traces or internal secrets
    @application.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Unhandled server exception during %s %s: %s",
            request.method,
            request.url.path,
            exc.__class__.__name__,
            exc_info=settings.app_debug,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": "An internal server error occurred."},
        )

    # Root endpoint required by specification
    @application.get("/", summary="Root application status", tags=["Root"])
    async def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "status": "running",
        }

    # Mount API routes (including /health and /health/db)
    application.include_router(api_router)

    return application


app = create_application()
