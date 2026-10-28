"""FastAPI webhook routes for Click and Payme payment gateways."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.config import get_settings
from app.logging import get_logger
from app.repositories.payment_transaction_repository import PaymentTransactionRepository
from app.repositories.valuation_order_repository import ValuationOrderRepository
from app.services.payment.click_service import (
    CLICK_ERROR_ACTION_NOT_FOUND,
    CLICK_ERROR_ALREADY_PAID,
    CLICK_ERROR_INVALID_AMOUNT,
    CLICK_ERROR_ORDER_NOT_FOUND,
    CLICK_ERROR_SIGN_CHECK_FAILED,
    CLICK_ERROR_SUCCESS,
    CLICK_ERROR_TRANSACTION_CANCELLED,
    CLICK_ERROR_TRANSACTION_NOT_FOUND,
    ClickPaymentService,
)
from app.services.payment.payme_service import (
    PAYME_ERR_AUTH_FAILED,
    PAYME_ERR_INVALID_AMOUNT,
    PAYME_ERR_INVALID_PARAMS,
    PAYME_ERR_METHOD_NOT_FOUND,
    PAYME_ERR_ORDER_NOT_FOUND,
    PAYME_ERR_ORDER_STATE_INVALID,
    PAYME_ERR_TRANSACTION_NOT_FOUND,
    PAYME_ERR_UNABLE_CANCEL,
    PAYME_STATE_CANCELLED,
    PAYME_STATE_CANCELLED_AFTER_PERFORM,
    PAYME_STATE_CREATED,
    PAYME_STATE_PERFORMED,
    PaymePaymentService,
)
from app.services.payment.valuation_payment_service import ValuationPaymentService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


# ---------------------------------------------------------------------------
# Click Shop API Webhook (action=0 Prepare, action=1 Complete)
# ---------------------------------------------------------------------------


@router.post("/click/webhook")
@router.post("/click/prepare")
@router.post("/click/complete")
async def click_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Process incoming Click Shop API requests (Prepare & Complete)."""
    settings = get_settings()
    click_svc = ClickPaymentService(settings)

    # Click can send urlencoded form data or json
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            data = await request.json()
        except Exception:
            data = {}
    else:
        body_bytes = await request.body()
        if body_bytes:
            from urllib.parse import parse_qs

            raw_str = body_bytes.decode("utf-8")
            if raw_str.strip().startswith("{"):
                import json

                try:
                    data = json.loads(raw_str)
                except Exception:
                    data = {}
            else:
                parsed = parse_qs(raw_str)
                data = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
        else:
            data = {}

    click_trans_id = str(data.get("click_trans_id", ""))
    service_id = str(data.get("service_id", ""))
    merchant_trans_id = str(data.get("merchant_trans_id", ""))
    merchant_prepare_id = str(data.get("merchant_prepare_id", ""))
    amount_str = str(data.get("amount", ""))
    action_str = str(data.get("action", ""))
    sign_time = str(data.get("sign_time", ""))
    sign_string = str(data.get("sign_string", ""))
    error_code = int(data.get("error", 0))

    order_repo = ValuationOrderRepository()
    tx_repo = PaymentTransactionRepository()
    val_pay_svc = ValuationPaymentService(settings=settings, order_repo=order_repo)

    # Action 0: Prepare
    if action_str == "0":
        if not click_svc.verify_prepare_signature(
            click_trans_id=click_trans_id,
            service_id=service_id,
            merchant_trans_id=merchant_trans_id,
            amount=amount_str,
            action=action_str,
            sign_time=sign_time,
            sign_string=sign_string,
        ):
            logger.warning("Click prepare signature verification failed: %s", merchant_trans_id)
            return {
                "click_trans_id": click_trans_id,
                "merchant_trans_id": merchant_trans_id,
                "merchant_prepare_id": 0,
                "error": CLICK_ERROR_SIGN_CHECK_FAILED,
                "error_note": "SIGN CHECK FAILED!",
            }

        order = await order_repo.get_by_order_id(session, merchant_trans_id)
        if not order:
            logger.warning("Click order not found: %s", merchant_trans_id)
            return {
                "click_trans_id": click_trans_id,
                "merchant_trans_id": merchant_trans_id,
                "merchant_prepare_id": 0,
                "error": CLICK_ERROR_ORDER_NOT_FOUND,
                "error_note": "Order not found",
            }

        try:
            req_amount = Decimal(amount_str)
        except Exception:
            req_amount = Decimal("-1")

        if req_amount != order.amount_uzs:
            logger.warning(
                "Click amount mismatch for %s: expected %s, got %s",
                merchant_trans_id,
                order.amount_uzs,
                req_amount,
            )
            return {
                "click_trans_id": click_trans_id,
                "merchant_trans_id": merchant_trans_id,
                "merchant_prepare_id": 0,
                "error": CLICK_ERROR_INVALID_AMOUNT,
                "error_note": "Incorrect parameter amount",
            }

        if order.payment_status == "paid":
            return {
                "click_trans_id": click_trans_id,
                "merchant_trans_id": merchant_trans_id,
                "merchant_prepare_id": 0,
                "error": CLICK_ERROR_ALREADY_PAID,
                "error_note": "Already paid",
            }

        # Save or get transaction log
        tx = await tx_repo.get_by_provider_trans_id(session, "click", click_trans_id)
        if not tx:
            tx = await tx_repo.create_transaction(
                session,
                order_id=order.id,
                provider="click",
                provider_trans_id=click_trans_id,
                amount=order.amount_uzs,
                state="prepare",
                raw_payload=data,
            )

        return {
            "click_trans_id": click_trans_id,
            "merchant_trans_id": merchant_trans_id,
            "merchant_prepare_id": tx.id,
            "error": CLICK_ERROR_SUCCESS,
            "error_note": "Success",
        }

    # Action 1: Complete
    elif action_str == "1":
        if not click_svc.verify_complete_signature(
            click_trans_id=click_trans_id,
            service_id=service_id,
            merchant_trans_id=merchant_trans_id,
            merchant_prepare_id=merchant_prepare_id,
            amount=amount_str,
            action=action_str,
            sign_time=sign_time,
            sign_string=sign_string,
        ):
            logger.warning("Click complete signature verification failed: %s", merchant_trans_id)
            return {
                "click_trans_id": click_trans_id,
                "merchant_trans_id": merchant_trans_id,
                "merchant_confirm_id": 0,
                "error": CLICK_ERROR_SIGN_CHECK_FAILED,
                "error_note": "SIGN CHECK FAILED!",
            }

        order = await order_repo.get_by_order_id(session, merchant_trans_id)
        if not order:
            return {
                "click_trans_id": click_trans_id,
                "merchant_trans_id": merchant_trans_id,
                "merchant_confirm_id": 0,
                "error": CLICK_ERROR_ORDER_NOT_FOUND,
                "error_note": "Order not found",
            }

        tx = await tx_repo.get_by_provider_trans_id(session, "click", click_trans_id)
        if not tx:
            return {
                "click_trans_id": click_trans_id,
                "merchant_trans_id": merchant_trans_id,
                "merchant_confirm_id": 0,
                "error": CLICK_ERROR_TRANSACTION_NOT_FOUND,
                "error_note": "Transaction not found",
            }

        if error_code < 0:
            await tx_repo.update_state(
                session,
                tx,
                state="cancelled",
                error_code=error_code,
                error_note=data.get("error_note"),
            )
            return {
                "click_trans_id": click_trans_id,
                "merchant_trans_id": merchant_trans_id,
                "merchant_confirm_id": tx.id,
                "error": CLICK_ERROR_TRANSACTION_CANCELLED,
                "error_note": "Transaction cancelled",
            }

        # Idempotent complete
        if tx.state == "complete" or order.payment_status == "paid":
            return {
                "click_trans_id": click_trans_id,
                "merchant_trans_id": merchant_trans_id,
                "merchant_confirm_id": tx.id,
                "error": CLICK_ERROR_SUCCESS,
                "error_note": "Success",
            }

        now = datetime.now(UTC)
        await tx_repo.update_state(session, tx, state="complete", perform_time=now)
        await order_repo.mark_paid(session, merchant_trans_id, "click", click_trans_id)

        # Trigger valuation execution & notification
        bot_instance = getattr(request.app.state, "bot", None)
        await val_pay_svc.fulfill_order_and_valuate(session, merchant_trans_id, bot=bot_instance)

        return {
            "click_trans_id": click_trans_id,
            "merchant_trans_id": merchant_trans_id,
            "merchant_confirm_id": tx.id,
            "error": CLICK_ERROR_SUCCESS,
            "error_note": "Success",
        }

    return {
        "click_trans_id": click_trans_id,
        "merchant_trans_id": merchant_trans_id,
        "merchant_confirm_id": 0,
        "error": CLICK_ERROR_ACTION_NOT_FOUND,
        "error_note": "Action not found",
    }


# ---------------------------------------------------------------------------
# Payme Merchant JSON-RPC 2.0 Webhook
# ---------------------------------------------------------------------------


def make_payme_error(req_id: Any, code: int, message_uz: str, message_ru: str) -> dict[str, Any]:
    """Helper to format JSON-RPC 2.0 error response for Payme."""
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {
            "code": code,
            "message": {
                "uz": message_uz,
                "ru": message_ru,
                "en": message_ru,
            },
        },
    }


@router.post("/payme")
async def payme_webhook(
    request: Request,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Process incoming Payme JSON-RPC 2.0 merchant requests."""
    settings = get_settings()
    payme_svc = PaymePaymentService(settings)

    try:
        body = await request.json()
    except Exception:
        return make_payme_error(None, -32700, "JSON formati noto‘g‘ri", "Неверный формат JSON")

    req_id = body.get("id")
    method = body.get("method")
    params = body.get("params") or {}

    # Basic Auth authentication
    if not payme_svc.verify_basic_auth(authorization):
        logger.warning("Payme Basic Auth failed")
        return make_payme_error(
            req_id,
            PAYME_ERR_AUTH_FAILED,
            "Autentifikatsiya xatosi",
            "Ошибка аутентификации",
        )

    order_repo = ValuationOrderRepository()
    tx_repo = PaymentTransactionRepository()
    val_pay_svc = ValuationPaymentService(settings=settings, order_repo=order_repo)

    # 1. CheckPerformTransaction
    if method == "CheckPerformTransaction":
        account = params.get("account") or {}
        order_id = account.get("order_id")
        amount = params.get("amount")

        if not order_id or amount is None:
            return make_payme_error(
                req_id,
                PAYME_ERR_INVALID_PARAMS,
                "Parametrlar to‘liq emas",
                "Недостаточно параметров",
            )

        order = await order_repo.get_by_order_id(session, order_id)
        if not order:
            return make_payme_error(
                req_id,
                PAYME_ERR_ORDER_NOT_FOUND,
                "Buyurtma topilmadi",
                "Заказ не найден",
            )

        expected_tiyin = int(order.amount_uzs * 100)
        if int(amount) != expected_tiyin:
            return make_payme_error(
                req_id,
                PAYME_ERR_INVALID_AMOUNT,
                "Noto‘g‘ri summa",
                "Неверная сумма",
            )

        if order.payment_status != "pending":
            return make_payme_error(
                req_id,
                PAYME_ERR_ORDER_STATE_INVALID,
                "Buyurtma kutilayotgan holatda emas",
                "Заказ не в состоянии ожидания",
            )

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"allow": True},
        }

    # 2. CreateTransaction
    elif method == "CreateTransaction":
        payme_trans_id = str(params.get("id", ""))
        time_ms = int(params.get("time", 0))
        amount = params.get("amount")
        account = params.get("account") or {}
        order_id = account.get("order_id")

        if not payme_trans_id or not order_id or amount is None:
            return make_payme_error(
                req_id,
                PAYME_ERR_INVALID_PARAMS,
                "Parametrlar to‘liq emas",
                "Недостаточно параметров",
            )

        order = await order_repo.get_by_order_id(session, order_id)
        if not order:
            return make_payme_error(
                req_id,
                PAYME_ERR_ORDER_NOT_FOUND,
                "Buyurtma topilmadi",
                "Заказ не найден",
            )

        expected_tiyin = int(order.amount_uzs * 100)
        if int(amount) != expected_tiyin:
            return make_payme_error(
                req_id,
                PAYME_ERR_INVALID_AMOUNT,
                "Noto‘g‘ri summa",
                "Неверная сумма",
            )

        tx = await tx_repo.get_by_provider_trans_id(session, "payme", payme_trans_id)
        if tx:
            # Check if active
            tx_create_time_ms = int(tx.created_at.timestamp() * 1000)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "create_time": tx_create_time_ms,
                    "transaction": str(tx.id),
                    "state": (
                        PAYME_STATE_CREATED
                        if tx.state == "created"
                        else (
                            PAYME_STATE_PERFORMED
                            if tx.state == "performed"
                            else PAYME_STATE_CANCELLED
                        )
                    ),
                },
            }

        # Create new transaction
        new_tx = await tx_repo.create_transaction(
            session,
            order_id=order.id,
            provider="payme",
            provider_trans_id=payme_trans_id,
            amount=order.amount_uzs,
            state="created",
            raw_payload=params,
        )
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "create_time": time_ms,
                "transaction": str(new_tx.id),
                "state": PAYME_STATE_CREATED,
            },
        }

    # 3. PerformTransaction
    elif method == "PerformTransaction":
        payme_trans_id = str(params.get("id", ""))
        tx = await tx_repo.get_by_provider_trans_id(session, "payme", payme_trans_id)
        if not tx:
            return make_payme_error(
                req_id,
                PAYME_ERR_TRANSACTION_NOT_FOUND,
                "Tranzaksiya topilmadi",
                "Транзакция не найдена",
            )

        if tx.state == "performed":
            perform_ms = int(tx.perform_time.timestamp() * 1000) if tx.perform_time else 0
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "transaction": str(tx.id),
                    "perform_time": perform_ms,
                    "state": PAYME_STATE_PERFORMED,
                },
            }

        if tx.state != "created":
            return make_payme_error(
                req_id,
                PAYME_ERR_UNABLE_CANCEL,
                "Tranzaksiyani bajarish imkonsiz",
                "Невозможно выполнить транзакцию",
            )

        now = datetime.now(UTC)
        await tx_repo.update_state(session, tx, state="performed", perform_time=now)

        order = await order_repo.get_by_id(session, tx.order_id)
        if order:
            await order_repo.mark_paid(session, order.order_id, "payme", payme_trans_id)
            bot_instance = getattr(request.app.state, "bot", None)
            await val_pay_svc.fulfill_order_and_valuate(
                session, order.order_id, bot=bot_instance
            )

        perform_ms = int(now.timestamp() * 1000)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "transaction": str(tx.id),
                "perform_time": perform_ms,
                "state": PAYME_STATE_PERFORMED,
            },
        }

    # 4. CancelTransaction
    elif method == "CancelTransaction":
        payme_trans_id = str(params.get("id", ""))
        reason = params.get("reason", 1)

        tx = await tx_repo.get_by_provider_trans_id(session, "payme", payme_trans_id)
        if not tx:
            return make_payme_error(
                req_id,
                PAYME_ERR_TRANSACTION_NOT_FOUND,
                "Tranzaksiya topilmadi",
                "Транзакция не найдена",
            )

        now = datetime.now(UTC)
        new_state = (
            PAYME_STATE_CANCELLED
            if tx.state == "created"
            else PAYME_STATE_CANCELLED_AFTER_PERFORM
        )
        await tx_repo.update_state(
            session,
            tx,
            state="cancelled",
            cancel_time=now,
            cancel_reason=reason,
        )

        cancel_ms = int(now.timestamp() * 1000)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "transaction": str(tx.id),
                "cancel_time": cancel_ms,
                "state": new_state,
            },
        }

    # 5. CheckTransaction
    elif method == "CheckTransaction":
        payme_trans_id = str(params.get("id", ""))
        tx = await tx_repo.get_by_provider_trans_id(session, "payme", payme_trans_id)
        if not tx:
            return make_payme_error(
                req_id,
                PAYME_ERR_TRANSACTION_NOT_FOUND,
                "Tranzaksiya topilmadi",
                "Транзакция не найдена",
            )

        create_ms = int(tx.created_at.timestamp() * 1000)
        perform_ms = int(tx.perform_time.timestamp() * 1000) if tx.perform_time else 0
        cancel_ms = int(tx.cancel_time.timestamp() * 1000) if tx.cancel_time else 0
        state = (
            PAYME_STATE_CREATED
            if tx.state == "created"
            else (
                PAYME_STATE_PERFORMED
                if tx.state == "performed"
                else PAYME_STATE_CANCELLED
            )
        )

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "create_time": create_ms,
                "perform_time": perform_ms,
                "cancel_time": cancel_ms,
                "transaction": str(tx.id),
                "state": state,
                "reason": tx.cancel_reason,
            },
        }

    return make_payme_error(
        req_id,
        PAYME_ERR_METHOD_NOT_FOUND,
        "Metod topilmadi",
        "Метод не найден",
    )
