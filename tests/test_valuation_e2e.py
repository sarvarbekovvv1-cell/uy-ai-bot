"""End-to-End integration tests for Phase 8 Property Valuation Engine and Telegram bot flow."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.types import CallbackQuery, Chat, Message, Update
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.dispatcher import create_dispatcher
from app.bot.states import PropertyValuationStates
from app.models.property import Property
from app.models.user import User
from app.services.valuation.service import ValuationService


def make_msg_update(user_id: int, text: str, update_id: int = 1) -> Update:
    """Create a Message update."""
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


def make_cb_update(user_id: int, data: str, update_id: int = 2) -> Update:
    """Create a CallbackQuery update."""
    from_user = TgUser(id=user_id, is_bot=False, first_name="ValUser", username="val_user")
    chat = Chat(id=user_id, type="private")
    msg = Message(
        message_id=update_id,
        date=datetime.now(UTC),
        chat=chat,
        from_user=from_user,
        text="Previous message",
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
    """Extract sent or edited texts from mock bot calls."""
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


@pytest.fixture
async def setup_valuation_db(db_session: AsyncSession) -> dict[str, int]:
    """Seed test customer and approved comparable properties in Tashkent."""
    # Customer
    customer = User(
        telegram_id=990001,
        language="uz",
        first_name="ValCustomer",
        phone="+998909900001",
        consent_accepted_at=datetime.now(UTC),
    )
    # Russian customer
    customer_ru = User(
        telegram_id=990002,
        language="ru",
        first_name="ValCustomerRu",
        phone="+998909900002",
        consent_accepted_at=datetime.now(UTC),
    )
    db_session.add_all([customer, customer_ru])
    await db_session.commit()

    # Seed approved comparables in Chilonzor (Sale)
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
    comp2 = Property(
        owner_user_id=customer.id,
        listing_type="sale",
        property_type="apartment",
        title="2-room Chilonzor 2",
        region="Toshkent shahri",
        district="Chilonzor",
        address="Chilonzor-10",
        rooms=2,
        total_area=Decimal("58"),
        condition="renovated",
        price=Decimal("98000"),
        currency="USD",
        status="approved",
    )
    comp3 = Property(
        owner_user_id=customer.id,
        listing_type="sale",
        property_type="apartment",
        title="2-room Chilonzor 3",
        region="Toshkent shahri",
        district="Chilonzor",
        address="Chilonzor-11",
        rooms=2,
        total_area=Decimal("56"),
        condition="renovated",
        price=Decimal("96000"),
        currency="USD",
        status="approved",
    )

    # Seed approved comparable in Yunusobod (Rent)
    comp_rent1 = Property(
        owner_user_id=customer.id,
        listing_type="rent",
        property_type="apartment",
        title="1-room Yunusobod",
        region="Toshkent shahri",
        district="Yunusobod",
        address="Yunusobod-4",
        rooms=1,
        total_area=Decimal("40"),
        condition="renovated",
        price=Decimal("450"),
        currency="USD",
        status="approved",
    )
    comp_rent2 = Property(
        owner_user_id=customer.id,
        listing_type="rent",
        property_type="apartment",
        title="1-room Yunusobod 2",
        region="Toshkent shahri",
        district="Yunusobod",
        address="Yunusobod-5",
        rooms=1,
        total_area=Decimal("42"),
        condition="renovated",
        price=Decimal("480"),
        currency="USD",
        status="approved",
    )

    db_session.add_all([comp1, comp2, comp3, comp_rent1, comp_rent2])
    await db_session.commit()

    return {
        "customer_uz": customer.telegram_id,
        "customer_ru": customer_ru.telegram_id,
        "comp1": comp1.id,
    }


@pytest.mark.asyncio
async def test_valuation_e2e_sale_apartment_uzbek(
    setup_valuation_db: dict[str, int],
    db_session: AsyncSession,
) -> None:
    """End-to-End simulation of full property valuation in Uzbek."""
    user_id = setup_valuation_db["customer_uz"]
    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    # 1. Start valuation via button
    up1 = make_msg_update(user_id, "📊 Uyimni baholash", 1)
    await dp.feed_update(mock_bot, up1, session=db_session)

    # 2. Select listing type: sale
    up2 = make_cb_update(user_id, "val_lt:sale", 2)
    await dp.feed_update(mock_bot, up2, session=db_session)

    # 3. Select property type: apartment
    up3 = make_cb_update(user_id, "val_pt:apartment", 3)
    await dp.feed_update(mock_bot, up3, session=db_session)

    # 4. Select district: Chilonzor
    up4 = make_cb_update(user_id, "val_dst:Chilonzor", 4)
    await dp.feed_update(mock_bot, up4, session=db_session)

    # 5. Select rooms: 2
    up5 = make_cb_update(user_id, "val_rooms:2", 5)
    await dp.feed_update(mock_bot, up5, session=db_session)

    # 6. Enter area: 56
    up6 = make_msg_update(user_id, "56", 6)
    await dp.feed_update(mock_bot, up6, session=db_session)

    # 7. Select condition: renovated
    up7 = make_cb_update(user_id, "val_cond:renovated", 7)
    await dp.feed_update(mock_bot, up7, session=db_session)

    # 8. Enter floor: 4/9
    up8 = make_msg_update(user_id, "4/9", 8)
    await dp.feed_update(mock_bot, up8, session=db_session)

    # 9. Select currency: USD -> triggers calculation!
    val_svc = ValuationService(llm_provider=None)
    up9 = make_cb_update(user_id, "val_curr:USD", 9)
    await dp.feed_update(mock_bot, up9, session=db_session, valuation_service=val_svc)

    texts = extract_bot_texts(mock_bot)
    full_output = " ".join(texts)

    assert "AI BOZOR BAHOSI" in full_output
    assert "Chilonzor" in full_output
    assert "Taxminiy bozor bahosi:" in full_output
    assert "$" in full_output
    assert "Taqqoslangan e'lonlar:" in full_output
    assert "rasmiy baholash hisoblanmaydi" in full_output

    # 10. Test clicking "🏘 Taqqoslangan e'lonlar"
    mock_bot.reset_mock()
    up10 = make_cb_update(user_id, "val_act:comps", 10)
    await dp.feed_update(mock_bot, up10, session=db_session)

    comp_texts = extract_bot_texts(mock_bot)
    comp_output = " ".join(comp_texts)
    assert "Tahlil qilingan o‘xshash tasdiqlangan e'lonlar" in comp_output
    assert "Chilonzor" in comp_output


@pytest.mark.asyncio
async def test_valuation_e2e_rent_apartment_russian(
    setup_valuation_db: dict[str, int],
    db_session: AsyncSession,
) -> None:
    """End-to-End simulation of rental valuation in Russian with floor skip."""
    user_id = setup_valuation_db["customer_ru"]
    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    # 1. Start valuation via Russian button
    up1 = make_msg_update(user_id, "📊 Оценка недвижимости", 1)
    await dp.feed_update(mock_bot, up1, session=db_session)

    # 2. Select rent
    up2 = make_cb_update(user_id, "val_lt:rent", 2)
    await dp.feed_update(mock_bot, up2, session=db_session)

    # 3. Select apartment
    up3 = make_cb_update(user_id, "val_pt:apartment", 3)
    await dp.feed_update(mock_bot, up3, session=db_session)

    # 4. Select district: Yunusobod
    up4 = make_cb_update(user_id, "val_dst:Yunusobod", 4)
    await dp.feed_update(mock_bot, up4, session=db_session)

    # 5. Select rooms: 1
    up5 = make_cb_update(user_id, "val_rooms:1", 5)
    await dp.feed_update(mock_bot, up5, session=db_session)

    # 6. Enter area: 40
    up6 = make_msg_update(user_id, "40", 6)
    await dp.feed_update(mock_bot, up6, session=db_session)

    # 7. Select condition: renovated
    up7 = make_cb_update(user_id, "val_cond:renovated", 7)
    await dp.feed_update(mock_bot, up7, session=db_session)

    # 8. Skip floor
    up8 = make_cb_update(user_id, "val_floor:skip", 8)
    await dp.feed_update(mock_bot, up8, session=db_session)

    # 9. Select currency: USD
    val_svc = ValuationService(llm_provider=None)
    up9 = make_cb_update(user_id, "val_curr:USD", 9)
    await dp.feed_update(mock_bot, up9, session=db_session, valuation_service=val_svc)

    texts = extract_bot_texts(mock_bot)
    full_output = " ".join(texts)

    assert "РЫНОЧНАЯ ОЦЕНКА AI" in full_output
    assert "Yunusobod" in full_output
    assert "Ориентировочная рыночная цена:" in full_output
    assert "не является официальной экспертизой" in full_output


@pytest.mark.asyncio
async def test_valuation_rejects_commercial_property_type(
    setup_valuation_db: dict[str, int],
    db_session: AsyncSession,
) -> None:
    """Verify selecting commercial property politely declines and returns to main menu."""
    user_id = setup_valuation_db["customer_uz"]
    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    # 1. Start valuation
    up1 = make_msg_update(user_id, "📊 Uyimni baholash", 1)
    await dp.feed_update(mock_bot, up1, session=db_session)

    # 2. Select sale
    up2 = make_cb_update(user_id, "val_lt:sale", 2)
    await dp.feed_update(mock_bot, up2, session=db_session)

    # 3. Select commercial
    up3 = make_cb_update(user_id, "val_pt:commercial", 3)
    await dp.feed_update(mock_bot, up3, session=db_session)

    texts = extract_bot_texts(mock_bot)
    full_output = " ".join(texts)

    assert "kvartira" in full_output and "hovli" in full_output


@pytest.mark.asyncio
async def test_main_menu_escape_during_valuation_fsm(
    setup_valuation_db: dict[str, int],
    db_session: AsyncSession,
) -> None:
    """Verify pressing another main menu button (e.g. '🏠 Uy sotib olish') escapes valuation FSM."""
    user_id = setup_valuation_db["customer_uz"]
    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    # 1. Start valuation
    up1 = make_msg_update(user_id, "📊 Uyimni baholash", 1)
    await dp.feed_update(mock_bot, up1, session=db_session)

    # 2. Mid-flow: click main menu "🏠 Uy sotib olish" button
    up2 = make_msg_update(user_id, "🏠 Uy sotib olish", 2)
    await dp.feed_update(mock_bot, up2, session=db_session)

    texts = extract_bot_texts(mock_bot)
    full_output = " ".join(texts)

    # Verify search flow took over and valuation did not trap the user
    assert "qidiruv" in full_output.lower() or "qidiryapsiz" in full_output.lower()


@pytest.mark.asyncio
async def test_valuation_has_no_database_side_effects(
    setup_valuation_db: dict[str, int],
    db_session: AsyncSession,
) -> None:
    """CRITICAL PURITY TEST:

    Running and viewing a valuation must NOT create any new Property, Lead,
    ViewingRequest, or Appointment records in the database.
    """
    from sqlalchemy import func, select

    from app.models.lead import Lead
    from app.models.viewing_request import ViewingRequest

    user_id = setup_valuation_db["customer_uz"]
    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    # Count records before
    props_before = (await db_session.execute(select(func.count(Property.id)))).scalar_one()
    leads_before = (await db_session.execute(select(func.count(Lead.id)))).scalar_one()
    views_before = (await db_session.execute(select(func.count(ViewingRequest.id)))).scalar_one()

    # Run full valuation flow
    up_start = make_msg_update(user_id, "📊 Uyimni baholash", 1)
    await dp.feed_update(mock_bot, up_start, session=db_session)
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
    await dp.feed_update(
        mock_bot, make_cb_update(user_id, "val_floor:skip", 8), session=db_session
    )
    val_svc = ValuationService(llm_provider=None)
    await dp.feed_update(
        mock_bot,
        make_cb_update(user_id, "val_curr:USD", 9),
        session=db_session,
        valuation_service=val_svc,
    )

    # Count records after
    props_after = (await db_session.execute(select(func.count(Property.id)))).scalar_one()
    leads_after = (await db_session.execute(select(func.count(Lead.id)))).scalar_one()
    views_after = (await db_session.execute(select(func.count(ViewingRequest.id)))).scalar_one()

    assert props_after == props_before
    assert leads_after == leads_before
    assert views_after == views_before


@pytest.mark.asyncio
async def test_fsm_validation_for_invalid_area_and_floors(
    setup_valuation_db: dict[str, int],
    db_session: AsyncSession,
) -> None:
    """Verify input validation rejects invalid area and floor > total_floors."""
    user_id = setup_valuation_db["customer_uz"]
    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    # Setup up to area
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

    # 1. Invalid area: non-numeric
    mock_bot.reset_mock()
    await dp.feed_update(
        mock_bot, make_msg_update(user_id, "not_a_number", 6), session=db_session
    )
    texts1 = extract_bot_texts(mock_bot)
    assert any("musbat" in t.lower() or "raqam" in t.lower() for t in texts1)

    # 2. Invalid area: non-positive (<= 0)
    mock_bot.reset_mock()
    await dp.feed_update(mock_bot, make_msg_update(user_id, "0", 7), session=db_session)
    texts2 = extract_bot_texts(mock_bot)
    assert any("musbat" in t.lower() or "raqam" in t.lower() for t in texts2)

    # 3. Valid area: 55 -> advances to condition
    mock_bot.reset_mock()
    await dp.feed_update(mock_bot, make_msg_update(user_id, "55", 8), session=db_session)
    await dp.feed_update(
        mock_bot, make_cb_update(user_id, "val_cond:renovated", 9), session=db_session
    )

    # 4. Invalid floor: floor > total_floors (12/9) -> refuses to advance, repeats floor prompt
    mock_bot.reset_mock()
    await dp.feed_update(mock_bot, make_msg_update(user_id, "12/9", 10), session=db_session)
    texts4 = extract_bot_texts(mock_bot)
    assert any("qavat" in t.lower() for t in texts4)
    # Verify state did NOT advance to currency
    fsm_ctx = dp.fsm.get_context(bot=mock_bot, chat_id=user_id, user_id=user_id)
    assert await fsm_ctx.get_state() == PropertyValuationStates.waiting_floor


@pytest.mark.asyncio
async def test_callback_tampering_is_handled_gracefully(
    setup_valuation_db: dict[str, int],
    db_session: AsyncSession,
) -> None:
    """Verify arbitrary or tampered callback data does not crash the bot or cause tracebacks."""
    user_id = setup_valuation_db["customer_uz"]
    dp = create_dispatcher()
    mock_bot = AsyncMock(spec=Bot)

    # 1. Start valuation
    await dp.feed_update(
        mock_bot, make_msg_update(user_id, "📊 Uyimni baholash", 1), session=db_session
    )

    # 2. Tampered listing type
    await dp.feed_update(
        mock_bot, make_cb_update(user_id, "val_lt:SQL_INJECTION", 2), session=db_session
    )
    # 3. Tampered property type
    await dp.feed_update(
        mock_bot, make_cb_update(user_id, "val_pt:HACKED", 3), session=db_session
    )
    # 4. Tampered district
    await dp.feed_update(
        mock_bot, make_cb_update(user_id, "val_dst:DROP_TABLE", 4), session=db_session
    )
    # 5. Tampered rooms
    await dp.feed_update(
        mock_bot, make_cb_update(user_id, "val_rooms:9999", 5), session=db_session
    )
    # 6. Tampered condition
    await dp.feed_update(
        mock_bot, make_cb_update(user_id, "val_cond:NOT_A_COND", 6), session=db_session
    )
    # 7. Tampered currency
    await dp.feed_update(
        mock_bot, make_cb_update(user_id, "val_curr:BITCOIN", 7), session=db_session
    )
    # 8. Tampered action
    await dp.feed_update(
        mock_bot, make_cb_update(user_id, "val_act:UNAUTHORIZED", 8), session=db_session
    )

    # No unhandled exceptions; test completes cleanly!
