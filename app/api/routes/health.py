"""Health check endpoints for system and database connectivity."""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.database.session import check_database_connection

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Basic service health check")
async def health_check() -> dict[str, str]:
    """Return basic service health status."""
    return {"status": "ok"}


@router.get("/health/db", summary="Database connectivity health check")
async def database_health_check() -> JSONResponse:
    """Check and return database connectivity status."""
    is_connected = await check_database_connection()
    if is_connected:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ok", "database": "connected"},
        )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "error", "database": "disconnected"},
    )
