"""Tests for keyboard generation and FSM registration states."""

from app.bot.keyboards import (
    get_consent_keyboard,
    get_language_keyboard,
    get_main_menu_keyboard,
    get_phone_keyboard,
    get_settings_keyboard,
)
from app.bot.states import RegistrationStates, SettingsStates


def test_registration_state_definitions() -> None:
    """6. Verify registration and settings FSM state group definitions."""
    states = [s.state for s in RegistrationStates.__all_states__]
    assert "RegistrationStates:choosing_language" in states
    assert "RegistrationStates:waiting_consent" in states
    assert "RegistrationStates:waiting_name" in states
    assert "RegistrationStates:waiting_phone" in states

    settings_states = [s.state for s in SettingsStates.__all_states__]
    assert "SettingsStates:changing_language" in settings_states


def test_language_selection_keyboard() -> None:
    """7. Verify language selection inline keyboard structure and callback data."""
    kb = get_language_keyboard()
    assert kb.inline_keyboard is not None
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "lang:uz" in callbacks
    assert "lang:ru" in callbacks


def test_consent_keyboard() -> None:
    """8. Verify privacy and terms consent keyboard callbacks."""
    kb_uz = get_consent_keyboard("uz")
    callbacks_uz = [btn.callback_data for row in kb_uz.inline_keyboard for btn in row]
    assert "consent:accept" in callbacks_uz
    assert "consent:decline" in callbacks_uz

    kb_ru = get_consent_keyboard("ru")
    callbacks_ru = [btn.callback_data for row in kb_ru.inline_keyboard for btn in row]
    assert "consent:accept" in callbacks_ru
    assert "consent:decline" in callbacks_ru


def test_phone_contact_keyboard() -> None:
    """9. Verify phone contact request reply keyboard."""
    kb = get_phone_keyboard("uz")
    assert kb.keyboard is not None
    button = kb.keyboard[0][0]
    assert button.request_contact is True


def test_main_menu_generation() -> None:
    """17. Verify main customer menu generation contains all required buttons."""
    menu_uz = get_main_menu_keyboard("uz")
    buttons_uz = [btn.text for row in menu_uz.keyboard for btn in row]
    assert "🏠 Uy sotib olish" in buttons_uz
    assert "🔑 Uy ijaraga olish" in buttons_uz
    assert "💰 Uyimni sotish" in buttons_uz
    assert "🏡 Uyimni ijaraga berish" in buttons_uz
    assert "📊 Uyimni baholash" in buttons_uz
    assert "📍 Xaritadan uy qidirish" in buttons_uz
    assert "🤖 AI broker" in buttons_uz
    assert "❤️ Saqlangan uylar" in buttons_uz
    assert "📅 Uchrashuvlarim" in buttons_uz
    assert "👨‍💼 Broker bilan bog‘lanish" in buttons_uz
    assert "⚙️ Sozlamalar" in buttons_uz

    menu_ru = get_main_menu_keyboard("ru")
    buttons_ru = [btn.text for row in menu_ru.keyboard for btn in row]
    assert "🏠 Купить недвижимость" in buttons_ru
    assert "⚙️ Настройки" in buttons_ru


def test_settings_keyboard() -> None:
    """Verify settings keyboard structure."""
    kb = get_settings_keyboard("uz")
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "settings:change_lang" in callbacks
