"""Tests for Telegram bot dispatcher and handler registration."""

from unittest.mock import AsyncMock

import pytest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Chat, Message, User
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.dispatcher import create_dispatcher
from app.bot.handlers.start import handle_start_command, start_router
from app.bot.locales import get_text


def test_dispatcher_creation_without_polling() -> None:
    """Verify that Dispatcher initializes cleanly with registered routers and no polling."""
    dp = create_dispatcher()
    assert dp is not None
    # Verify start_router is included in sub_routers
    sub_router_names = [r.name for r in dp.sub_routers]
    assert "start" in sub_router_names


def test_start_router_has_registered_handlers() -> None:
    """Verify that start_router has the CommandStart handler registered without network calls."""
    assert len(start_router.message.handlers) >= 1
    handler_obj = start_router.message.handlers[0]
    # Check that CommandStart filter is present on the handler callback
    assert any(isinstance(getattr(f, "callback", None), CommandStart) for f in handler_obj.filters)


@pytest.mark.asyncio
async def test_start_command_handler_response() -> None:
    """Verify that handle_start_command initiates language selection for new users."""
    from unittest.mock import patch

    from app.services.user_service import UserService

    mock_message = AsyncMock(spec=Message)
    mock_message.answer = AsyncMock()
    mock_message.text = "/start"
    mock_message.chat = Chat(id=12345678, type="private")
    mock_message.from_user = User(id=12345678, is_bot=False, first_name="TestUser")

    mock_state = AsyncMock(spec=FSMContext)
    mock_session = AsyncMock(spec=AsyncSession)

    with patch.object(UserService, "get_by_telegram_id", new=AsyncMock(return_value=None)):
        await handle_start_command(mock_message, mock_state, mock_session)

    mock_message.answer.assert_awaited_once()
    assert mock_message.answer.call_args[0][0] == get_text("choose_language", "uz")
