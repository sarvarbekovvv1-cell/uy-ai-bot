"""Telegram bot handlers for AI Broker natural language conversation."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.property_search import format_card_caption
from app.bot.keyboards import (
    MAIN_MENU_BUTTONS,
    get_ai_broker_keyboard,
    get_main_menu_keyboard,
    get_property_card_keyboard,
)
from app.bot.locales import LOCALES, get_text
from app.bot.states import AIBrokerStates
from app.config import get_settings
from app.core.exceptions import AIBrokerRateLimitError
from app.logging import get_logger
from app.services.ai_broker_service import AIBrokerService
from app.services.favorite_service import FavoriteService
from app.services.user_service import UserService

logger = get_logger(__name__)

ai_broker_router = Router(name="ai_broker")

# Collect localized triggers for entering AI Broker
AI_BROKER_TRIGGERS: set[str] = {
    locale_dict["btn_ai_broker"]
    for locale_dict in LOCALES.values()
    if "btn_ai_broker" in locale_dict
} | {"🤖 AI broker bilan suhbat", "🤖 AI broker", "🤖 AI брокер"}

# Localized triggers for exiting AI Broker
AI_EXIT_TRIGGERS: set[str] = {
    locale_dict["btn_ai_exit"]
    for locale_dict in LOCALES.values()
    if "btn_ai_exit" in locale_dict
} | {"❌ Suhbatni yakunlash", "❌ Завершить диалог", "❌ AI suhbatni tugatish"}


@ai_broker_router.message(F.text.in_(AI_BROKER_TRIGGERS))
@ai_broker_router.message(F.text == "/ai_broker")
async def handle_ai_broker_entry(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Enter AI Broker conversation mode or inform user if disabled."""
    if not message.from_user:
        return

    settings = get_settings()
    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, message.from_user.id)
    lang = user.language if user else "uz"

    # Feature flag check
    if not settings.ai_broker_enabled:
        await message.answer(
            get_text("ai_disabled", lang),
            reply_markup=get_main_menu_keyboard(lang),
        )
        return

    # Enter conversational state
    await state.set_state(AIBrokerStates.chatting)
    await state.update_data(ai_history=[])

    await message.answer(
        get_text("ai_welcome", lang),
        reply_markup=get_ai_broker_keyboard(lang),
    )


@ai_broker_router.message(AIBrokerStates.chatting, F.text.in_(AI_EXIT_TRIGGERS))
@ai_broker_router.message(AIBrokerStates.chatting, F.text.in_({"/cancel", "/exit"}))
async def handle_ai_broker_exit(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Exit AI Broker mode and return to main menu."""
    await state.clear()

    user_service = UserService()
    user = (
        await user_service.get_by_telegram_id(session, message.from_user.id)
        if message.from_user
        else None
    )
    lang = user.language if user else "uz"

    await message.answer(
        get_text("ai_exit_confirmation", lang),
        reply_markup=get_main_menu_keyboard(lang),
    )


@ai_broker_router.message(
    AIBrokerStates.chatting,
    ~F.text.in_(MAIN_MENU_BUTTONS),
    ~F.text.startswith("/"),
)
async def handle_ai_broker_message(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    ai_broker_service: AIBrokerService | None = None,
) -> None:
    """Process natural language real estate message with AI Broker."""
    if not message.text or not message.from_user:
        return

    user_service = UserService()
    user = await user_service.get_by_telegram_id(session, message.from_user.id)
    if not user:
        user = await user_service.create_user(
            session,
            telegram_id=message.from_user.id,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            username=message.from_user.username,
            language="uz",
        )

    lang = user.language or "uz"
    data = await state.get_data()
    history = data.get("ai_history", [])

    service = ai_broker_service or AIBrokerService()
    fav_service = FavoriteService()

    try:
        result = await service.process_message(
            session=session,
            user=user,
            message_text=message.text,
            history=history,
        )
    except AIBrokerRateLimitError:
        await message.answer(get_text("ai_rate_limited", lang))
        return
    except Exception as exc:
        logger.error("Unexpected error in AI Broker message handler: %s", exc)
        await message.answer(get_text("ai_fallback_error", lang))
        return

    # Update bounded conversational history
    settings = get_settings()
    max_turns = settings.ai_max_history_messages
    new_history = list(history)
    new_history.append({"role": "user", "text": message.text})
    new_history.append({"role": "model", "text": result.text})
    if len(new_history) > max_turns:
        new_history = new_history[-max_turns:]
    await state.update_data(ai_history=new_history)

    # Presentation based on AI result action
    if result.action == "search_results":
        if not result.properties:
            await message.answer(result.text)
            return

        await message.answer(result.text)
        for p in result.properties:
            is_fav = await fav_service.is_favorite(session, user_id=user.id, property_id=p.id)
            caption = format_card_caption(p, lang)
            card_kb = get_property_card_keyboard(p.id, is_fav=is_fav, lang=lang)

            if p.media and len(p.media) > 0 and message.bot:
                try:
                    first_photo = p.media[0]
                    await message.answer_photo(
                        photo=first_photo.telegram_file_id,
                        caption=caption,
                        reply_markup=card_kb,
                    )
                    continue
                except Exception:
                    pass

            await message.answer(caption, reply_markup=card_kb)

    elif result.action == "property_answer":
        prop = result.properties[0] if result.properties else None
        if prop:
            is_fav = await fav_service.is_favorite(session, user_id=user.id, property_id=prop.id)
            card_kb = get_property_card_keyboard(prop.id, is_fav=is_fav, lang=lang)
            await message.answer(result.text, reply_markup=card_kb)
        else:
            await message.answer(result.text)

    elif result.action == "route_viewing":
        prop_id = result.property_id
        if prop_id:
            btn_viewing_text = (
                "📅 Ko‘rishga yozilish" if lang == "uz" else "📅 Записаться на просмотр"
            )
            btn_details_text = "ℹ️ E'lon tafsilotlari" if lang == "uz" else "ℹ️ Подробнее"
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=btn_viewing_text,
                            callback_data=f"request_viewing:{prop_id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=btn_details_text,
                            callback_data=f"prop_details:{prop_id}",
                        )
                    ],
                ]
            )
            await message.answer(result.text, reply_markup=kb)
        else:
            await message.answer(result.text)

    elif result.action == "route_broker":
        prop_id = result.property_id
        if prop_id:
            btn_broker_text = (
                "👨‍💼 Broker bilan bog‘lanish" if lang == "uz" else "👨‍💼 Связаться с брокером"
            )
            btn_details_text = "ℹ️ E'lon tafsilotlari" if lang == "uz" else "ℹ️ Подробнее"
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=btn_broker_text,
                            callback_data=f"contact_broker:{prop_id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=btn_details_text,
                            callback_data=f"prop_details:{prop_id}",
                        )
                    ],
                ]
            )
            await message.answer(result.text, reply_markup=kb)
        else:
            await message.answer(result.text)

    else:
        # General, clarification, favorites_help
        await message.answer(result.text)
