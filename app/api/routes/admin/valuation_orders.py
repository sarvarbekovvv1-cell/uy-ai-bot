"""Admin API routes for valuation orders, receipts verification, and approval."""

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.bot.handlers.valuation import format_valuation_result_card, get_valuation_service
from app.config import get_settings
from app.logging import get_logger
from app.models.admin_auth import AdminAuditEvent
from app.models.user import User
from app.repositories.valuation_order_repository import ValuationOrderRepository
from app.schemas.valuation import PropertyValuationInput
from app.services.admin_rbac import PERM_DASHBOARD_VIEW, require_permission

logger = get_logger(__name__)

router = APIRouter(prefix="/valuation-orders", tags=["Admin Valuation Orders"])

check_valuation_order_perm = require_permission(PERM_DASHBOARD_VIEW)


class ApproveOrderPayload(BaseModel):
    """Payload for approving a valuation order receipt."""

    notes: str | None = Field(default=None, max_length=500)


class RejectOrderPayload(BaseModel):
    """Payload for rejecting a valuation order receipt."""

    reason: str = Field(min_length=2, max_length=500)


async def _notify_customer_telegram(telegram_id: int, text: str) -> None:
    """Best-effort async delivery of notification to customer's Telegram chat."""
    settings = get_settings()
    token = getattr(settings, "bot_token", None) or getattr(settings, "telegram_bot_token", None)
    if not token or not telegram_id:
        return

    try:
        from aiogram import Bot

        bot = Bot(token=token)
        try:
            await bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML")
        finally:
            await bot.session.close()
    except Exception as exc:
        logger.warning("Failed to send Telegram notification to user %s: %s", telegram_id, exc)


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
            "package_type": o.package_type,
            "payment_provider": o.payment_provider,
            "provider_trans_id": o.provider_trans_id,
            "payment_status": o.payment_status,
            "valuation_status": o.valuation_status,
            "receipt_file_id": o.receipt_file_id,
            "receipt_analysis": o.receipt_analysis,
            "admin_notes": o.admin_notes,
            "approved_by_user_id": o.approved_by_user_id,
            "reviewed_at": o.reviewed_at.isoformat() if o.reviewed_at else None,
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
    """Retrieve full details of a valuation order including input, analysis and result."""
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
        "package_type": order.package_type,
        "payment_provider": order.payment_provider,
        "provider_trans_id": order.provider_trans_id,
        "payment_status": order.payment_status,
        "valuation_status": order.valuation_status,
        "receipt_file_id": order.receipt_file_id,
        "receipt_analysis": order.receipt_analysis,
        "admin_notes": order.admin_notes,
        "approved_by_user_id": order.approved_by_user_id,
        "reviewed_at": order.reviewed_at.isoformat() if order.reviewed_at else None,
        "property_input": order.property_input,
        "valuation_result": order.valuation_result,
        "error_message": order.error_message,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


@router.post("/{order_id}/approve")
async def approve_valuation_order(
    order_id: str,
    payload: ApproveOrderPayload | None = None,
    session: AsyncSession = Depends(get_db_session),
    _staff: User = Depends(check_valuation_order_perm),
) -> dict[str, Any]:
    """Approve a valuation order receipt, mark as paid, execute AI valuation, and deliver report."""
    repo = ValuationOrderRepository()
    order = await repo.get_by_order_id(session, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Valuation order '{order_id}' not found.",
        )

    if order.payment_status == "paid":
        return {
            "status": "already_approved",
            "order_id": order.order_id,
            "payment_status": order.payment_status,
            "valuation_status": order.valuation_status,
        }

    admin_notes = payload.notes if payload else None

    # 1. Transition to paid
    await repo.mark_approved(
        session,
        order_id,
        admin_user_id=_staff.id,
        admin_notes=admin_notes,
    )

    # 2. Immutable audit log
    audit_event = AdminAuditEvent(
        actor_user_id=_staff.id,
        action="valuation_order.approve",
        entity_type="valuation_order",
        entity_id=order.id,
        safe_metadata_json=json.dumps(
            {
                "order_id": order.order_id,
                "amount_uzs": float(order.amount_uzs),
                "package_type": order.package_type,
                "admin_notes": admin_notes,
            }
        ),
    )
    session.add(audit_event)
    await session.flush()

    # 3. Execute AI property valuation for customer's chosen package
    val_service = get_valuation_service()
    val_input = PropertyValuationInput.model_validate(order.property_input)
    val_result = await val_service.valuate_property(session, val_input, language="uz")

    await repo.set_valuation_result(
        session,
        order_id,
        valuation_status="completed",
        valuation_result=val_result.model_dump(mode="json"),
    )
    await session.commit()
    await session.refresh(order)

    # 4. Proactive Telegram delivery to customer
    card_text = format_valuation_result_card(
        val_input,
        val_result,
        lang="uz",
        package=order.package_type,
    )
    delivery_text = (
        "🎉 <b>To‘lovingiz tasdiqlandi!</b>\n"
        f"<b>Buyurtma ID:</b> <code>{order.order_id}</code>\n"
        f"<b>Tarif:</b> {order.package_type.capitalize()}\n\n"
        f"{card_text}"
    )
    await _notify_customer_telegram(order.telegram_id, delivery_text)

    return {
        "status": "approved",
        "order_id": order.order_id,
        "payment_status": order.payment_status,
        "valuation_status": order.valuation_status,
        "valuation_result": order.valuation_result,
    }


@router.post("/{order_id}/reject")
async def reject_valuation_order(
    order_id: str,
    payload: RejectOrderPayload,
    session: AsyncSession = Depends(get_db_session),
    _staff: User = Depends(check_valuation_order_perm),
) -> dict[str, Any]:
    """Reject a valuation order receipt with reason, notify customer, and log audit event."""
    repo = ValuationOrderRepository()
    order = await repo.get_by_order_id(session, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Valuation order '{order_id}' not found.",
        )

    if order.payment_status == "rejected":
        return {
            "status": "already_rejected",
            "order_id": order.order_id,
            "payment_status": order.payment_status,
            "admin_notes": order.admin_notes,
        }

    if order.payment_status == "paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="To'lov tasdiqlangan buyurtmani rad etib bo'lmaydi.",
        )

    await repo.mark_rejected(
        session,
        order_id,
        admin_user_id=_staff.id,
        admin_notes=payload.reason,
    )

    # Immutable audit log
    audit_event = AdminAuditEvent(
        actor_user_id=_staff.id,
        action="valuation_order.reject",
        entity_type="valuation_order",
        entity_id=order.id,
        safe_metadata_json=json.dumps(
            {
                "order_id": order.order_id,
                "amount_uzs": float(order.amount_uzs),
                "reason": payload.reason,
            }
        ),
    )
    session.add(audit_event)
    await session.commit()
    await session.refresh(order)

    # Notify customer of rejection
    rejection_text = (
        "❌ <b>To‘lov chekingiz tasdiqlanmadi</b>\n\n"
        f"• <b>Buyurtma ID:</b> <code>{order.order_id}</code>\n"
        f"• <b>Sabab:</b> {payload.reason}\n\n"
        "Iltimos, to‘lov ma'lumotlarini tekshirib, botga to‘g‘ri chekni qayta yuboring "
        "yoki qo‘llab-quvvatlash xizmati bilan bog‘laning."
    )
    await _notify_customer_telegram(order.telegram_id, rejection_text)

    return {
        "status": "rejected",
        "order_id": order.order_id,
        "payment_status": order.payment_status,
        "admin_notes": order.admin_notes,
    }
