"""Admin API routes for managing and reporting valuation orders and payments."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.models.user import User
from app.repositories.valuation_order_repository import ValuationOrderRepository
from app.services.admin_rbac import PERM_DASHBOARD_VIEW, require_permission

router = APIRouter(prefix="/valuation-orders", tags=["Admin Valuation Orders"])

check_valuation_order_perm = require_permission(PERM_DASHBOARD_VIEW)


@router.get("")
async def list_valuation_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    payment_status: str | None = None,
    valuation_status: str | None = None,
    session: AsyncSession = Depends(get_db_session),
    _staff: User = Depends(check_valuation_order_perm),
) -> dict[str, Any]:
    """List valuation orders with status filters and pagination."""
    repo = ValuationOrderRepository()
    offset = (page - 1) * page_size
    orders, total = await repo.list_orders(
        session,
        payment_status=payment_status,
        valuation_status=valuation_status,
        limit=page_size,
        offset=offset,
    )

    items = [
        {
            "id": o.id,
            "order_id": o.order_id,
            "user_id": o.user_id,
            "telegram_id": o.telegram_id,
            "amount_uzs": float(o.amount_uzs),
            "currency": o.currency,
            "payment_provider": o.payment_provider,
            "provider_trans_id": o.provider_trans_id,
            "payment_status": o.payment_status,
            "valuation_status": o.valuation_status,
            "paid_at": o.paid_at.isoformat() if o.paid_at else None,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in orders
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{order_id}")
async def get_valuation_order_detail(
    order_id: str,
    session: AsyncSession = Depends(get_db_session),
    _staff: User = Depends(check_valuation_order_perm),
) -> dict[str, Any]:
    """Retrieve full details of a valuation order including input and result."""
    repo = ValuationOrderRepository()
    order = await repo.get_by_order_id(session, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Valuation order '{order_id}' not found.",
        )

    return {
        "id": order.id,
        "order_id": order.order_id,
        "user_id": order.user_id,
        "telegram_id": order.telegram_id,
        "amount_uzs": float(order.amount_uzs),
        "currency": order.currency,
        "payment_provider": order.payment_provider,
        "provider_trans_id": order.provider_trans_id,
        "payment_status": order.payment_status,
        "valuation_status": order.valuation_status,
        "property_input": order.property_input,
        "valuation_result": order.valuation_result,
        "error_message": order.error_message,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }
