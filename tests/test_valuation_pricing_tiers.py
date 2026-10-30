"""Tests for AI valuation pricing tiers display, selection, and admin management."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Chat, Message, Update
from aiogram.types import User as TgUser
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.bot.dispatcher import create_dispatcher
from app.bot.handlers.valuation import (
    handle_valuation_package_back,
    handle_valuation_package_selection,
    handle_valuation_upgrade_ai,
)
from app.bot.keyboards import get_valuation_package_keyboard
from app.bot.states import PropertyValuationStates
from app.config import get_settings
from app.models.property import Property
from app.models.role import Role
from app.models.user import User
from app.repositories.payment_card_setting_repository import PaymentCardSettingRepository
from app.repositories.valuation_order_repository import ValuationOrderRepository
from app.services.admin_auth_service import AdminAuthService


@pytest.fixture(autouse=True)
def setup_admin_db_dependencies(db_session: AsyncSession):
    async def override_get_db_session():
        yield db_session

    from app.main import app

    app.dependency_overrides[get_db_session] = override_get_db_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def fsm_context() -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=123456789, chat_id=987654321, user_id=987654321)
    return FSMContext(storage=storage, key=key)


@pytest.fixture
async def sample_user(db_session: AsyncSession) -> User:
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
async def setup_valuation_db(db_session: AsyncSession) -> dict[str, int]:
    customer = User(
        telegram_id=990001,
        language="uz",
        first_name="ValCustomer",
        phone="+998909900001",
        consent_accepted_at=datetime.now(UTC),
    )
    customer_ru = User(
        telegram_id=990002,
        language="ru",
        first_name="ValCustomerRu",
        phone="+998909900002",
        consent_accepted_at=datetime.now(UTC),
    )
    db_session.add_all([customer, customer_ru])
    await db_session.commit()

    comp1 = Property(
        owner_user_id=customer.id,
        listing_type="sale",
        property_type="apartment",
        title="2-room Chilonzor",
        region="Toshkent shahri",
        district="Chilonzor",
        address="Chilonzor-9",
        rooms=2,
        total_area=Decimal("55"),
        condition="renovated",
        price=Decimal("95000"),
        currency="USD",
        status="approved",
    )
    db_session.add(comp1)
    await db_session.commit()
    await db_session.refresh(comp1)

    return {
        "customer_uz": customer.telegram_id,
        "customer_ru": customer_ru.telegram_id,
        "comp1": comp1.id,
    }


@pytest.fixture
async def admin_auth_context(db_session: AsyncSession):
    super_role = Role(name="superadmin", description="Super administrator")
    db_session.add(super_role)
    await db_session.flush()

    admin_user = User(
        telegram_id=992001,
        first_name="Admin",
        last_name="Valuation",
        is_active=True,
    )
    admin_user.roles.append(super_role)
    db_session.add(admin_user)
    await db_session.flush()

    auth_service = AdminAuthService(get_settings())
    await auth_service.create_or_update_staff_credential(
        db_session,
        user_id=admin_user.id,
        username="admin_valuation",
        password="AdminValuation123!",
    )
    return admin_user


async def _login_admin(client: AsyncClient, username: str, password: str) -> str:
    resp = await client.post(
        "/api/admin/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["csrf_token"]


def make_cb_update(user_id: int, data: str, update_id: int = 2) -> Update:
    from_user = TgUser(id=user_id, is_bot=False, first_name="ValUser", username="val_user")
    chat = Chat(id=user_id, type="private")
    msg = Message(
        message_id=update_id,
        date=datetime.now(UTC),
        chat=chat,
        from_user=from_user,
        text="Card Message",
    )
    cb = CallbackQuery(
        id=f"cb_{update_id}",
        from_user=from_user,
        chat_instance="val_instance",
        message=msg,
        data=data,
    )
    return Update(update_id=update_id, callback_query=cb)


def make_msg_update(user_id: int, text: str, update_id: int = 1) -> Update:
    from_user = TgUser(id=user_id, is_bot=False, first_name="ValUser", username="val_user")
    chat = Chat(id=user_id, type="private")
    msg = Message(
        message_id=update_id,
        date=datetime.now(UTC),
        chat=chat,
        from_user=from_user,
        text=text,
    )
    return Update(update_id=update_id, message=msg)


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


@pytest.mark.asyncio
async def test_upgrade_ai_displays_3_tiers_and_prices_without_creating_order(
    setup_valuation_db: dict[str, int],
    db_session: AsyncSession,
) -> None:
    """Clicking 'Kengaytirilgan AI tahlil' displays 3 tiers and prices with no order yet."""
    user_id = setup_valuation_db["customer_uz"]
    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    # 1. Complete standard free valuation
    await dp.feed_update(
        mock_bot, make_msg_update(user_id, "📊 Uyimni baholash", 1), session=db_session
    )
    await dp.feed_update(mock_bot, make_cb_update(user_id, "val_lt:sale", 2), session=db_session)
    await dp.feed_update(
        mock_bot, make_cb_update(user_id, "val_pt:apartment", 3), session=db_session
    )
    await dp.feed_update(
        mock_bot, make_cb_update(user_id, "val_dst:Chilonzor", 4), session=db_session
    )
    await dp.feed_update(mock_bot, make_cb_update(user_id, "val_rooms:2", 5), session=db_session)
    await dp.feed_update(mock_bot, make_msg_update(user_id, "56", 6), session=db_session)
    await dp.feed_update(
        mock_bot, make_cb_update(user_id, "val_cond:renovated", 7), session=db_session
    )
    await dp.feed_update(mock_bot, make_msg_update(user_id, "5/8", 8), session=db_session)
    await dp.feed_update(mock_bot, make_cb_update(user_id, "val_curr:USD", 9), session=db_session)

    fsm_ctx = dp.fsm.get_context(bot=mock_bot, chat_id=user_id, user_id=user_id)
    assert await fsm_ctx.get_state() == PropertyValuationStates.viewing_result

    # Ensure no orders exist before tier selection
    order_repo = ValuationOrderRepository()
    orders_before = await order_repo.list_orders(db_session)
    count_before = len(orders_before)

    # 2. Click "Kengaytirilgan AI tahlil" (val_act:upgrade_ai)
    mock_bot.reset_mock()
    await dp.feed_update(
        mock_bot, make_cb_update(user_id, "val_act:upgrade_ai", 10), session=db_session
    )

    texts = extract_bot_texts(mock_bot)
    full_text = " ".join(texts)

    # All three tiers must be prominently listed with prices
    assert "Basic" in full_text
    assert "Standard" in full_text
    assert "Premium" in full_text
    assert "50 000" in full_text
    assert "65 000" in full_text
    assert "90 000" in full_text

    # Features check
    assert "Asosiy AI ko‘chmas mulk tahlili" in full_text
    assert "Kengaytirilgan bozor tahlili" in full_text
    assert "Eng batafsil AI tahlili" in full_text

    # State must be waiting_package
    assert await fsm_ctx.get_state() == PropertyValuationStates.waiting_package

    # Still no order created until a package is chosen
    orders_after = await order_repo.list_orders(db_session)
    assert len(orders_after) == count_before


@pytest.mark.asyncio
async def test_package_keyboard_has_distinct_buttons_and_back() -> None:
    """Verify package keyboard contains separate buttons for 3 tiers and back navigation."""
    kb_uz = get_valuation_package_keyboard(50000, 65000, 90000, lang="uz")
    rows = kb_uz.inline_keyboard
    assert len(rows) == 4
    assert rows[0][0].callback_data == "val_pkg:basic"
    assert "50 000 so‘m" in rows[0][0].text
    assert rows[1][0].callback_data == "val_pkg:standard"
    assert "65 000 so‘m" in rows[1][0].text
    assert rows[2][0].callback_data == "val_pkg:premium"
    assert "90 000 so‘m" in rows[2][0].text
    assert rows[3][0].callback_data == "val_pkg_back"
    assert "Ortga" in rows[3][0].text

    kb_ru = get_valuation_package_keyboard(50000, 65000, 90000, lang="ru")
    rows_ru = kb_ru.inline_keyboard
    assert "50 000 сум" in rows_ru[0][0].text
    assert "Назад" in rows_ru[3][0].text


@pytest.mark.asyncio
async def test_each_tier_selection_creates_order_with_exact_price(
    db_session: AsyncSession,
    sample_user: User,
    fsm_context: FSMContext,
) -> None:
    """Selecting basic, standard, or premium creates an order with that tier's exact price."""
    card_repo = PaymentCardSettingRepository()
    await card_repo.update_setting(
        db_session,
        card_number="8600 1234 5678 9999",
        card_holder="UyAI Real Estate",
        basic_price_uzs=Decimal("50000"),
        standard_price_uzs=Decimal("65000"),
        premium_price_uzs=Decimal("90000"),
        is_active=True,
    )
    await db_session.commit()

    test_tiers = [
        ("basic", 50000, "50 000"),
        ("standard", 65000, "65 000"),
        ("premium", 90000, "90 000"),
    ]

    for pkg_name, expected_amount, expected_fmt in test_tiers:
        await fsm_context.set_data(
            {
                "val_input": {
                    "listing_type": "sale",
                    "property_type": "apartment",
                    "region": "Toshkent shahri",
                    "district": "Chilonzor",
                    "total_area": "60",
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
        callback.data = f"val_pkg:{pkg_name}"
        callback.from_user = tg_user
        callback.message = callback_msg
        callback.answer = AsyncMock()

        await handle_valuation_package_selection(callback, fsm_context, db_session)

        # Message must contain the exact price and order details
        call_text = callback_msg.edit_text.call_args[0][0]
        assert f"{expected_fmt} so‘m" in call_text
        assert "8600 1234 5678 9999" in call_text
        assert "UyAI Real Estate" in call_text

        # FSM state should now wait for receipt
        assert await fsm_context.get_state() == PropertyValuationStates.waiting_receipt

        # Verify order in DB
        data = await fsm_context.get_data()
        order_id = data["order_id"]
        order_repo = ValuationOrderRepository()
        order = await order_repo.get_by_order_id(db_session, order_id)
        assert order is not None
        assert order.package_type == pkg_name
        assert int(order.amount_uzs) == expected_amount
        assert order.payment_status == "pending"


@pytest.mark.asyncio
async def test_admin_updates_prices_and_bot_reflects_immediately(
    async_client: AsyncClient,
    db_session: AsyncSession,
    admin_auth_context: User,
    sample_user: User,
    fsm_context: FSMContext,
) -> None:
    """Admin changes tier prices; bot reflects new prices immediately on next query."""
    assert admin_auth_context is not None
    csrf = await _login_admin(async_client, "admin_valuation", "AdminValuation123!")

    # 1. Update prices via Admin API
    res = await async_client.put(
        "/api/admin/v1/payment-settings",
        headers={"x-csrf-token": csrf},
        json={
            "card_number": "8600 1111 2222 3333",
            "card_holder": "New Admin Card",
            "basic_price_uzs": 55000,
            "standard_price_uzs": 75000,
            "premium_price_uzs": 105000,
            "is_active": True,
        },
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert float(payload["basic_price_uzs"]) == 55000.0
    assert float(payload["standard_price_uzs"]) == 75000.0
    assert float(payload["premium_price_uzs"]) == 105000.0

    # 2. Call handle_valuation_upgrade_ai in bot
    await fsm_context.set_data(
        {
            "val_input": {
                "listing_type": "sale",
                "property_type": "apartment",
                "region": "Toshkent shahri",
                "district": "Yunusobod",
                "total_area": "70",
                "rooms": 3,
            },
            "language": "uz",
        }
    )
    await fsm_context.set_state(PropertyValuationStates.viewing_result)

    callback_msg = AsyncMock(spec=Message)
    callback_msg.edit_text = AsyncMock()

    tg_user = TgUser(id=sample_user.telegram_id, is_bot=False, first_name="Test")
    callback = MagicMock(spec=CallbackQuery)
    callback.data = "val_act:upgrade_ai"
    callback.from_user = tg_user
    callback.message = callback_msg
    callback.answer = AsyncMock()

    await handle_valuation_upgrade_ai(callback, fsm_context, db_session)

    call_text = callback_msg.edit_text.call_args[0][0]
    # Newly updated prices must appear immediately
    assert "55 000 so‘m" in call_text
    assert "75 000 so‘m" in call_text
    assert "105 000 so‘m" in call_text


@pytest.mark.asyncio
async def test_existing_order_amount_is_frozen_when_prices_change(
    db_session: AsyncSession,
    sample_user: User,
) -> None:
    """Existing orders maintain their created price even if admin changes tier prices later."""
    order_repo = ValuationOrderRepository()
    order = await order_repo.create_order(
        db_session,
        user_id=sample_user.id,
        telegram_id=sample_user.telegram_id,
        property_input={"district": "Chilonzor"},
        amount_uzs=Decimal("50000"),
        currency="UZS",
        package_type="basic",
    )
    await db_session.commit()
    order_id = order.order_id

    # Change prices in settings
    card_repo = PaymentCardSettingRepository()
    await card_repo.update_setting(
        db_session,
        basic_price_uzs=Decimal("99000"),
    )
    await db_session.commit()

    # Existing order must remain 50 000
    refreshed_order = await order_repo.get_by_order_id(db_session, order_id)
    assert refreshed_order is not None
    assert int(refreshed_order.amount_uzs) == 50000


@pytest.mark.asyncio
async def test_back_button_from_package_restores_valuation_result_card(
    fsm_context: FSMContext,
) -> None:
    """Clicking 'val_pkg_back' restores previous valuation result card and viewing_result state."""
    await fsm_context.set_data(
        {
            "val_input": {
                "listing_type": "sale",
                "property_type": "apartment",
                "region": "Toshkent shahri",
                "district": "Chilonzor",
                "total_area": "50",
                "rooms": 2,
                "currency": "USD",
            },
            "last_result": {
                "estimated_price": 55000,
                "estimated_min_price": 50000,
                "estimated_max_price": 60000,
                "currency": "USD",
                "confidence": "high",
                "comparable_count": 5,
                "comparable_properties": [],
            },
            "language": "uz",
        }
    )
    await fsm_context.set_state(PropertyValuationStates.waiting_package)

    callback_msg = AsyncMock(spec=Message)
    callback_msg.edit_text = AsyncMock()

    callback = MagicMock(spec=CallbackQuery)
    callback.data = "val_pkg_back"
    callback.message = callback_msg
    callback.answer = AsyncMock()

    await handle_valuation_package_back(callback, fsm_context)

    # State restored to viewing_result
    assert await fsm_context.get_state() == PropertyValuationStates.viewing_result
    call_text = callback_msg.edit_text.call_args[0][0]
    assert "Taxminiy bozor bahosi" in call_text


@pytest.mark.asyncio
async def test_upgrade_ai_callback_without_prior_input_shows_tiers_gracefully(
    fsm_context: FSMContext,
    db_session: AsyncSession,
    sample_user: User,
) -> None:
    """Clicking upgrade_ai when state has no val_input still displays all 3 tiers and prices."""
    await fsm_context.clear()

    callback_msg = AsyncMock(spec=Message)
    callback_msg.edit_text = AsyncMock()

    tg_user = TgUser(id=sample_user.telegram_id, is_bot=False, first_name="Test")
    callback = MagicMock(spec=CallbackQuery)
    callback.data = "val_act:upgrade_ai"
    callback.from_user = tg_user
    callback.message = callback_msg
    callback.answer = AsyncMock()

    await handle_valuation_upgrade_ai(callback, fsm_context, db_session)

    assert callback_msg.edit_text.called
    call_text = callback_msg.edit_text.call_args[0][0]
    assert "Basic (Bazaviy)" in call_text
    assert "Standard (Standart)" in call_text
    assert "Premium (Ekspert)" in call_text
    assert "50 000 so‘m" in call_text
    assert "65 000 so‘m" in call_text
    assert "90 000 so‘m" in call_text


@pytest.mark.asyncio
async def test_upgrade_ai_callback_with_expired_answer_does_not_crash(
    fsm_context: FSMContext,
    db_session: AsyncSession,
    sample_user: User,
) -> None:
    """If callback.answer() fails due to timeout/duplicate, handler still delivers the tiers."""
    await fsm_context.clear()

    callback_msg = AsyncMock(spec=Message)
    callback_msg.edit_text = AsyncMock()

    tg_user = TgUser(id=sample_user.telegram_id, is_bot=False, first_name="Test")
    callback = MagicMock(spec=CallbackQuery)
    callback.data = "val_act:upgrade_ai"
    callback.from_user = tg_user
    callback.message = callback_msg
    # Simulate expired query or network glitch on answer()
    callback.answer = AsyncMock(
        side_effect=TelegramBadRequest(method="answerCallbackQuery", message="query is too old")
    )

    await handle_valuation_upgrade_ai(callback, fsm_context, db_session)

    assert callback_msg.edit_text.called
    call_text = callback_msg.edit_text.call_args[0][0]
    assert "50 000 so‘m" in call_text


@pytest.mark.asyncio
async def test_upgrade_ai_diagnostic_logs_emitted(
    fsm_context: FSMContext,
    db_session: AsyncSession,
    sample_user: User,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify all 6 diagnostic log stages are emitted during handle_valuation_upgrade_ai."""
    import logging
    caplog.set_level(logging.INFO)

    await fsm_context.clear()
    callback_msg = AsyncMock(spec=Message)
    callback_msg.edit_text = AsyncMock()

    tg_user = TgUser(id=sample_user.telegram_id, is_bot=False, first_name="Test")
    callback = MagicMock(spec=CallbackQuery)
    callback.data = "val_act:upgrade_ai"
    callback.from_user = tg_user
    callback.message = callback_msg
    callback.answer = AsyncMock()

    await handle_valuation_upgrade_ai(callback, fsm_context, db_session)

    log_records = caplog.text
    assert "DIAG_UPGRADE_AI: Callback qabul qilindi" in log_records
    assert "DIAG_UPGRADE_AI: Handler ishga tushdi: handle_valuation_upgrade_ai" in log_records
    assert "DIAG_UPGRADE_AI: Tariflar muvaffaqiyatli olindimi: HA" in log_records
    assert "DIAG_UPGRADE_AI: Keyboard yaratildimi: HA" in log_records
    assert "DIAG_UPGRADE_AI: Xatolik yuz berdimi: YO‘Q" in log_records

