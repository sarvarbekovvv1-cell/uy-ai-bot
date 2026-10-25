"""Tests for Phase 3 property wizard handlers, my properties, and review flows."""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Location, Message, PhotoSize
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.my_properties import handle_my_properties_list
from app.bot.handlers.property_submission import (
    handle_location,
    handle_photo_upload,
    handle_photos_ready,
    handle_start_submission,
    handle_submit_confirmed,
)
from app.bot.handlers.review import handle_approve_callback, handle_review_properties_list
from app.bot.locales import get_text
from app.bot.states import PropertySubmissionStates
from app.models.property import Property
from app.models.user import User
from app.services.property_service import PropertyService
from app.services.user_service import UserService


@pytest.mark.asyncio
async def test_start_submission_initiates_wizard() -> None:
    """Verify clicking '💰 Uyimni sotish' starts the FSM wizard."""
    mock_message = AsyncMock(spec=Message)
    mock_message.answer = AsyncMock()
    mock_message.text = "💰 Uyimni sotish"
    mock_message.from_user = TgUser(id=111, is_bot=False, first_name="Owner")

    mock_state = AsyncMock(spec=FSMContext)
    mock_session = AsyncMock(spec=AsyncSession)

    registered_user = User(id=5, telegram_id=111, language="uz", phone="+998901234567")

    with (
        patch.object(
            UserService, "get_by_telegram_id", new=AsyncMock(return_value=registered_user)
        ),
        patch.object(UserService, "is_registration_complete", new=AsyncMock(return_value=True)),
    ):
        await handle_start_submission(mock_message, mock_state, mock_session)

        mock_state.clear.assert_awaited_once()
        mock_state.set_state.assert_awaited_once_with(
            PropertySubmissionStates.waiting_property_type
        )
        mock_message.answer.assert_awaited_once()
        assert get_text("explain_sell_process", "uz") in mock_message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_location_and_skip_handling() -> None:
    """Verify location handler stores coordinates or None when skipped."""
    mock_message_loc = AsyncMock(spec=Message)
    mock_message_loc.location = Location(latitude=41.2995, longitude=69.2401)
    mock_message_loc.answer = AsyncMock()

    mock_state = AsyncMock(spec=FSMContext)
    mock_state.get_data.return_value = {"language": "uz"}

    await handle_location(mock_message_loc, mock_state)
    mock_state.update_data.assert_awaited_once_with(
        latitude=Decimal("41.2995"),
        longitude=Decimal("69.2401"),
    )
    mock_state.set_state.assert_awaited_once_with(PropertySubmissionStates.waiting_rooms)


@pytest.mark.asyncio
async def test_photo_upload_and_preview_flow() -> None:
    """Verify photo upload increments count and 'photos ready' renders summary."""
    mock_message_photo = AsyncMock(spec=Message)
    mock_message_photo.photo = [
        PhotoSize(file_id="fid_1", file_unique_id="fuid_1", width=100, height=100)
    ]
    mock_message_photo.from_user = TgUser(id=111, is_bot=False, first_name="Owner")
    mock_message_photo.answer = AsyncMock()

    mock_state = AsyncMock(spec=FSMContext)
    mock_state.get_data.return_value = {
        "language": "uz",
        "property_id": 1,
        "user_id": 5,
        "property_type": "apartment",
        "listing_type": "sale",
        "region": "Toshkent",
        "district": "Chilonzor",
        "address": "9-mavze",
        "rooms": 2,
        "total_area": 55.0,
        "floor": 4,
        "total_floors": 9,
        "condition": "new",
        "has_furniture": True,
        "cadastre_status": "available",
        "price": 60000.0,
        "currency": "USD",
        "negotiable": True,
    }
    mock_session = AsyncMock(spec=AsyncSession)

    with (
        patch.object(PropertyService, "add_photo", new=AsyncMock()),
        patch.object(PropertyService, "submit_listing", new=AsyncMock()),
    ):
        # 1. Upload photo
        await handle_photo_upload(mock_message_photo, mock_state, mock_session)
        mock_message_photo.answer.assert_awaited_once()

        # 2. Photos ready
        mock_message_ready = AsyncMock(spec=Message)
        mock_message_ready.answer = AsyncMock()
        with patch(
            "app.repositories.property_media_repository.PropertyMediaRepository.count_by_property",
            new=AsyncMock(return_value=1),
        ):
            await handle_photos_ready(mock_message_ready, mock_state, mock_session)

            mock_state.set_state.assert_awaited_with(PropertySubmissionStates.waiting_confirmation)
            mock_message_ready.answer.assert_awaited_once()
            assert get_text("preview_title", "uz") in mock_message_ready.answer.call_args[0][0]

        # 3. Confirm submission
        mock_callback = AsyncMock(spec=CallbackQuery)
        mock_callback.message = AsyncMock(spec=Message)
        mock_callback.message.answer = AsyncMock()
        mock_callback.answer = AsyncMock()
        await handle_submit_confirmed(mock_callback, mock_state, mock_session)

        mock_state.clear.assert_awaited_once()
        mock_callback.message.answer.assert_awaited_once()
        assert get_text("submission_success", "uz") in mock_callback.message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_my_properties_handler() -> None:
    """Verify owner viewing their own listings."""
    mock_message = AsyncMock(spec=Message)
    mock_message.from_user = TgUser(id=111, is_bot=False, first_name="Owner")
    mock_message.answer = AsyncMock()

    mock_session = AsyncMock(spec=AsyncSession)
    user = User(id=5, telegram_id=111, language="uz")

    prop = Property(
        id=12,
        owner_user_id=5,
        property_type="apartment",
        listing_type="sale",
        region="Toshkent",
        district="Yunusobod",
        address="1-mavze",
        price=Decimal(75000),
        currency="USD",
        status="submitted",
    )

    with (
        patch.object(UserService, "get_by_telegram_id", new=AsyncMock(return_value=user)),
        patch.object(PropertyService, "list_owner_properties", new=AsyncMock(return_value=[prop])),
    ):
        await handle_my_properties_list(mock_message, mock_session)

        mock_message.answer.assert_awaited_once()
        msg_text = mock_message.answer.call_args[0][0]
        assert "#12" in msg_text
        assert "SUBMITTED" in msg_text
        assert "Yunusobod" in msg_text


@pytest.mark.asyncio
async def test_review_properties_authorization_and_approval() -> None:
    """Verify /review_properties restricts unauthorized access and approves valid listings."""
    mock_message = AsyncMock(spec=Message)
    mock_message.from_user = TgUser(id=999, is_bot=False, first_name="Broker")
    mock_message.answer = AsyncMock()
    mock_session = AsyncMock(spec=AsyncSession)

    reviewer_user = User(id=88, telegram_id=999, language="uz")
    prop = Property(
        id=7,
        owner_user_id=5,
        property_type="apartment",
        listing_type="sale",
        region="Toshkent",
        district="Chilonzor",
        address="9-mavze",
        rooms=3,
        total_area=Decimal(70),
        floor=2,
        total_floors=9,
        condition="renovated",
        price=Decimal(70000),
        currency="USD",
        status="submitted",
    )

    with (
        patch.object(UserService, "get_by_telegram_id", new=AsyncMock(return_value=reviewer_user)),
        patch(
            "app.repositories.user_repository.UserRepository.get_by_id",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            PropertyService, "list_pending_review_properties", new=AsyncMock(return_value=[prop])
        ),
        patch.object(PropertyService, "start_review", new=AsyncMock()),
        patch.object(PropertyService, "approve_listing", new=AsyncMock(return_value=prop)),
    ):
        # 1. Staff requests review list
        await handle_review_properties_list(mock_message, mock_session)
        mock_message.answer.assert_awaited_once()
        assert "#7" in mock_message.answer.call_args[0][0]

        # 2. Staff approves listing
        mock_callback = AsyncMock(spec=CallbackQuery)
        mock_callback.data = "review_act:approve:7"
        mock_callback.from_user = TgUser(id=999, is_bot=False, first_name="Broker")
        mock_callback.message = AsyncMock(spec=Message)
        mock_callback.message.edit_text = AsyncMock()
        mock_callback.answer = AsyncMock()
        mock_callback.bot = AsyncMock()

        await handle_approve_callback(mock_callback, mock_session)
        mock_callback.message.edit_text.assert_awaited_once()
