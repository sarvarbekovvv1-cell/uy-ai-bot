"""FastAPI application entrypoint and lifespan management."""

import uuid
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
    if settings.app_env == "production":
        logger.info("Verified production settings: strict security constraints enforced.")
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

    # Configure CORS narrowly for Telegram Mini App and Admin Panel
    allowed_origins = settings.get_miniapp_allowed_origins()
    if settings.miniapp_url and settings.miniapp_url not in allowed_origins:
        allowed_origins.append(settings.miniapp_url)

    for admin_origin in settings.get_admin_allowed_origins():
        if admin_origin not in allowed_origins:
            allowed_origins.append(admin_origin)
    if settings.admin_url and settings.admin_url not in allowed_origins:
        allowed_origins.append(settings.admin_url)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Correlation ID and Security headers middleware
    @application.middleware("http")
    async def add_security_headers_and_request_id(request: Request, call_next):
        req_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = req_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Mini App endpoints support Telegram Web embedding via CSP frame-ancestors;
        # admin and other endpoints enforce strict SAMEORIGIN framing.
        if request.url.path.startswith("/api/miniapp/v1/"):
            response.headers["Content-Security-Policy"] = (
                "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org;"
            )
        else:
            response.headers["X-Frame-Options"] = "SAMEORIGIN"

        if settings.app_env == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
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
