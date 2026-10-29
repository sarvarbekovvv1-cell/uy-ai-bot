"""Comprehensive test suite for P2P Card Monetization and Admin Approval Flow."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from aiogram.types import CallbackQuery, Message, PhotoSize
from aiogram.types import User as TgUser
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.admin.payment_settings import check_payment_settings_perm
from app.api.routes.admin.valuation_orders import check_valuation_order_perm
from app.bot.handlers.valuation import (
    handle_valuation_currency,
    handle_valuation_package_selection,
    handle_valuation_receipt_text_reminder,
    handle_valuation_receipt_upload,
)
from app.bot.states import PropertyValuationStates
from app.main import app
from app.models.user import User
from app.repositories.payment_card_setting_repository import PaymentCardSettingRepository
from app.repositories.valuation_order_repository import ValuationOrderRepository
from app.services.payment.receipt_verification_service import (
    ReceiptVerificationResult,
    ReceiptVerificationService,
)


@pytest.fixture
async def sample_user(db_session: AsyncSession) -> User:
    """Create test customer user in database."""
    user = User(
        telegram_id=987654321,
        first_name="Valuation",
        last_name="Tester",
        phone="+998901234567",
        language="uz",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def fsm_context() -> FSMContext:
    """Create in-memory FSMContext for testing."""
    storage = MemoryStorage()
    key = StorageKey(bot_id=123456789, chat_id=987654321, user_id=987654321)
    return FSMContext(storage=storage, key=key)


@pytest.mark.asyncio
async def test_payment_card_setting_configured_logic(db_session: AsyncSession) -> None:
    """Test payment card repository and is_configured detection."""
    repo = PaymentCardSettingRepository()
    setting = await repo.get_setting(db_session)

    # If card_number is empty or placeholder, is_configured() is False
    assert setting.is_configured() is False

    # Update with real credentials
    updated = await repo.update_setting(
        db_session,
        card_number="8600 1234 5678 9999",
        card_holder="Alisher Navoiy",
        basic_price_uzs=Decimal("50000"),
        standard_price_uzs=Decimal("65000"),
        premium_price_uzs=Decimal("90000"),
        is_active=True,
    )
    assert updated.is_configured() is True
    assert updated.basic_price_uzs == Decimal("50000")
    assert updated.standard_price_uzs == Decimal("65000")
    assert updated.premium_price_uzs == Decimal("90000")


@pytest.mark.asyncio
async def test_admin_api_payment_settings(db_session: AsyncSession, sample_user: User) -> None:
    """Test GET and PUT /api/admin/v1/payment-settings endpoints."""
    from app.api.deps import get_db_session

    async def _override_db():
        yield db_session

    app.dependency_overrides[check_payment_settings_perm] = lambda: sample_user
    app.dependency_overrides[get_db_session] = _override_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. GET settings
            resp = await client.get("/api/admin/v1/payment-settings")
            assert resp.status_code == 200
            data = resp.json()
            assert "card_number" in data
            assert "basic_price_uzs" in data
            assert "standard_price_uzs" in data
            assert "premium_price_uzs" in data

            # 2. PUT settings
            put_resp = await client.put(
                "/api/admin/v1/payment-settings",
                json={
                    "card_number": "9860 1111 2222 3333",
                    "card_holder": "SARVAR BEKOV",
                    "basic_price_uzs": 48000,
                    "standard_price_uzs": 64000,
                    "premium_price_uzs": 88000,
                    "is_active": True,
                },
            )
            assert put_resp.status_code == 200
            put_data = put_resp.json()
            assert put_data["card_number"] == "9860 1111 2222 3333"
            assert put_data["card_holder"] == "SARVAR BEKOV"
            assert Decimal(str(put_data["basic_price_uzs"])) == Decimal("48000")
            assert Decimal(str(put_data["standard_price_uzs"])) == Decimal("64000")
            assert Decimal(str(put_data["premium_price_uzs"])) == Decimal("88000")
    finally:
        app.dependency_overrides.pop(check_payment_settings_perm, None)
        app.dependency_overrides.pop(get_db_session, None)


@pytest.mark.asyncio
async def test_bot_currency_step_unconfigured_card_shows_safe_message(
    db_session: AsyncSession,
    sample_user: User,
    fsm_context: FSMContext,
) -> None:
    """Test unconfigured card shows safe notice rather than fake placeholder card."""
    repo = PaymentCardSettingRepository()
    await repo.update_setting(db_session, card_number="", card_holder="", is_active=False)
    await db_session.commit()

    await fsm_context.set_data({"language": "uz"})
    await fsm_context.set_state(PropertyValuationStates.waiting_currency)

    callback_msg = AsyncMock(spec=Message)
    callback_msg.answer = AsyncMock()

    tg_user = TgUser(id=sample_user.telegram_id, is_bot=False, first_name="Test")
    callback = MagicMock(spec=CallbackQuery)
    callback.data = "val_curr:USD"
    callback.from_user = tg_user
    callback.message = callback_msg
    callback.answer = AsyncMock()

    await handle_valuation_currency(callback, fsm_context, db_session)

    callback_msg.answer.assert_called()
    msg_text = callback_msg.answer.call_args[0][0]
    assert "To‘lov qabul qilish tizimi sozlanmagan" in msg_text or "vaqtinchalik" in msg_text


@pytest.mark.asyncio
async def test_bot_currency_step_configured_card_shows_3_tiers(
    db_session: AsyncSession,
    sample_user: User,
    fsm_context: FSMContext,
) -> None:
    """Test configured card displays 3 distinct pricing tiers."""
    repo = PaymentCardSettingRepository()
    await repo.update_setting(
        db_session,
        card_number="8600 5555 6666 7777",
        card_holder="UyAI Merchant",
        basic_price_uzs=Decimal("50000"),
        standard_price_uzs=Decimal("65000"),
        premium_price_uzs=Decimal("90000"),
        is_active=True,
    )
    await db_session.commit()

    await fsm_context.set_data(
        {
            "listing_type": "sale",
            "property_type": "apartment",
            "region": "Toshkent shahri",
            "district": "Chilonzor",
            "rooms": 3,
            "total_area": "75",
            "condition": "renovated",
            "floor": 4,
            "total_floors": 9,
            "language": "uz",
        }
    )
    await fsm_context.set_state(PropertyValuationStates.waiting_currency)

    callback_msg = AsyncMock(spec=Message)
    callback_msg.edit_text = AsyncMock()
    callback_msg.answer = AsyncMock()

    tg_user = TgUser(id=sample_user.telegram_id, is_bot=False, first_name="Test")
    callback = MagicMock(spec=CallbackQuery)
    callback.data = "val_curr:USD"
    callback.from_user = tg_user
    callback.message = callback_msg
    callback.answer = AsyncMock()

    await handle_valuation_currency(callback, fsm_context, db_session)

    call_args = callback_msg.edit_text.call_args[0][0]
    assert "Basic (Bazaviy)" in call_args
    assert "Standard (Standart)" in call_args
    assert "Premium (Ekspert)" in call_args
    assert "50 000" in call_args
    assert "65 000" in call_args
    assert "90 000" in call_args

    state_name = await fsm_context.get_state()
    assert state_name == PropertyValuationStates.waiting_package


@pytest.mark.asyncio
async def test_bot_package_selection_creates_order_and_prompts_card(
    db_session: AsyncSession,
    sample_user: User,
    fsm_context: FSMContext,
) -> None:
    """Test package selection creates order and shows copyable card details."""
    repo = PaymentCardSettingRepository()
    await repo.update_setting(
        db_session,
        card_number="8600 5555 6666 7777",
        card_holder="UyAI Merchant",
        basic_price_uzs=Decimal("50000"),
        is_active=True,
    )
    await db_session.commit()

    await fsm_context.set_data(
        {
            "val_input": {
                "listing_type": "sale",
                "property_type": "apartment",
                "region": "Toshkent shahri",
                "district": "Chilonzor",
                "total_area": "50",
                "rooms": 2,
            },
            "language": "uz",
        }
    )
    await fsm_context.set_state(PropertyValuationStates.waiting_package)

    callback_msg = AsyncMock(spec=Message)
    callback_msg.edit_text = AsyncMock()

    tg_user = TgUser(id=sample_user.telegram_id, is_bot=False, first_name="Test")
    callback = MagicMock(spec=CallbackQuery)
    callback.data = "val_pkg:basic"
    callback.from_user = tg_user
    callback.message = callback_msg
    callback.answer = AsyncMock()

    await handle_valuation_package_selection(callback, fsm_context, db_session)

    call_args = callback_msg.edit_text.call_args[0][0]
    assert "To‘lov ma’lumotlari" in call_args
    assert "8600 5555 6666 7777" in call_args
    assert "UyAI Merchant" in call_args
    assert "50 000 so‘m" in call_args

    data = await fsm_context.get_data()
    assert data["package_type"] == "basic"
    assert "order_id" in data


@pytest.mark.asyncio
async def test_bot_receipt_upload_sets_pending_verification(
    db_session: AsyncSession,
    sample_user: User,
    fsm_context: FSMContext,
) -> None:
    """Test uploading a valid receipt transitions order to pending_verification."""
    order_repo = ValuationOrderRepository()
    order = await order_repo.create_order(
        db_session,
        user_id=sample_user.id,
        telegram_id=sample_user.telegram_id,
        property_input={
            "listing_type": "sale",
            "property_type": "apartment",
            "region": "Toshkent shahri",
            "district": "Chilonzor",
            "rooms": 2,
            "total_area": "50",
            "condition": "renovated",
            "currency": "USD",
        },
        amount_uzs=Decimal("65000"),
        currency="UZS",
        package_type="standard",
    )
    await db_session.commit()

    await fsm_context.set_data(
        {
            "order_id": order.order_id,
            "package_type": "standard",
            "language": "uz",
        }
    )
    await fsm_context.set_state(PropertyValuationStates.waiting_receipt)

    status_msg = AsyncMock(spec=Message)
    status_msg.edit_text = AsyncMock()

    bot_mock = AsyncMock()
    bot_mock.get_file = AsyncMock(return_value=MagicMock(file_path="mock/receipt.jpg"))
    bot_mock.download_file = AsyncMock(return_value=b"fake-image-bytes")

    tg_user = TgUser(id=sample_user.telegram_id, is_bot=False, first_name="Test")
    photo = PhotoSize(file_id="receipt_photo_123", file_unique_id="uniq123", width=800, height=600)
    msg = AsyncMock(spec=Message)
    msg.photo = [photo]
    msg.from_user = tg_user
    msg.bot = bot_mock
    msg.answer = AsyncMock(return_value=status_msg)

    mock_receipt_svc = MagicMock(spec=ReceiptVerificationService)
    mock_receipt_svc.verify_receipt = AsyncMock(
        return_value=ReceiptVerificationResult(
            verdict="likely_match",
            is_receipt=True,
            is_successful=True,
            amount_uzs=Decimal("65000"),
            payment_system="click",
            notes="Click orqali to'langan",
        )
    )

    await handle_valuation_receipt_upload(
        msg,
        fsm_context,
        db_session,
        receipt_service=mock_receipt_svc,
    )

    # CRITICAL: Verify order is in pending_verification, NOT paid!
    refreshed_order = await order_repo.get_by_order_id(db_session, order.order_id)
    assert refreshed_order is not None
    assert refreshed_order.payment_status == "pending_verification"
    assert refreshed_order.receipt_file_id == "receipt_photo_123"
    assert refreshed_order.receipt_analysis["verdict"] == "likely_match"

    # User received pending verification message
    edit_args = status_msg.edit_text.call_args[0][0]
    assert "administrator tomonidan tasdiqlanishi kutilmoqda" in edit_args


@pytest.mark.asyncio
async def test_bot_receipt_duplicate_prevention(
    db_session: AsyncSession,
    sample_user: User,
    fsm_context: FSMContext,
) -> None:
    """Test attempting to upload an already used receipt photo is blocked."""
    order_repo = ValuationOrderRepository()

    # Pre-existing order with receipt_file_id
    existing_order = await order_repo.create_order(
        db_session,
        user_id=sample_user.id,
        telegram_id=sample_user.telegram_id,
        property_input={"district": "Chilonzor", "total_area": "50", "rooms": 2},
        amount_uzs=Decimal("50000"),
        currency="UZS",
        package_type="basic",
    )
    await order_repo.mark_pending_verification(
        db_session,
        existing_order.order_id,
        receipt_file_id="duplicate_photo_999",
        receipt_analysis={"verdict": "likely_match"},
    )
    await db_session.commit()

    # New order trying to upload duplicate photo
    new_order = await order_repo.create_order(
        db_session,
        user_id=sample_user.id,
        telegram_id=sample_user.telegram_id,
        property_input={"district": "Chilonzor", "total_area": "50", "rooms": 2},
        amount_uzs=Decimal("50000"),
        currency="UZS",
        package_type="basic",
    )
    await db_session.commit()

    await fsm_context.set_data({"order_id": new_order.order_id, "language": "uz"})
    await fsm_context.set_state(PropertyValuationStates.waiting_receipt)

    photo = PhotoSize(
        file_id="duplicate_photo_999", file_unique_id="uniq999", width=800, height=600
    )
    msg = AsyncMock(spec=Message)
    msg.photo = [photo]
    msg.from_user = TgUser(id=sample_user.telegram_id, is_bot=False, first_name="Test")
    msg.answer = AsyncMock()

    await handle_valuation_receipt_upload(msg, fsm_context, db_session)

    msg.answer.assert_called()
    assert "allaqachon boshqa buyurtmada ishlatilgan" in msg.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_admin_api_approve_and_reject_flow(
    db_session: AsyncSession,
    sample_user: User,
) -> None:
    """Test Admin API endpoints to approve and reject valuation receipts with audit logs."""
    from app.api.deps import get_db_session

    order_repo = ValuationOrderRepository()
    order = await order_repo.create_order(
        db_session,
        user_id=sample_user.id,
        telegram_id=sample_user.telegram_id,
        property_input={
            "listing_type": "sale",
            "property_type": "apartment",
            "region": "Toshkent shahri",
            "district": "Chilonzor",
            "rooms": 2,
            "total_area": "50",
            "condition": "renovated",
            "currency": "USD",
        },
        amount_uzs=Decimal("90000"),
        currency="UZS",
        package_type="premium",
    )
    await order_repo.mark_pending_verification(
        db_session,
        order.order_id,
        receipt_file_id="admin_test_receipt",
        receipt_analysis={"verdict": "likely_match", "amount_uzs": 90000},
    )
    await db_session.commit()

    async def _override_db():
        yield db_session

    app.dependency_overrides[check_valuation_order_perm] = lambda: sample_user
    app.dependency_overrides[get_db_session] = _override_db

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Detail check
            resp = await client.get(f"/api/admin/v1/valuation-orders/{order.order_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["payment_status"] == "pending_verification"
            assert data["package_type"] == "premium"

            # 2. Approve order
            approve_resp = await client.post(
                f"/api/admin/v1/valuation-orders/{order.order_id}/approve",
                json={"notes": "Karta hisobiga 90 000 so'm tushgani tasdiqlandi."},
            )
            assert approve_resp.status_code == 200
            approve_data = approve_resp.json()
            assert approve_data["status"] == "approved"
            assert approve_data["payment_status"] == "paid"
            assert approve_data["valuation_status"] == "completed"

            # Verify in DB
            refreshed = await order_repo.get_by_order_id(db_session, order.order_id)
            assert refreshed.payment_status == "paid"
            assert refreshed.valuation_status == "completed"
            assert refreshed.approved_by_user_id == sample_user.id

            # 3. Create another order to test rejection
            rej_order = await order_repo.create_order(
                db_session,
                user_id=sample_user.id,
                telegram_id=sample_user.telegram_id,
                property_input={"district": "Chilonzor", "total_area": "50", "rooms": 2},
                amount_uzs=Decimal("50000"),
                package_type="basic",
            )
            await order_repo.mark_pending_verification(
                db_session,
                rej_order.order_id,
                receipt_file_id="rej_receipt",
                receipt_analysis={"verdict": "mismatch"},
            )
            await db_session.commit()

            reject_resp = await client.post(
                f"/api/admin/v1/valuation-orders/{rej_order.order_id}/reject",
                json={"reason": "Chekdagi summa mos emas va pul tushmagan."},
            )
            assert reject_resp.status_code == 200
            rej_data = reject_resp.json()
            assert rej_data["status"] == "rejected"
            assert rej_data["payment_status"] == "rejected"

            rej_refreshed = await order_repo.get_by_order_id(db_session, rej_order.order_id)
            assert rej_refreshed.payment_status == "rejected"
            assert rej_refreshed.admin_notes == "Chekdagi summa mos emas va pul tushmagan."

    finally:
        app.dependency_overrides.pop(check_valuation_order_perm, None)
        app.dependency_overrides.pop(get_db_session, None)


@pytest.mark.asyncio
async def test_bot_receipt_text_reminder(
    fsm_context: FSMContext,
) -> None:
    """Test text messages sent while in waiting_receipt state receive photo reminder."""
    await fsm_context.set_data({"order_id": "VAL-1234", "language": "uz"})
    await fsm_context.set_state(PropertyValuationStates.waiting_receipt)

    msg = AsyncMock(spec=Message)
    msg.answer = AsyncMock()

    await handle_valuation_receipt_text_reminder(msg, fsm_context)

    msg.answer.assert_awaited()
    assert "to‘lov chekining skrinshotini" in msg.answer.call_args[0][0]
