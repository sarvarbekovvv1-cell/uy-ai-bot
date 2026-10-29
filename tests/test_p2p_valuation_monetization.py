"""Comprehensive test suite for P2P Card Monetization and Gemini Receipt Verification."""

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
async def test_payment_card_setting_repository(db_session: AsyncSession) -> None:
    """Test getting and updating payment card settings."""
    repo = PaymentCardSettingRepository()
    setting = await repo.get_setting(db_session)
    assert setting.card_number == "9860 0000 0000 0000"
    assert setting.standard_price_uzs == Decimal("15000")
    assert setting.premium_price_uzs == Decimal("30000")
    assert setting.is_active is True

    updated = await repo.update_setting(
        db_session,
        card_number="8600 1234 5678 9999",
        card_holder="Alisher Navoiy",
        standard_price_uzs=Decimal("20000"),
        premium_price_uzs=Decimal("45000"),
        is_active=True,
    )
    assert updated.card_number == "8600 1234 5678 9999"
    assert updated.card_holder == "Alisher Navoiy"
    assert updated.standard_price_uzs == Decimal("20000")
    assert updated.premium_price_uzs == Decimal("45000")


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
            assert "standard_price_uzs" in data
            assert "premium_price_uzs" in data
            assert data["is_active"] is True

            # 2. PUT settings
            put_resp = await client.put(
                "/api/admin/v1/payment-settings",
                json={
                    "card_number": "9860 1111 2222 3333",
                    "card_holder": "SARVAR BEKOV",
                    "standard_price_uzs": 18000,
                    "premium_price_uzs": 35000,
                    "is_active": True,
                },
            )
            assert put_resp.status_code == 200
            put_data = put_resp.json()
            assert put_data["card_number"] == "9860 1111 2222 3333"
            assert put_data["card_holder"] == "SARVAR BEKOV"
            assert Decimal(str(put_data["standard_price_uzs"])) == Decimal("18000")
            assert Decimal(str(put_data["premium_price_uzs"])) == Decimal("35000")
    finally:
        app.dependency_overrides.pop(check_payment_settings_perm, None)
        app.dependency_overrides.pop(get_db_session, None)


@pytest.mark.asyncio
async def test_bot_currency_step_shows_package_selection(
    db_session: AsyncSession,
    sample_user: User,
    fsm_context: FSMContext,
) -> None:
    """Test currency step shows package selection when card payment is active."""
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

    callback.answer.assert_awaited()
    # Check that package selection message was presented
    call_args = callback_msg.edit_text.call_args[0][0]
    assert "Baholash xizmati darajasini tanlang" in call_args
    assert "Standart baholash" in call_args
    assert "Ekspert / Kengaytirilgan tahlil" in call_args

    state_name = await fsm_context.get_state()
    assert state_name == PropertyValuationStates.waiting_package


@pytest.mark.asyncio
async def test_bot_package_selection_prompts_card_and_receipt(
    db_session: AsyncSession,
    sample_user: User,
    fsm_context: FSMContext,
) -> None:
    """Test that choosing package creates order and prompts for card payment and receipt upload."""
    await fsm_context.set_data(
        {
            "val_input": {
                "listing_type": "sale",
                "property_type": "apartment",
                "region": "Toshkent shahri",
                "district": "Chilonzor",
                "rooms": 2,
                "total_area": "60",
                "currency": "USD",
            },
            "language": "uz",
        }
    )
    await fsm_context.set_state(PropertyValuationStates.waiting_package)

    callback_msg = AsyncMock(spec=Message)
    callback_msg.edit_text = AsyncMock()

    tg_user = TgUser(id=sample_user.telegram_id, is_bot=False, first_name="Test")
    callback = MagicMock(spec=CallbackQuery)
    callback.data = "val_pkg:premium"
    callback.from_user = tg_user
    callback.message = callback_msg
    callback.answer = AsyncMock()

    await handle_valuation_package_selection(callback, fsm_context, db_session)

    call_args = callback_msg.edit_text.call_args[0][0]
    assert "To‘lov ma’lumotlari" in call_args
    assert "Ekspert / Kengaytirilgan tahlil" in call_args
    assert "Quyidagi kartaga to‘lovni o‘tkazing" in call_args
    assert "To‘lov chekini (skrinshotini) shu yerga rasm ko‘rinishida yuboring" in call_args

    state_name = await fsm_context.get_state()
    assert state_name == PropertyValuationStates.waiting_receipt

    data = await fsm_context.get_data()
    assert "order_id" in data
    assert data["package_type"] == "premium"

    order_repo = ValuationOrderRepository()
    order = await order_repo.get_by_order_id(db_session, data["order_id"])
    assert order is not None
    assert order.package_type == "premium"
    assert order.payment_status == "pending"


@pytest.mark.asyncio
async def test_bot_receipt_upload_success_fulfills_valuation(
    db_session: AsyncSession,
    sample_user: User,
    fsm_context: FSMContext,
) -> None:
    """Test uploading a valid payment receipt triggers valuation report."""
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
        amount_uzs=Decimal("15000"),
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
    bot_mock.get_file = AsyncMock(return_value=MagicMock(file_path="mock/path.jpg"))
    bot_mock.download_file = AsyncMock(return_value=b"fake-image-bytes")

    tg_user = TgUser(id=sample_user.telegram_id, is_bot=False, first_name="Test")
    photo = PhotoSize(file_id="photo123", file_unique_id="uniq123", width=800, height=600)
    msg = AsyncMock(spec=Message)
    msg.photo = [photo]
    msg.from_user = tg_user
    msg.bot = bot_mock
    msg.answer = AsyncMock(return_value=status_msg)

    # Mock ReceiptVerificationService to return valid payment
    mock_receipt_svc = MagicMock(spec=ReceiptVerificationService)
    mock_receipt_svc.verify_receipt = AsyncMock(
        return_value=ReceiptVerificationResult(
            is_receipt=True,
            is_successful=True,
            amount_uzs=Decimal("15000"),
            payment_system="click",
            notes="Valid Click receipt",
        )
    )

    await handle_valuation_receipt_upload(
        msg,
        fsm_context,
        db_session,
        receipt_service=mock_receipt_svc,
    )

    # Verify order is marked paid
    refreshed_order = await order_repo.get_by_order_id(db_session, order.order_id)
    assert refreshed_order is not None
    assert refreshed_order.payment_status == "paid"
    assert refreshed_order.payment_provider == "card_transfer"
    assert refreshed_order.receipt_file_id == "photo123"

    # Verify valuation answer was sent to customer
    msg.answer.assert_called()
    last_answer_args = msg.answer.call_args[0][0]
    assert (
        "Bozor bahosi" in last_answer_args
        or "Taxminiy bozor bahosi" in last_answer_args
        or "Taqqoslama ma'lumotlar yetarli emas" in last_answer_args
    )


@pytest.mark.asyncio
async def test_bot_receipt_upload_insufficient_amount_rejects(
    db_session: AsyncSession,
    sample_user: User,
    fsm_context: FSMContext,
) -> None:
    """Test uploading receipt with amount lower than required displays warning."""
    order_repo = ValuationOrderRepository()
    order = await order_repo.create_order(
        db_session,
        user_id=sample_user.id,
        telegram_id=sample_user.telegram_id,
        property_input={"district": "Chilonzor", "total_area": "50", "rooms": 2},
        amount_uzs=Decimal("30000"),
        currency="UZS",
        package_type="premium",
    )
    await db_session.commit()

    await fsm_context.set_data(
        {
            "order_id": order.order_id,
            "package_type": "premium",
            "language": "uz",
        }
    )
    await fsm_context.set_state(PropertyValuationStates.waiting_receipt)

    status_msg = AsyncMock(spec=Message)
    status_msg.edit_text = AsyncMock()

    bot_mock = AsyncMock()
    bot_mock.get_file = AsyncMock(return_value=MagicMock(file_path="mock/path.jpg"))
    bot_mock.download_file = AsyncMock(return_value=b"fake-image-bytes")

    tg_user = TgUser(id=sample_user.telegram_id, is_bot=False, first_name="Test")
    photo = PhotoSize(file_id="photo123", file_unique_id="uniq123", width=800, height=600)
    msg = AsyncMock(spec=Message)
    msg.photo = [photo]
    msg.from_user = tg_user
    msg.bot = bot_mock
    msg.answer = AsyncMock(return_value=status_msg)

    # Receipt with only 10,000 UZS instead of 30,000 UZS
    mock_receipt_svc = MagicMock(spec=ReceiptVerificationService)
    mock_receipt_svc.verify_receipt = AsyncMock(
        return_value=ReceiptVerificationResult(
            is_receipt=True,
            is_successful=True,
            amount_uzs=Decimal("10000"),
            payment_system="payme",
            notes="Partial payment",
        )
    )

    await handle_valuation_receipt_upload(
        msg,
        fsm_context,
        db_session,
        receipt_service=mock_receipt_svc,
    )

    # Verify order is STILL pending
    refreshed_order = await order_repo.get_by_order_id(db_session, order.order_id)
    assert refreshed_order is not None
    assert refreshed_order.payment_status == "pending"

    # Status message updated with warning
    call_args = status_msg.edit_text.call_args[0][0]
    assert "To‘lov summasi yetarli emas" in call_args
    assert "10 000" in call_args
    assert "30 000" in call_args


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
