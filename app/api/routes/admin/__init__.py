"""Admin / Manager Panel API router package."""

from fastapi import APIRouter

from app.api.routes.admin.audit import router as audit_router
from app.api.routes.admin.auth import router as auth_router
from app.api.routes.admin.brokers import router as brokers_router
from app.api.routes.admin.crm import router as crm_router
from app.api.routes.admin.dashboard import router as dashboard_router
from app.api.routes.admin.leads import router as leads_router
from app.api.routes.admin.properties import router as properties_router
from app.api.routes.admin.users import router as users_router
from app.api.routes.admin.viewings import router as viewings_router

admin_router = APIRouter(prefix="/api/admin/v1")

admin_router.include_router(auth_router)
admin_router.include_router(dashboard_router)
admin_router.include_router(properties_router)
admin_router.include_router(users_router)
admin_router.include_router(brokers_router)
admin_router.include_router(leads_router)
admin_router.include_router(viewings_router)
admin_router.include_router(crm_router)
admin_router.include_router(audit_router)

__all__ = ["admin_router"]
