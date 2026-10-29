"""Admin API endpoints for managing payment card details and valuation pricing tiers."""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.models.user import User
from app.repositories.payment_card_setting_repository import PaymentCardSettingRepository
from app.services.admin_rbac import PERM_DASHBOARD_VIEW, require_permission

router = APIRouter(prefix="/payment-settings", tags=["admin-payment-settings"])

check_payment_settings_perm = require_permission(PERM_DASHBOARD_VIEW)


class PaymentCardSettingRead(BaseModel):
    """Schema for reading payment card settings."""

    card_number: str
    card_holder: str
    standard_price_uzs: Decimal
    premium_price_uzs: Decimal
    is_active: bool
    updated_at: datetime

    class Config:
        from_attributes = True


class PaymentCardSettingUpdate(BaseModel):
    """Schema for updating payment card settings."""

    card_number: str | None = Field(default=None, max_length=32)
    card_holder: str | None = Field(default=None, max_length=128)
    standard_price_uzs: Decimal | None = Field(default=None, ge=0)
    premium_price_uzs: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None


@router.get("", response_model=PaymentCardSettingRead)
async def get_payment_settings(
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(check_payment_settings_perm),
) -> PaymentCardSettingRead:
    """Get active payment card and valuation pricing settings."""
    repo = PaymentCardSettingRepository()
    setting = await repo.get_setting(session)
    return PaymentCardSettingRead(
        card_number=setting.card_number,
        card_holder=setting.card_holder,
        standard_price_uzs=setting.standard_price_uzs,
        premium_price_uzs=setting.premium_price_uzs,
        is_active=setting.is_active,
        updated_at=setting.updated_at,
    )


@router.put("", response_model=PaymentCardSettingRead)
async def update_payment_settings(
    payload: PaymentCardSettingUpdate,
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(check_payment_settings_perm),
) -> PaymentCardSettingRead:
    """Update payment card and valuation pricing settings."""
    if payload.card_number is not None and not payload.card_number.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Karta raqami bo'sh bo'lishi mumkin emas.",
        )

    repo = PaymentCardSettingRepository()
    setting = await repo.update_setting(
        session,
        card_number=payload.card_number,
        card_holder=payload.card_holder,
        standard_price_uzs=payload.standard_price_uzs,
        premium_price_uzs=payload.premium_price_uzs,
        is_active=payload.is_active,
    )
    await session.commit()
    return PaymentCardSettingRead(
        card_number=setting.card_number,
        card_holder=setting.card_holder,
        standard_price_uzs=setting.standard_price_uzs,
        premium_price_uzs=setting.premium_price_uzs,
        is_active=setting.is_active,
        updated_at=setting.updated_at,
    )
