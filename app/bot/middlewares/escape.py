"""Middleware to gracefully escape active conversational FSM when main menu button is pressed."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, TelegramObject

from app.bot.keyboards import MAIN_MENU_BUTTONS
from app.bot.states import AIBrokerStates


class MenuEscapeMiddleware(BaseMiddleware):
    """Automatically clears AI Broker conversation state when a menu button is clicked."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.text and event.text in MAIN_MENU_BUTTONS:
            state: FSMContext | None = data.get("state")
            if state:
                cur = await state.get_state()
                if cur == AIBrokerStates.chatting.state:
                    await state.clear()

        return await handler(event, data)
