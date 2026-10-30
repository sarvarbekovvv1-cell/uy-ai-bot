"""Unit and integration tests for dynamic Professional Broker phone settings."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.types import CallbackQuery, Chat, Message, Update
from aiogram.types import User as TgUser
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.bot.dispatcher import create_dispatcher
from app.bot.states import PropertyValuationStates
from app.config import get_settings
from app.models.role import Role
from app.models.system_setting import SystemSetting
from app.models.user import User
from app.repositories.system_setting_repository import (
    DEFAULT_BROKER_PHONE,
    KEY_BROKER_PHONE,
    SystemSettingRepository,
)
from app.services.admin_auth_service import AdminAuthService
from app.utils.phone import format_uzbek_phone, normalize_phone_number


@pytest.fixture(autouse=True)
def setup_admin_db_dependencies(db_session: AsyncSession):
    async def override_get_db_session():
        yield db_session

    from app.main import app

    app.dependency_overrides[get_db_session] = override_get_db_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def broker_phone_test_context(db_session: AsyncSession):
    super_role = Role(name="superadmin", description="Super administrator")
    customer_role = Role(name="customer", description="Customer")
    db_session.add_all([super_role, customer_role])
    await db_session.flush()

    admin_user = User(
        telegram_id=881001,
        first_name="Admin",
        last_name="System",
        is_active=True,
    )
    admin_user.roles.append(super_role)

    customer_user = User(
        telegram_id=881002,
        first_name="Customer",
        last_name="Regular",
        is_active=True,
    )
    customer_user.roles.append(customer_role)

    db_session.add_all([admin_user, customer_user])
    await db_session.flush()

    auth_service = AdminAuthService(get_settings())
    await auth_service.create_or_update_staff_credential(
        db_session,
        user_id=admin_user.id,
        username="admin_settings",
        password="AdminPassword123!",
    )
    await auth_service.create_or_update_staff_credential(
        db_session,
        user_id=customer_user.id,
        username="customer_user",
        password="CustomerPassword123!",
    )

    return {
        "admin": admin_user,
        "customer": customer_user,
    }


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
        text="Valuation Card",
    )
    cb = CallbackQuery(
        id=f"cb_{update_id}",
        from_user=from_user,
        chat_instance="val_instance",
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


# -------------------------------------------------------------
# 1. Phone Utility Functions Test
# -------------------------------------------------------------
def test_phone_utils():
    assert normalize_phone_number("+998 71 200 00 00") == "+998712000000"
    assert normalize_phone_number("90 123 45 67") == "+998901234567"
    assert normalize_phone_number("invalid") is None

    assert format_uzbek_phone("+998712000000") == "+998 71 200 00 00"
    assert format_uzbek_phone("+998901234567") == "+998 90 123 45 67"
    assert format_uzbek_phone("90 123 45 67") == "+998 90 123 45 67"
    assert format_uzbek_phone("invalid") is None


# -------------------------------------------------------------
# 2. Repository Tests
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_repository_default_broker_phone(db_session: AsyncSession):
    repo = SystemSettingRepository()
    phone = await repo.get_broker_phone(db_session)
    assert phone == DEFAULT_BROKER_PHONE


@pytest.mark.asyncio
async def test_repository_set_and_get_broker_phone(db_session: AsyncSession):
    repo = SystemSettingRepository()
    saved = await repo.set_broker_phone(db_session, "+998 90 555 44 33")
    assert saved == "+998 90 555 44 33"

    fetched = await repo.get_broker_phone(db_session)
    assert fetched == "+998 90 555 44 33"

    # Verify directly in DB
    stmt = select(SystemSetting).where(SystemSetting.key == KEY_BROKER_PHONE)
    res = await db_session.execute(stmt)
    obj = res.scalar_one_or_none()
    assert obj is not None
    assert obj.value == "+998 90 555 44 33"


@pytest.mark.asyncio
async def test_repository_invalid_broker_phone_raises(db_session: AsyncSession):
    repo = SystemSettingRepository()
    with pytest.raises(ValueError, match="Telefon raqami"):
        await repo.set_broker_phone(db_session, "123")

    with pytest.raises(ValueError, match="bo'sh bo'lishi mumkin emas"):
        await repo.set_broker_phone(db_session, "   ")


# -------------------------------------------------------------
# 3. Admin API Tests
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_get_broker_phone_api(
    async_client: AsyncClient,
    broker_phone_test_context: dict[str, User],
):
    assert broker_phone_test_context["admin"] is not None
    csrf = await _login_admin(async_client, "admin_settings", "AdminPassword123!")
    resp = await async_client.get(
        "/api/admin/v1/system-settings/broker-phone",
        headers={"x-csrf-token": csrf},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["broker_phone"] == DEFAULT_BROKER_PHONE


@pytest.mark.asyncio
async def test_admin_update_broker_phone_api_success(
    async_client: AsyncClient,
    db_session: AsyncSession,
    broker_phone_test_context: dict[str, User],
):
    assert broker_phone_test_context["admin"] is not None
    csrf = await _login_admin(async_client, "admin_settings", "AdminPassword123!")

    # 1. Update phone
    resp = await async_client.put(
        "/api/admin/v1/system-settings/broker-phone",
        headers={"x-csrf-token": csrf},
        json={"broker_phone": "+998 90 123 45 67"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["broker_phone"] == "+998 90 123 45 67"

    # 2. Get phone again via API
    get_resp = await async_client.get(
        "/api/admin/v1/system-settings/broker-phone",
        headers={"x-csrf-token": csrf},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["broker_phone"] == "+998 90 123 45 67"

    # 3. Verify in database
    repo = SystemSettingRepository()
    db_phone = await repo.get_broker_phone(db_session)
    assert db_phone == "+998 90 123 45 67"


@pytest.mark.asyncio
async def test_admin_update_broker_phone_api_invalid_returns_422(
    async_client: AsyncClient,
    broker_phone_test_context: dict[str, User],
):
    assert broker_phone_test_context["admin"] is not None
    csrf = await _login_admin(async_client, "admin_settings", "AdminPassword123!")
    resp = await async_client.put(
        "/api/admin/v1/system-settings/broker-phone",
        headers={"x-csrf-token": csrf},
        json={"broker_phone": "abc-not-a-number"},
    )
    assert resp.status_code == 422
    assert "Telefon raqami" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_unauthenticated_cannot_get_or_update(async_client: AsyncClient):
    # Unauthenticated GET
    get_resp = await async_client.get("/api/admin/v1/system-settings/broker-phone")
    assert get_resp.status_code == 401

    # Unauthenticated PUT
    put_resp = await async_client.put(
        "/api/admin/v1/system-settings/broker-phone",
        json={"broker_phone": "+998 90 123 45 67"},
    )
    assert put_resp.status_code == 401


@pytest.mark.asyncio
async def test_ordinary_user_cannot_access_or_update(
    async_client: AsyncClient,
    broker_phone_test_context: dict[str, User],
):
    assert broker_phone_test_context["customer"] is not None
    # 1. Non-staff customer cannot authenticate to admin endpoints
    resp = await async_client.post(
        "/api/admin/v1/auth/login",
        json={"username": "customer_user", "password": "CustomerPassword123!"},
    )
    assert resp.status_code == 401
    assert "detail" in resp.json()
    # 1. Non-staff customer cannot authenticate to admin endpoints
    resp = await async_client.post(
        "/api/admin/v1/auth/login",
        json={"username": "customer_user", "password": "CustomerPassword123!"},
    )
    assert resp.status_code == 401
    assert "Not an authorized staff account" in resp.json()["detail"]

    # 2. Attempting to call system-settings without valid admin session returns 401
    get_resp = await async_client.get("/api/admin/v1/system-settings/broker-phone")
    assert get_resp.status_code == 401

    put_resp = await async_client.put(
        "/api/admin/v1/system-settings/broker-phone",
        json={"broker_phone": "+998 90 123 45 67"},
    )
    assert put_resp.status_code == 401


# -------------------------------------------------------------
# 4. Telegram Bot Dynamic Broker Phone Integration Tests
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_bot_displays_default_and_updated_phone_without_restart(
    db_session: AsyncSession,
):
    user_id = 777001
    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    # 1. User clicks val_act:broker with empty DB -> Default phone
    fsm_ctx = dp.fsm.get_context(bot=mock_bot, chat_id=user_id, user_id=user_id)
    await fsm_ctx.set_state(PropertyValuationStates.viewing_result)
    await fsm_ctx.update_data(language="uz")

    mock_bot.reset_mock()
    await dp.feed_update(
        mock_bot,
        make_cb_update(user_id, "val_act:broker", 1),
        session=db_session,
    )

    texts = extract_bot_texts(mock_bot)
    full_output = " ".join(texts)
    assert "👨‍💼 <b>Professional broker xizmati</b>" in full_output
    assert f"Aloqa uchun telefon: <b>{DEFAULT_BROKER_PHONE}</b>" in full_output

    # 2. Administrator updates the broker phone in the database
    new_phone = "+998 90 777 66 55"
    repo = SystemSettingRepository()
    await repo.set_broker_phone(db_session, new_phone)
    await db_session.commit()

    # 3. Next user request without restarting bot -> Immediately reflects new phone
    await fsm_ctx.set_state(PropertyValuationStates.viewing_result)
    await fsm_ctx.update_data(language="uz")

    mock_bot.reset_mock()
    await dp.feed_update(
        mock_bot,
        make_cb_update(user_id, "val_act:broker", 2),
        session=db_session,
    )

    texts = extract_bot_texts(mock_bot)
    full_output2 = " ".join(texts)
    assert "👨‍💼 <b>Professional broker xizmati</b>" in full_output2
    assert f"Aloqa uchun telefon: <b>{new_phone}</b>" in full_output2
    assert DEFAULT_BROKER_PHONE not in full_output2


@pytest.mark.asyncio
async def test_bot_displays_broker_phone_multilingual(
    db_session: AsyncSession,
):
    user_id = 777002
    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)
    custom_phone = "+998 93 111 22 33"

    repo = SystemSettingRepository()
    await repo.set_broker_phone(db_session, custom_phone)
    await db_session.commit()

    # Russian
    fsm_ctx = dp.fsm.get_context(bot=mock_bot, chat_id=user_id, user_id=user_id)
    await fsm_ctx.set_state(PropertyValuationStates.viewing_result)
    await fsm_ctx.update_data(language="ru")

    mock_bot.reset_mock()
    await dp.feed_update(
        mock_bot,
        make_cb_update(user_id, "val_act:broker", 3),
        session=db_session,
    )
    texts_ru = " ".join(extract_bot_texts(mock_bot))
    assert "Услуги профессионального брокера" in texts_ru
    assert f"Телефон для связи: <b>{custom_phone}</b>" in texts_ru

    # English
    await fsm_ctx.set_state(PropertyValuationStates.viewing_result)
    await fsm_ctx.update_data(language="en")

    mock_bot.reset_mock()
    await dp.feed_update(
        mock_bot,
        make_cb_update(user_id, "val_act:broker", 4),
        session=db_session,
    )
    texts_en = " ".join(extract_bot_texts(mock_bot))
    assert "Professional Broker Service" in texts_en
    assert f"Contact phone: <b>{custom_phone}</b>" in texts_en
