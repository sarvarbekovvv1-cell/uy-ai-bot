"""Comprehensive integration tests for Monetized AI Property Valuation (Click & Payme)."""

import base64
import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.types import CallbackQuery, Chat, Message, Update
from aiogram.types import User as TgUser
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.dispatcher import create_dispatcher
from app.config import Settings
from app.main import app
from app.models.property import Property
from app.models.user import User
from app.repositories.role_repository import RoleRepository
from app.repositories.valuation_order_repository import ValuationOrderRepository
from app.schemas.valuation import PropertyValuationInput
from app.services.payment import (
    CLICK_ERROR_SIGN_CHECK_FAILED,
    CLICK_ERROR_SUCCESS,
    ValuationPaymentService,
)


def make_msg_update(user_id: int, text: str, update_id: int = 1) -> Update:
    from_user = TgUser(id=user_id, is_bot=False, first_name="MonetizeUser", username="mon_user")
    chat = Chat(id=user_id, type="private")
    msg = Message(
        message_id=update_id,
        date=datetime.now(UTC),
        chat=chat,
        from_user=from_user,
        text=text,
    )
    return Update(update_id=update_id, message=msg)


def make_cb_update(user_id: int, data: str, update_id: int = 2) -> Update:
    from_user = TgUser(id=user_id, is_bot=False, first_name="MonetizeUser", username="mon_user")
    chat = Chat(id=user_id, type="private")
    msg = Message(
        message_id=update_id,
        date=datetime.now(UTC),
        chat=chat,
        from_user=from_user,
        text="Previous message",
    )
    cb = CallbackQuery(
        id=f"cb_{update_id}",
        from_user=from_user,
        chat_instance="mon_instance",
        message=msg,
        data=data,
    )
    return Update(update_id=update_id, callback_query=cb)


def extract_bot_texts(mock_bot: AsyncMock) -> list[str]:
    texts = []
    for call in mock_bot.mock_calls:
        if call.args:
            obj = call.args[0]
            name = obj.__class__.__name__
            if name in ("SendMessage", "EditMessageText"):
                if hasattr(obj, "text") and obj.text:
                    texts.append(str(obj.text))
                elif hasattr(obj, "caption") and obj.caption:
                    texts.append(str(obj.caption))
    return texts


@pytest.fixture
async def setup_payment_test_data(db_session: AsyncSession) -> dict[str, Any]:
    """Seed customer and approved comparable properties for monetization tests."""
    role_repo = RoleRepository()
    await role_repo.ensure_default_roles(db_session)

    customer = User(
        telegram_id=980001,
        language="uz",
        first_name="CustomerOne",
        phone="+998901112233",
        consent_accepted_at=datetime.now(UTC),
    )
    customer2 = User(
        telegram_id=980002,
        language="uz",
        first_name="CustomerTwo",
        phone="+998909998877",
        consent_accepted_at=datetime.now(UTC),
    )
    db_session.add_all([customer, customer2])
    await db_session.flush()

    # Seed comparables
    comp1 = Property(
        owner_user_id=customer.id,
        listing_type="sale",
        property_type="apartment",
        title="2-room Chilonzor Comps 1",
        region="Toshkent shahri",
        district="Chilonzor",
        address="Chilonzor-1",
        rooms=2,
        total_area=Decimal("55"),
        condition="renovated",
        price=Decimal("55000"),
        currency="USD",
        status="approved",
    )
    comp2 = Property(
        owner_user_id=customer.id,
        listing_type="sale",
        property_type="apartment",
        title="2-room Chilonzor Comps 2",
        region="Toshkent shahri",
        district="Chilonzor",
        address="Chilonzor-2",
        rooms=2,
        total_area=Decimal("58"),
        condition="renovated",
        price=Decimal("57000"),
        currency="USD",
        status="approved",
    )
    db_session.add_all([comp1, comp2])
    await db_session.commit()

    return {
        "customer_id": customer.id,
        "customer_tg_id": customer.telegram_id,
        "customer2_tg_id": customer2.telegram_id,
    }


# ---------------------------------------------------------------------------
# 1. Unconfigured Payment Provider / Price Notice
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valuation_unconfigured_payment_shows_safe_notice(
    setup_payment_test_data: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    """When VALUATION_PRICE_UZS is 0 or unconfigured, bot returns safe notice."""
    cust_tg_id = setup_payment_test_data["customer_tg_id"]
    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    # Walk through input wizard
    await dp.feed_update(
        mock_bot, make_msg_update(cust_tg_id, "📊 Uyimni baholash", 1), session=db_session
    )
    await dp.feed_update(
        mock_bot, make_cb_update(cust_tg_id, "val_lt:sale", 2), session=db_session
    )
    await dp.feed_update(
        mock_bot, make_cb_update(cust_tg_id, "val_pt:apartment", 3), session=db_session
    )
    await dp.feed_update(
        mock_bot, make_cb_update(cust_tg_id, "val_dst:Chilonzor", 4), session=db_session
    )
    await dp.feed_update(
        mock_bot, make_cb_update(cust_tg_id, "val_rooms:2", 5), session=db_session
    )
    await dp.feed_update(mock_bot, make_msg_update(cust_tg_id, "56", 6), session=db_session)
    await dp.feed_update(
        mock_bot, make_cb_update(cust_tg_id, "val_cond:renovated", 7), session=db_session
    )
    await dp.feed_update(mock_bot, make_msg_update(cust_tg_id, "4/9", 8), session=db_session)

    # Currency selection with default (unconfigured) settings
    await dp.feed_update(
        mock_bot, make_cb_update(cust_tg_id, "val_curr:USD", 9), session=db_session
    )

    texts = extract_bot_texts(mock_bot)
    full_output = " ".join(texts)

    # Must contain safe explanation that service is paid and setup is in progress
    assert "rasmiy to‘lov tizimiga ulanmoqda" in full_output
    assert "Click va Payme" in full_output
    # Free calculation output must NOT be present
    assert "Taxminiy bozor bahosi:" not in full_output


# ---------------------------------------------------------------------------
# 2. Configured Payment: Order Creation & Checkout Links
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valuation_creates_order_and_renders_payment_options(
    setup_payment_test_data: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    """When price & providers are configured, completing wizard creates order."""
    cust_tg_id = setup_payment_test_data["customer_tg_id"]
    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    test_settings = Settings(
        VALUATION_PRICE_UZS=25000,
        CLICK_SERVICE_ID="12345",
        CLICK_MERCHANT_ID="67890",
        CLICK_SECRET_KEY="test_click_secret",
        PAYME_MERCHANT_ID="payme_merchant_123",
        PAYME_SECRET_KEY="test_payme_secret",
        PAYMENT_RETURN_URL="https://t.me/uy_ai_bot",
    )
    val_pay_svc = ValuationPaymentService(settings=test_settings)

    # Wizard
    await dp.feed_update(
        mock_bot, make_msg_update(cust_tg_id, "📊 Uyimni baholash", 11), session=db_session
    )
    await dp.feed_update(
        mock_bot, make_cb_update(cust_tg_id, "val_lt:sale", 12), session=db_session
    )
    await dp.feed_update(
        mock_bot, make_cb_update(cust_tg_id, "val_pt:apartment", 13), session=db_session
    )
    await dp.feed_update(
        mock_bot, make_cb_update(cust_tg_id, "val_dst:Chilonzor", 14), session=db_session
    )
    await dp.feed_update(
        mock_bot, make_cb_update(cust_tg_id, "val_rooms:2", 15), session=db_session
    )
    await dp.feed_update(mock_bot, make_msg_update(cust_tg_id, "56", 16), session=db_session)
    await dp.feed_update(
        mock_bot, make_cb_update(cust_tg_id, "val_cond:renovated", 17), session=db_session
    )
    await dp.feed_update(mock_bot, make_msg_update(cust_tg_id, "4/9", 18), session=db_session)

    # Complete currency step with injected configured service
    await dp.feed_update(
        mock_bot,
        make_cb_update(cust_tg_id, "val_curr:USD", 19),
        session=db_session,
        val_pay_svc=val_pay_svc,
    )

    texts = extract_bot_texts(mock_bot)
    full_output = " ".join(texts)

    # Check order prompt
    assert "Kiritilgan mulk ma'lumotlari:" in full_output
    assert "25 000 UZS" in full_output
    assert "Buyurtma ID:" in full_output

    # Check order in database
    order_repo = ValuationOrderRepository()
    orders, total = await order_repo.list_orders(db_session, limit=1)
    assert total == 1
    assert orders[0].amount_uzs == Decimal("25000")
    assert orders[0].payment_status == "pending"
    assert orders[0].valuation_status == "pending"
    assert orders[0].property_input["district"] == "Chilonzor"


# ---------------------------------------------------------------------------
# 3. Click Webhook Prepare & Complete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_click_webhook_full_lifecycle(
    setup_payment_test_data: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    """Verify Click prepare and complete webhook lifecycle with signature verification."""
    cust_id = setup_payment_test_data["customer_id"]
    cust_tg_id = setup_payment_test_data["customer_tg_id"]

    order_repo = ValuationOrderRepository()
    val_input = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        rooms=2,
        total_area=Decimal("56"),
        condition="renovated",
        currency="USD",
    )
    order = await order_repo.create_order(
        db_session,
        user_id=cust_id,
        telegram_id=cust_tg_id,
        property_input=val_input.model_dump(mode="json"),
        amount_uzs=Decimal("25000"),
    )
    await db_session.commit()

    service_id = "12345"
    secret_key = "test_click_secret"

    # Prepare action (action=0)
    click_trans_id = "998877"
    amount_str = "25000.00"
    action_0 = "0"
    sign_time = "2026-10-28 06:00:00"

    raw_prep = (
        f"{click_trans_id}{service_id}{secret_key}{order.order_id}"
        f"{amount_str}{action_0}{sign_time}"
    )
    sign_string_0 = hashlib.md5(raw_prep.encode("utf-8")).hexdigest()

    client = TestClient(app)
    from app.api.deps import get_db_session

    app.dependency_overrides[get_db_session] = lambda: db_session

    prep_payload = {
        "click_trans_id": click_trans_id,
        "service_id": service_id,
        "merchant_trans_id": order.order_id,
        "amount": amount_str,
        "action": action_0,
        "error": 0,
        "error_note": "",
        "sign_time": sign_time,
        "sign_string": sign_string_0,
    }

    # Inject test settings into app
    from app.config import get_settings

    settings = get_settings()
    settings.click_service_id = service_id
    settings.click_secret_key = secret_key

    resp = client.post("/api/v1/payments/click/webhook", data=prep_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["error"] == CLICK_ERROR_SUCCESS
    assert data["merchant_prepare_id"] > 0
    prep_id = str(data["merchant_prepare_id"])

    # Complete action (action=1)
    action_1 = "1"
    raw_comp = (
        f"{click_trans_id}{service_id}{secret_key}{order.order_id}"
        f"{prep_id}{amount_str}{action_1}{sign_time}"
    )
    sign_string_1 = hashlib.md5(raw_comp.encode("utf-8")).hexdigest()

    comp_payload = {
        "click_trans_id": click_trans_id,
        "service_id": service_id,
        "merchant_trans_id": order.order_id,
        "merchant_prepare_id": prep_id,
        "amount": amount_str,
        "action": action_1,
        "error": 0,
        "error_note": "",
        "sign_time": sign_time,
        "sign_string": sign_string_1,
    }

    resp_comp = client.post("/api/v1/payments/click/webhook", data=comp_payload)
    assert resp_comp.status_code == 200
    comp_data = resp_comp.json()
    assert comp_data["error"] == CLICK_ERROR_SUCCESS

    # Verify order is paid and valuation is completed in DB
    updated_order = await order_repo.get_by_order_id(db_session, order.order_id)
    assert updated_order is not None
    assert updated_order.payment_status == "paid"
    assert updated_order.payment_provider == "click"
    assert updated_order.valuation_status == "completed"
    assert updated_order.valuation_result is not None
    assert "estimated_price" in updated_order.valuation_result


@pytest.mark.asyncio
async def test_click_webhook_invalid_signature_and_amount(
    setup_payment_test_data: dict[str, Any],  # noqa: ARG001
    db_session: AsyncSession,
) -> None:
    """Verify Click signature failure and amount mismatch errors."""
    client = TestClient(app)
    from app.api.deps import get_db_session

    app.dependency_overrides[get_db_session] = lambda: db_session

    # 1. Invalid signature
    resp = client.post(
        "/api/v1/payments/click/webhook",
        data={
            "click_trans_id": "112233",
            "service_id": "12345",
            "merchant_trans_id": "VAL-INVALID",
            "amount": "25000",
            "action": "0",
            "sign_time": "2026-10-28 06:00:00",
            "sign_string": "bad_signature",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["error"] == CLICK_ERROR_SIGN_CHECK_FAILED


# ---------------------------------------------------------------------------
# 4. Payme JSON-RPC 2.0 Webhook
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_payme_jsonrpc_full_lifecycle(
    setup_payment_test_data: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    """Verify Payme CheckPerformTransaction, CreateTransaction, and PerformTransaction."""
    cust_id = setup_payment_test_data["customer_id"]
    cust_tg_id = setup_payment_test_data["customer_tg_id"]

    order_repo = ValuationOrderRepository()
    val_input = PropertyValuationInput(
        listing_type="sale",
        property_type="apartment",
        region="Toshkent shahri",
        district="Chilonzor",
        rooms=2,
        total_area=Decimal("56"),
        currency="USD",
    )
    order = await order_repo.create_order(
        db_session,
        user_id=cust_id,
        telegram_id=cust_tg_id,
        property_input=val_input.model_dump(mode="json"),
        amount_uzs=Decimal("25000"),
    )
    await db_session.commit()

    from app.config import get_settings

    settings = get_settings()
    settings.payme_secret_key = "test_payme_secret"

    # Build Basic Auth header: base64(Paycom:test_payme_secret)
    auth_str = base64.b64encode(b"Paycom:test_payme_secret").decode("utf-8")
    headers = {"Authorization": f"Basic {auth_str}"}

    client = TestClient(app)
    from app.api.deps import get_db_session

    app.dependency_overrides[get_db_session] = lambda: db_session
    amount_tiyin = 25000 * 100

    # 1. CheckPerformTransaction
    resp_check = client.post(
        "/api/v1/payments/payme",
        json={
            "jsonrpc": "2.0",
            "id": 101,
            "method": "CheckPerformTransaction",
            "params": {
                "amount": amount_tiyin,
                "account": {"order_id": order.order_id},
            },
        },
        headers=headers,
    )
    assert resp_check.status_code == 200
    assert resp_check.json()["result"]["allow"] is True

    # 2. CreateTransaction
    payme_id = "payme_tx_554433"
    resp_create = client.post(
        "/api/v1/payments/payme",
        json={
            "jsonrpc": "2.0",
            "id": 102,
            "method": "CreateTransaction",
            "params": {
                "id": payme_id,
                "time": 1730000000000,
                "amount": amount_tiyin,
                "account": {"order_id": order.order_id},
            },
        },
        headers=headers,
    )
    assert resp_create.status_code == 200
    assert resp_create.json()["result"]["state"] == 1

    # 3. PerformTransaction
    resp_perform = client.post(
        "/api/v1/payments/payme",
        json={
            "jsonrpc": "2.0",
            "id": 103,
            "method": "PerformTransaction",
            "params": {"id": payme_id},
        },
        headers=headers,
    )
    assert resp_perform.status_code == 200
    assert resp_perform.json()["result"]["state"] == 2

    # Verify order is marked paid and fulfilled
    updated_order = await order_repo.get_by_order_id(db_session, order.order_id)
    assert updated_order is not None
    assert updated_order.payment_status == "paid"
    assert updated_order.payment_provider == "payme"
    assert updated_order.valuation_status == "completed"


# ---------------------------------------------------------------------------
# 5. Security: Unpaid check & RBAC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unpaid_order_cannot_be_fulfilled_via_telegram_button(
    setup_payment_test_data: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    """Pressing 'val_check_pay' on unpaid order does not mark it paid."""
    cust_id = setup_payment_test_data["customer_id"]
    cust_tg_id = setup_payment_test_data["customer_tg_id"]

    order_repo = ValuationOrderRepository()
    order = await order_repo.create_order(
        db_session,
        user_id=cust_id,
        telegram_id=cust_tg_id,
        property_input={"district": "Chilonzor"},
        amount_uzs=Decimal("25000"),
    )
    await db_session.commit()

    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    # User clicks 'To‘lovni tekshirish'
    await dp.feed_update(
        mock_bot,
        make_cb_update(cust_tg_id, f"val_check_pay:{order.order_id}", 301),
        session=db_session,
    )

    # Order must remain pending
    check_order = await order_repo.get_by_order_id(db_session, order.order_id)
    assert check_order is not None
    assert check_order.payment_status == "pending"


@pytest.mark.asyncio
async def test_unauthorized_user_cannot_view_others_order(
    setup_payment_test_data: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    """User B cannot view or check User A's valuation order."""
    cust_id = setup_payment_test_data["customer_id"]
    cust_tg_id = setup_payment_test_data["customer_tg_id"]
    attacker_tg_id = setup_payment_test_data["customer2_tg_id"]

    order_repo = ValuationOrderRepository()
    order = await order_repo.create_order(
        db_session,
        user_id=cust_id,
        telegram_id=cust_tg_id,
        property_input={"district": "Chilonzor"},
        amount_uzs=Decimal("25000"),
    )
    await db_session.commit()

    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    # Attacker clicks check pay on customer's order
    await dp.feed_update(
        mock_bot,
        make_cb_update(attacker_tg_id, f"val_check_pay:{order.order_id}", 401),
        session=db_session,
    )

    texts = extract_bot_texts(mock_bot)
    full_output = " ".join(texts)
    assert "Taxminiy bozor bahosi:" not in full_output


# ---------------------------------------------------------------------------
# 6. Admin Panel API: List & Detail Valuation Orders
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_api_list_and_detail_valuation_orders(
    setup_payment_test_data: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    """Admin staff can list valuation orders and view details."""
    cust_id = setup_payment_test_data["customer_id"]
    cust_tg_id = setup_payment_test_data["customer_tg_id"]

    order_repo = ValuationOrderRepository()
    order = await order_repo.create_order(
        db_session,
        user_id=cust_id,
        telegram_id=cust_tg_id,
        property_input={"district": "Chilonzor", "rooms": 2, "total_area": 56},
        amount_uzs=Decimal("25000"),
    )
    await order_repo.mark_paid(db_session, order.order_id, "click", "click_tx_123")
    await order_repo.set_valuation_result(
        db_session,
        order.order_id,
        valuation_status="completed",
        valuation_result={"estimated_price": 55000, "currency": "USD"},
    )
    await db_session.commit()

    # Create admin staff user with superadmin role
    role_repo = RoleRepository()
    superadmin_role = await role_repo.get_by_name(db_session, "superadmin")
    assert superadmin_role is not None

    admin_user = User(
        telegram_id=770001,
        first_name="AdminVal",
        last_name="Staff",
        is_active=True,
    )
    admin_user.roles.append(superadmin_role)
    db_session.add(admin_user)
    await db_session.commit()

    from app.api.deps import get_db_session
    from app.api.routes.admin.valuation_orders import check_valuation_order_perm

    client = TestClient(app)
    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[check_valuation_order_perm] = lambda: admin_user

    # 1. List orders
    resp = client.get("/api/admin/v1/valuation-orders")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    found_order = next((o for o in data["items"] if o["order_id"] == order.order_id), None)
    assert found_order is not None
    assert found_order["payment_status"] == "paid"
    assert found_order["valuation_status"] == "completed"

    # 2. Get detail
    detail_resp = client.get(f"/api/admin/v1/valuation-orders/{order.order_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["order_id"] == order.order_id
    assert detail_data["property_input"]["district"] == "Chilonzor"
    assert detail_data["valuation_result"]["estimated_price"] == 55000

    # 3. Not found detail
    not_found_resp = client.get("/api/admin/v1/valuation-orders/VAL-NONEXISTENT")
    assert not_found_resp.status_code == 404

    # Clean up overrides
    app.dependency_overrides.clear()

