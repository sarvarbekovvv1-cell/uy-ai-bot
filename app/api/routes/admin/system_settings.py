"""Admin API endpoints for system settings including professional broker phone."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.models.user import User
from app.repositories.system_setting_repository import (
    KEY_BROKER_PHONE,
    SystemSettingRepository,
)
from app.services.admin_rbac import PERM_DASHBOARD_VIEW, require_permission

router = APIRouter(prefix="/system-settings", tags=["admin-system-settings"])

check_settings_perm = require_permission(PERM_DASHBOARD_VIEW)


class BrokerPhoneSettingRead(BaseModel):
    """Schema for reading professional broker phone setting."""

    broker_phone: str
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class BrokerPhoneSettingUpdate(BaseModel):
    """Schema for updating professional broker phone setting."""

    broker_phone: str = Field(..., min_length=5, max_length=32)


@router.get("/broker-phone", response_model=BrokerPhoneSettingRead)
async def get_broker_phone(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(check_settings_perm),
) -> BrokerPhoneSettingRead:
    """Get the active professional broker contact phone number."""
    repo = SystemSettingRepository()
    phone = await repo.get_broker_phone(session)
    setting = await repo.get_setting_obj(session, KEY_BROKER_PHONE)
    return BrokerPhoneSettingRead(
        broker_phone=phone,
        updated_at=setting.updated_at if setting else None,
    )


@router.put("/broker-phone", response_model=BrokerPhoneSettingRead)
async def update_broker_phone(
    payload: BrokerPhoneSettingUpdate,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(check_settings_perm),
) -> BrokerPhoneSettingRead:
    """Update professional broker contact phone number."""
    repo = SystemSettingRepository()
    try:
        formatted = await repo.set_broker_phone(session, payload.broker_phone)
        await session.commit()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(e),
        ) from e

    setting = await repo.get_setting_obj(session, KEY_BROKER_PHONE)
    return BrokerPhoneSettingRead(
        broker_phone=formatted,
        updated_at=setting.updated_at if setting else None,
    )
