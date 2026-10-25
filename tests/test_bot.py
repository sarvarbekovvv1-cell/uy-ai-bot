"""Tests for Telegram bot dispatcher and handler registration."""

from unittest.mock import AsyncMock

import pytest
from aiogram.filters import CommandStart
from aiogram.types import Chat, Message, User

from app.bot.dispatcher import create_dispatcher
from app.bot.handlers.start import START_MESSAGE, handle_start_command, start_router


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
    """Verify that handle_start_command sends the foundation message without network calls."""
    mock_message = AsyncMock(spec=Message)
    mock_message.answer = AsyncMock()
    mock_message.text = "/start"
    mock_message.chat = Chat(id=12345678, type="private")
    mock_message.from_user = User(id=12345678, is_bot=False, first_name="TestUser")

    await handle_start_command(mock_message)

    mock_message.answer.assert_awaited_once_with(START_MESSAGE)
