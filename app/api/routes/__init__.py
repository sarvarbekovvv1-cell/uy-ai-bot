"""API routes aggregation."""

from fastapi import APIRouter

from app.api.routes.amocrm import router as amocrm_router
from app.api.routes.health import router as health_router
from app.api.routes.miniapp import router as miniapp_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(miniapp_router)
api_router.include_router(amocrm_router)

__all__ = ["api_router"]
