"""Tests for property search handlers, FSM wizard, pagination, and favorites."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Chat, Message, Update
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.dispatcher import create_dispatcher
from app.bot.handlers.favorites import (
    format_card_caption,
    format_detailed_view,
    handle_add_favorite_callback,
    handle_list_favorites,
    handle_remove_favorite_callback,
    handle_view_property_details,
)
from app.bot.handlers.property_search import (
    handle_district,
    handle_property_type,
    handle_region,
    handle_rooms,
    handle_search_page_callback,
    handle_search_restart_callback,
    handle_start_buy_search,
    handle_start_rent_search,
)
from app.bot.locales import get_text
from app.bot.states import PropertySearchStates
from app.models.property import Property
from app.models.user import User
from app.services.favorite_service import FavoriteService
from app.services.property_search_service import PropertySearchService
from app.services.user_service import UserService


@pytest.mark.asyncio
async def test_search_entrypoints_sale_and_rent() -> None:
    """Verify buying and renting entry points set correct listing_type and FSM state."""
    mock_message = AsyncMock(spec=Message)
    mock_message.from_user = TgUser(id=777, is_bot=False, first_name="Buyer")
    mock_message.answer = AsyncMock()

    mock_state = AsyncMock(spec=FSMContext)
    mock_session = AsyncMock(spec=AsyncSession)

    registered_user = User(
        id=1,
        telegram_id=777,
        language="uz",
        phone="+998901234567",
        consent_accepted_at=datetime.now(UTC),
    )

    with patch.object(
        UserService, "get_by_telegram_id", new=AsyncMock(return_value=registered_user)
    ):
        # 1. Buy search
        await handle_start_buy_search(mock_message, mock_state, mock_session)
        mock_state.set_state.assert_awaited_with(PropertySearchStates.choosing_property_type)
        mock_state.update_data.assert_awaited_with(listing_type="sale", language="uz", user_id=1)
        assert get_text("search_start_sale", "uz") in mock_message.answer.call_args[0][0]

        # 2. Rent search
        await handle_start_rent_search(mock_message, mock_state, mock_session)
        mock_state.update_data.assert_awaited_with(listing_type="rent", language="uz", user_id=1)
        assert get_text("search_start_rent", "uz") in mock_message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_search_wizard_fsm_steps() -> None:
    """Verify FSM transitions and filter data updates through wizard."""
    mock_state = AsyncMock(spec=FSMContext)
    mock_state.get_data.return_value = {"language": "uz", "listing_type": "sale"}

    # 1. Property type
    msg_type = AsyncMock(spec=Message)
    msg_type.text = "🏢 Kvartira"
    msg_type.answer = AsyncMock()
    await handle_property_type(msg_type, mock_state)
    mock_state.update_data.assert_awaited_with(property_type="apartment")
    mock_state.set_state.assert_awaited_with(PropertySearchStates.waiting_region)

    # 2. Region
    msg_region = AsyncMock(spec=Message)
    msg_region.text = "Toshkent"
    msg_region.answer = AsyncMock()
    await handle_region(msg_region, mock_state)
    mock_state.update_data.assert_awaited_with(region="Toshkent")
    mock_state.set_state.assert_awaited_with(PropertySearchStates.waiting_district)

    # 3. District with Skip
    msg_dist = AsyncMock(spec=Message)
    msg_dist.text = "⏭ O‘tkazib yuborish"
    msg_dist.answer = AsyncMock()
    await handle_district(msg_dist, mock_state)
    mock_state.update_data.assert_awaited_with(district=None)
    mock_state.set_state.assert_awaited_with(PropertySearchStates.choosing_rooms)

    # 4. Rooms 5+
    msg_rooms = AsyncMock(spec=Message)
    msg_rooms.text = "5+"
    msg_rooms.answer = AsyncMock()
    await handle_rooms(msg_rooms, mock_state)
    mock_state.update_data.assert_awaited_with(rooms=None, min_rooms=5)
    mock_state.set_state.assert_awaited_with(PropertySearchStates.waiting_min_price)


@pytest.mark.asyncio
async def test_search_cancel_resets_state() -> None:
    """Verify /cancel at any point clears FSM state and presents main menu."""
    mock_state = AsyncMock(spec=FSMContext)
    mock_state.get_data.return_value = {"language": "uz"}

    msg_cancel = AsyncMock(spec=Message)
    msg_cancel.text = "/cancel"
    msg_cancel.answer = AsyncMock()

    await handle_region(msg_cancel, mock_state)

    mock_state.clear.assert_awaited_once()
    assert get_text("cancel_text", "uz") in msg_cancel.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_pagination_and_restart_callbacks() -> None:
    """Verify search page navigation and restart triggers."""
    mock_state = AsyncMock(spec=FSMContext)
    mock_state.get_data.return_value = {
        "language": "uz",
        "listing_type": "sale",
        "user_id": 1,
    }
    mock_session = AsyncMock(spec=AsyncSession)

    # Pagination callback
    mock_callback = AsyncMock(spec=CallbackQuery)
    mock_callback.data = "search_page:2"
    mock_callback.message = AsyncMock(spec=Message)
    mock_callback.message.answer = AsyncMock()
    mock_callback.answer = AsyncMock()

    with patch.object(PropertySearchService, "search", new=AsyncMock(return_value=([], 0, 1))):
        await handle_search_page_callback(mock_callback, mock_state, mock_session)
        mock_callback.answer.assert_awaited_once()

    # Restart callback
    mock_restart_cb = AsyncMock(spec=CallbackQuery)
    mock_restart_cb.data = "search_nav:restart"
    mock_restart_cb.message = AsyncMock(spec=Message)
    mock_restart_cb.message.answer = AsyncMock()
    mock_restart_cb.from_user = TgUser(id=777, is_bot=False, first_name="Buyer")
    mock_restart_cb.answer = AsyncMock()

    registered_user = User(
        id=1,
        telegram_id=777,
        language="uz",
        phone="+998901234567",
        consent_accepted_at=datetime.now(UTC),
    )
    with patch.object(
        UserService, "get_by_telegram_id", new=AsyncMock(return_value=registered_user)
    ):
        await handle_search_restart_callback(mock_restart_cb, mock_state, mock_session)
        mock_state.set_state.assert_awaited_with(PropertySearchStates.choosing_property_type)


@pytest.mark.asyncio
async def test_favorites_handlers_and_privacy_checks() -> None:
    """Verify favorite add/remove/list handlers and check that owner PII is NOT exposed."""
    user = User(id=1, telegram_id=777, language="uz")
    prop = Property(
        id=42,
        owner_user_id=99,  # Private owner ID
        listing_type="sale",
        property_type="apartment",
        region="Toshkent",
        district="Yunusobod",
        address="1-mavze",
        rooms=3,
        total_area=Decimal("75"),
        floor=4,
        total_floors=9,
        condition="euro",
        cadastre_status="available",
        price=Decimal("70000"),
        currency="USD",
        has_furniture=True,
        negotiable=False,
        status="approved",
        description="Shinam xonadon",
    )

    # 1. Privacy test: ensure detailed view does not expose owner's ID or private contact
    detail_text = format_detailed_view(prop, "uz")
    assert "99" not in detail_text  # Owner's user ID must not appear
    assert "70,000 USD" in detail_text
    assert "Shinam xonadon" in detail_text

    card_text = format_card_caption(prop, "uz")
    assert "#42" in card_text
    assert "Yunusobod" in card_text

    # 2. List favorites
    mock_msg = AsyncMock(spec=Message)
    mock_msg.from_user = TgUser(id=777, is_bot=False, first_name="Buyer")
    mock_msg.answer = AsyncMock()
    mock_session = AsyncMock(spec=AsyncSession)

    with (
        patch.object(UserService, "get_by_telegram_id", new=AsyncMock(return_value=user)),
        patch.object(FavoriteService, "list_saved_properties", new=AsyncMock(return_value=[prop])),
    ):
        await handle_list_favorites(mock_msg, mock_session)
        mock_msg.answer.assert_awaited()

    # 3. Add favorite callback
    mock_fav_cb = AsyncMock(spec=CallbackQuery)
    mock_fav_cb.data = "search_prop:fav:42"
    mock_fav_cb.from_user = TgUser(id=777, is_bot=False, first_name="Buyer")
    mock_fav_cb.message = AsyncMock(spec=Message)
    mock_fav_cb.message.edit_reply_markup = AsyncMock()
    mock_fav_cb.answer = AsyncMock()

    with (
        patch.object(UserService, "get_by_telegram_id", new=AsyncMock(return_value=user)),
        patch.object(FavoriteService, "add_favorite", new=AsyncMock()),
    ):
        await handle_add_favorite_callback(mock_fav_cb, mock_session)
        mock_fav_cb.answer.assert_awaited_once_with(get_text("fav_added_alert", "uz"))
        mock_fav_cb.message.edit_reply_markup.assert_awaited_once()

    # 4. Remove favorite callback
    mock_unfav_cb = AsyncMock(spec=CallbackQuery)
    mock_unfav_cb.data = "search_prop:unfav:42"
    mock_unfav_cb.from_user = TgUser(id=777, is_bot=False, first_name="Buyer")
    mock_unfav_cb.message = AsyncMock(spec=Message)
    mock_unfav_cb.message.edit_reply_markup = AsyncMock()
    mock_unfav_cb.answer = AsyncMock()

    with (
        patch.object(UserService, "get_by_telegram_id", new=AsyncMock(return_value=user)),
        patch.object(FavoriteService, "remove_favorite", new=AsyncMock(return_value=True)),
    ):
        await handle_remove_favorite_callback(mock_unfav_cb, mock_session)
        mock_unfav_cb.answer.assert_awaited_once_with(get_text("fav_removed_alert", "uz"))
        mock_unfav_cb.message.edit_reply_markup.assert_awaited_once()

    # 5. View property details callback
    mock_view_cb = AsyncMock(spec=CallbackQuery)
    mock_view_cb.data = "search_prop:view:42"
    mock_view_cb.from_user = TgUser(id=777, is_bot=False, first_name="Buyer")
    mock_view_cb.message = AsyncMock(spec=Message)
    mock_view_cb.message.answer = AsyncMock()
    mock_view_cb.answer = AsyncMock()

    with (
        patch.object(UserService, "get_by_telegram_id", new=AsyncMock(return_value=user)),
        patch.object(
            PropertySearchService, "get_approved_details", new=AsyncMock(return_value=prop)
        ),
        patch.object(FavoriteService, "is_favorite", new=AsyncMock(return_value=True)),
    ):
        await handle_view_property_details(mock_view_cb, mock_session)
        mock_view_cb.answer.assert_awaited_once()
        mock_view_cb.message.answer.assert_awaited_once()
        sent_details = mock_view_cb.message.answer.call_args[0][0]
        assert "Yunusobod" in sent_details
        assert "99" not in sent_details


def make_message_update(user_id: int, text: str, update_id: int = 1) -> Update:
    """Create an Update with a Message for integration testing."""
    chat = Chat(id=user_id, type="private")
    from_user = TgUser(id=user_id, is_bot=False, first_name="Tester")
    msg = Message(
        message_id=update_id,
        date=datetime.now(UTC),
        chat=chat,
        from_user=from_user,
        text=text,
    )
    return Update(update_id=update_id, message=msg)


@pytest.mark.asyncio
async def test_dispatcher_real_routing_regression(db_session: AsyncSession) -> None:
    """Integration test verifying real dispatcher routing for search, favorites, and submission."""
    # 1. Seed real registered Uzbek user
    user_uz = User(
        telegram_id=555111,
        language="uz",
        first_name="RealTester",
        phone="+998901112233",
        consent_accepted_at=datetime.now(UTC),
    )
    # 2. Seed real registered Russian user
    user_ru = User(
        telegram_id=555222,
        language="ru",
        first_name="RuTester",
        phone="+998902223344",
        consent_accepted_at=datetime.now(UTC),
    )
    db_session.add_all([user_uz, user_ru])
    await db_session.flush()

    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    def get_last_sent_text() -> str:
        for call in reversed(mock_bot.mock_calls):
            if len(call.args) > 0 and call.args[0].__class__.__name__ == "SendMessage":
                return str(call.args[0].text)
        return ""

    # 1. Exact Uzbek: 🏠 Uy sotib olish starts sale search
    update_sale = make_message_update(555111, "🏠 Uy sotib olish", 101)
    await dp.feed_update(mock_bot, update_sale, session=db_session)

    fsm_uz = dp.fsm.get_context(mock_bot, chat_id=555111, user_id=555111)
    assert await fsm_uz.get_state() == PropertySearchStates.choosing_property_type
    assert (await fsm_uz.get_data())["listing_type"] == "sale"
    assert get_text("search_start_sale", "uz") in get_last_sent_text()

    # 2. Exact Uzbek: 🔑 Uy ijaraga olish starts rent search
    update_rent = make_message_update(555111, "🔑 Uy ijaraga olish", 102)
    await dp.feed_update(mock_bot, update_rent, session=db_session)
    assert await fsm_uz.get_state() == PropertySearchStates.choosing_property_type
    assert (await fsm_uz.get_data())["listing_type"] == "rent"
    assert get_text("search_start_rent", "uz") in get_last_sent_text()

    # 3. Exact Russian: 🏠 Купить недвижимость starts sale search
    update_ru_sale = make_message_update(555222, "🏠 Купить недвижимость", 103)
    await dp.feed_update(mock_bot, update_ru_sale, session=db_session)

    fsm_ru = dp.fsm.get_context(mock_bot, chat_id=555222, user_id=555222)
    assert await fsm_ru.get_state() == PropertySearchStates.choosing_property_type
    assert (await fsm_ru.get_data())["listing_type"] == "sale"
    assert get_text("search_start_sale", "ru") in get_last_sent_text()

    # 4. Exact Russian: 🔑 Снять недвижимость starts rent search
    update_ru_rent = make_message_update(555222, "🔑 Снять недвижимость", 104)
    await dp.feed_update(mock_bot, update_ru_rent, session=db_session)
    assert await fsm_ru.get_state() == PropertySearchStates.choosing_property_type
    assert (await fsm_ru.get_data())["listing_type"] == "rent"
    assert get_text("search_start_rent", "ru") in get_last_sent_text()

    # 5. Stale state interference: user in middle of search clicking sale menu starts fresh
    await fsm_uz.set_state(PropertySearchStates.waiting_region)
    update_fresh = make_message_update(555111, "🏠 Uy sotib olish", 105)
    await dp.feed_update(mock_bot, update_fresh, session=db_session)
    assert await fsm_uz.get_state() == PropertySearchStates.choosing_property_type
    assert (await fsm_uz.get_data())["listing_type"] == "sale"

    # 6. Favorites works via dispatcher
    update_fav = make_message_update(555111, "❤️ Saqlangan uylar", 106)
    await dp.feed_update(mock_bot, update_fav, session=db_session)
    assert get_text("saved_properties_empty", "uz") in get_last_sent_text()

    # 7. Phase 3 property submission works via dispatcher
    update_sell = make_message_update(555111, "💰 Uyimni sotish", 107)
    await dp.feed_update(mock_bot, update_sell, session=db_session)
    from app.bot.states import PropertySubmissionStates

    assert await fsm_uz.get_state() == PropertySubmissionStates.waiting_property_type

    # 8. Unregistered user attempting to search receives prompt to register
    update_unregistered = make_message_update(999888, "🏠 Uy sotib olish", 108)
    await dp.feed_update(mock_bot, update_unregistered, session=db_session)
    assert "avval ro‘yxatdan o‘tishni yakunlang" in get_last_sent_text()

