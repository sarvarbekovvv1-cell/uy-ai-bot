"""Tests for Telegram Mini App bot handlers and keyboards."""

from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import Chat, Message, User, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.dispatcher import create_dispatcher
from app.bot.handlers.miniapp import handle_miniapp_button, miniapp_router
from app.bot.keyboards import get_main_menu_keyboard
from app.config import Settings
from app.models.user import User as UserModel


def test_dispatcher_includes_miniapp_router() -> None:
    """Verify that Dispatcher includes the miniapp router."""
    dp = create_dispatcher()
    router_names = [r.name for r in dp.sub_routers]
    assert "miniapp" in router_names


def test_miniapp_router_has_registered_handlers() -> None:
    """Verify miniapp_router has message handlers registered."""
    assert len(miniapp_router.message.handlers) >= 1


@pytest.mark.asyncio
async def test_miniapp_button_with_url_configured_uz() -> None:
    """When MINIAPP_URL is set, bot returns WebAppInfo inline button in Uzbek."""
    mock_message = AsyncMock(spec=Message)
    mock_message.answer = AsyncMock()
    mock_message.text = "📍 Xaritadan uy qidirish"
    mock_message.chat = Chat(id=12345, type="private")
    tg_user = User(id=12345, is_bot=False, first_name="Ali")
    mock_message.from_user = tg_user

    mock_db_user = UserModel(
        id=1,
        telegram_id=12345,
        phone="+998901234567",
        first_name="Ali",
        language="uz",
    )
    mock_session = AsyncMock(spec=AsyncSession)

    test_settings = Settings(
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        MINIAPP_URL="https://app.uyai.uz",
    )

    with (
        patch("app.bot.handlers.miniapp.get_settings", return_value=test_settings),
        patch(
            "app.services.user_service.UserService.get_by_telegram_id",
            new=AsyncMock(return_value=mock_db_user),
        ),
    ):
        await handle_miniapp_button(mock_message, mock_session)

    mock_message.answer.assert_awaited_once()
    args, kwargs = mock_message.answer.call_args
    assert "Xaritasi va Mini App" in args[0]
    markup = kwargs.get("reply_markup")
    assert markup is not None
    assert len(markup.inline_keyboard) == 1
    btn = markup.inline_keyboard[0][0]
    assert isinstance(btn.web_app, WebAppInfo)
    assert btn.web_app.url == "https://app.uyai.uz"
    assert "Xaritani ochish" in btn.text


@pytest.mark.asyncio
async def test_miniapp_button_with_url_configured_ru() -> None:
    """When MINIAPP_URL is set, bot returns WebAppInfo inline button in Russian."""
    mock_message = AsyncMock(spec=Message)
    mock_message.answer = AsyncMock()
    mock_message.text = "/map"
    mock_message.chat = Chat(id=54321, type="private")
    mock_message.from_user = User(id=54321, is_bot=False, first_name="Ivan")

    mock_db_user = UserModel(
        id=2,
        telegram_id=54321,
        phone="+998907654321",
        first_name="Ivan",
        language="ru",
    )
    mock_session = AsyncMock(spec=AsyncSession)

    test_settings = Settings(
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        MINIAPP_URL="https://app.uyai.uz",
    )

    with (
        patch("app.bot.handlers.miniapp.get_settings", return_value=test_settings),
        patch(
            "app.services.user_service.UserService.get_by_telegram_id",
            new=AsyncMock(return_value=mock_db_user),
        ),
    ):
        await handle_miniapp_button(mock_message, mock_session)

    mock_message.answer.assert_awaited_once()
    args, kwargs = mock_message.answer.call_args
    assert "Карта и Mini App" in args[0]
    markup = kwargs.get("reply_markup")
    assert markup is not None
    btn = markup.inline_keyboard[0][0]
    assert btn.web_app.url == "https://app.uyai.uz"
    assert "Открыть карту" in btn.text


@pytest.mark.asyncio
async def test_miniapp_button_fallback_when_unconfigured() -> None:
    """When MINIAPP_URL is empty, bot replies with graceful fallback text."""
    mock_message = AsyncMock(spec=Message)
    mock_message.answer = AsyncMock()
    mock_message.text = "📍 Xaritadan uy qidirish"
    mock_message.chat = Chat(id=12345, type="private")
    mock_message.from_user = User(id=12345, is_bot=False, first_name="Ali")

    mock_session = AsyncMock(spec=AsyncSession)
    test_settings = Settings(
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        MINIAPP_URL="",
    )

    with (
        patch("app.bot.handlers.miniapp.get_settings", return_value=test_settings),
        patch(
            "app.services.user_service.UserService.get_by_telegram_id",
            new=AsyncMock(return_value=None),
        ),
    ):
        await handle_miniapp_button(mock_message, mock_session)

    mock_message.answer.assert_awaited_once()
    args, kwargs = mock_message.answer.call_args
    assert "sozlanmoqda" in args[0]
    assert kwargs.get("reply_markup") is None


def test_build_main_menu_keyboard_with_miniapp_url() -> None:
    """Check get_main_menu_keyboard attaches web_app when miniapp_url is configured."""
    test_settings = Settings(
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        MINIAPP_URL="https://app.uyai.uz",
    )
    with patch("app.bot.keyboards.get_settings", return_value=test_settings):
        kb = get_main_menu_keyboard("uz")
        map_btn = None
        for row in kb.keyboard:
            for btn in row:
                if "Xaritadan" in btn.text:
                    map_btn = btn
                    break
        assert map_btn is not None
        assert map_btn.web_app is not None
        assert map_btn.web_app.url == "https://app.uyai.uz"
