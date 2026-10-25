"""Tests for Phase 2 bot handlers, security checks, and routing."""

from unittest.mock import AsyncMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Contact, Message
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.dispatcher import create_dispatcher
from app.bot.handlers.common import handle_cancel_command, handle_help_command
from app.bot.handlers.menu import handle_placeholder_menu_buttons
from app.bot.handlers.registration import handle_contact_phone, handle_language_choice
from app.bot.handlers.settings import handle_settings_entry
from app.bot.locales import get_text
from app.bot.states import RegistrationStates
from app.services.user_service import UserService


def test_start_router_registration() -> None:
    """14. Verify /start and phase 2 routers are properly registered in dispatcher."""
    dp = create_dispatcher()
    router_names = [r.name for r in dp.sub_routers]
    assert "common" in router_names
    assert "start" in router_names
    assert "registration" in router_names
    assert "settings" in router_names
    assert "menu" in router_names


@pytest.mark.asyncio
async def test_invalid_contact_user_id_rejected() -> None:
    """10. Verify contact.user_id != message.from_user.id is rejected for security."""
    mock_message = AsyncMock(spec=Message)
    mock_message.answer = AsyncMock()

    # Sender ID is 111111
    mock_message.from_user = TgUser(id=111111, is_bot=False, first_name="Attacker")

    # Shared contact belongs to a different user ID (999999)
    mock_message.contact = Contact(
        phone_number="+998901234567",
        first_name="Victim",
        user_id=999999,  # Mismatch!
    )

    mock_state = AsyncMock(spec=FSMContext)
    mock_state.get_data.return_value = {"language": "uz"}
    mock_session = AsyncMock(spec=AsyncSession)

    await handle_contact_phone(mock_message, mock_state, mock_session)

    # Must send security error message and NOT complete registration
    mock_message.answer.assert_awaited_once_with(get_text("invalid_contact_owner", "uz"))


@pytest.mark.asyncio
async def test_help_command_handler() -> None:
    """15. Verify /help returns localized help text."""
    mock_message = AsyncMock(spec=Message)
    mock_message.answer = AsyncMock()
    mock_message.from_user = TgUser(id=123456, is_bot=False, first_name="Test")

    mock_session = AsyncMock(spec=AsyncSession)

    with patch.object(UserService, "get_by_telegram_id", new=AsyncMock(return_value=None)):
        await handle_help_command(mock_message, mock_session)

    mock_message.answer.assert_awaited_once()
    assert "UyAI" in mock_message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_cancel_command_handler() -> None:
    """16. Verify /cancel clears FSM state and sends cancel response."""
    mock_message = AsyncMock(spec=Message)
    mock_message.answer = AsyncMock()
    mock_message.from_user = TgUser(id=123456, is_bot=False, first_name="Test")

    mock_state = AsyncMock(spec=FSMContext)
    mock_session = AsyncMock(spec=AsyncSession)

    with patch.object(UserService, "get_by_telegram_id", new=AsyncMock(return_value=None)):
        await handle_cancel_command(mock_message, mock_state, mock_session)

    mock_state.clear.assert_awaited_once()
    mock_message.answer.assert_awaited_once()
    assert mock_message.answer.call_args[0][0] == get_text("cancel_text", "uz")


@pytest.mark.asyncio
async def test_placeholder_menu_behavior() -> None:
    """18. Verify that clicking menu placeholder buttons returns in-development notice."""
    mock_message = AsyncMock(spec=Message)
    mock_message.answer = AsyncMock()
    mock_message.from_user = TgUser(id=123456, is_bot=False, first_name="Test")
    mock_message.text = "🏠 Uy sotib olish"

    mock_session = AsyncMock(spec=AsyncSession)

    with patch.object(UserService, "get_by_telegram_id", new=AsyncMock(return_value=None)):
        await handle_placeholder_menu_buttons(mock_message, mock_session)

    mock_message.answer.assert_awaited_once_with(get_text("feature_in_development", "uz"))


@pytest.mark.asyncio
async def test_language_callback_uzbek_advances_to_consent() -> None:
    """Regression test: language choice (uz) advances FSM to consent step."""
    mock_callback = AsyncMock(spec=CallbackQuery)
    mock_callback.data = "lang:uz"
    mock_callback.from_user = TgUser(id=7165062713, is_bot=False, first_name="TestUser")
    mock_callback.message = AsyncMock(spec=Message)
    mock_callback.message.edit_text = AsyncMock()
    mock_callback.answer = AsyncMock()

    mock_state = AsyncMock(spec=FSMContext)
    mock_session = AsyncMock(spec=AsyncSession)

    with patch.object(UserService, "initialize_user", new=AsyncMock()) as mock_init:
        await handle_language_choice(mock_callback, mock_state, mock_session)

        mock_callback.answer.assert_awaited_once()
        mock_state.update_data.assert_awaited_once_with(language="uz")
        mock_init.assert_awaited_once()
        mock_state.set_state.assert_awaited_once_with(RegistrationStates.waiting_consent)

        # Verify message was edited to show consent prompt
        mock_callback.message.edit_text.assert_awaited_once()
        assert get_text("consent_text", "uz") in mock_callback.message.edit_text.call_args[0][0]


@pytest.mark.asyncio
async def test_language_callback_russian_advances_to_consent() -> None:
    """Regression test: language choice (ru) advances FSM to consent step."""
    mock_callback = AsyncMock(spec=CallbackQuery)
    mock_callback.data = "lang:ru"
    mock_callback.from_user = TgUser(id=7165062713, is_bot=False, first_name="TestUser")
    mock_callback.message = AsyncMock(spec=Message)
    mock_callback.message.edit_text = AsyncMock()
    mock_callback.answer = AsyncMock()

    mock_state = AsyncMock(spec=FSMContext)
    mock_session = AsyncMock(spec=AsyncSession)

    with patch.object(UserService, "initialize_user", new=AsyncMock()) as mock_init:
        await handle_language_choice(mock_callback, mock_state, mock_session)

        mock_callback.answer.assert_awaited_once()
        mock_state.update_data.assert_awaited_once_with(language="ru")
        mock_init.assert_awaited_once()
        mock_state.set_state.assert_awaited_once_with(RegistrationStates.waiting_consent)

        # Verify message was edited to show consent prompt
        mock_callback.message.edit_text.assert_awaited_once()
        assert get_text("consent_text", "ru") in mock_callback.message.edit_text.call_args[0][0]


@pytest.mark.asyncio
async def test_user_initialization_db_insert_autoincrement() -> None:
    """Regression test: verify user insert succeeds without NOT NULL constraint failed on id."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.database.base import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        user_service = UserService()
        user = await user_service.initialize_user(
            session,
            telegram_id=7165062713,
            language="uz",
            first_name="RealUser",
        )
        await session.commit()

        assert user.id is not None
        assert user.id > 0
        assert user.telegram_id == 7165062713
        assert user.language == "uz"

    await engine.dispose()


@pytest.mark.asyncio
async def test_settings_entry() -> None:
    """19. Verify settings menu button triggers settings prompt."""
    mock_message = AsyncMock(spec=Message)
    mock_message.answer = AsyncMock()
    mock_message.from_user = TgUser(id=123456, is_bot=False, first_name="Test")

    mock_session = AsyncMock(spec=AsyncSession)

    with patch.object(UserService, "get_by_telegram_id", new=AsyncMock(return_value=None)):
        await handle_settings_entry(mock_message, mock_session)

    mock_message.answer.assert_awaited_once()
    assert get_text("settings_title", "uz") in mock_message.answer.call_args[0][0]
