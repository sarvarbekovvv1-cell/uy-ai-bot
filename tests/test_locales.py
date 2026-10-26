"""Tests for localization dictionaries and phone normalization utility."""

from app.bot.keyboards import get_language_keyboard
from app.bot.locales import (
    format_cadastre,
    format_condition,
    format_furniture,
    format_listing_type,
    format_property_type,
    get_text,
)
from app.bot.locales.en import MESSAGES as EN_MESSAGES
from app.bot.locales.ru import MESSAGES as RU_MESSAGES
from app.bot.locales.uz import MESSAGES as UZ_MESSAGES
from app.utils.phone import normalize_phone_number


def test_phone_normalization() -> None:
    """11. Verify phone normalization for Uzbekistan and international formats."""
    # 9-digit local format without country code
    assert normalize_phone_number("901234567") == "+998901234567"
    assert normalize_phone_number("99 123 45 67") == "+998991234567"

    # 12-digit format with country code
    assert normalize_phone_number("998901234567") == "+998901234567"
    assert normalize_phone_number("+998 (90) 123-45-67") == "+998901234567"

    # International valid numbers
    assert normalize_phone_number("+12025550123") == "+12025550123"

    # Invalid cases
    assert normalize_phone_number("") is None
    assert normalize_phone_number("invalid_phone") is None
    assert normalize_phone_number("123") is None  # Too short
    assert normalize_phone_number("1234567890123456789") is None  # Too long


def test_localization_uzbek() -> None:
    """12. Verify Uzbek localization dictionary contains all mandatory keys."""
    required_keys = [
        "choose_language",
        "consent_text",
        "ask_name",
        "ask_phone",
        "registration_complete",
        "main_menu_title",
        "btn_buy",
        "btn_rent",
        "btn_sell",
        "btn_settings",
        "feature_in_development",
        "help_text",
        "cancel_text",
    ]
    for key in required_keys:
        assert key in UZ_MESSAGES
        assert len(UZ_MESSAGES[key]) > 0
        assert get_text(key, "uz") == UZ_MESSAGES[key]


def test_localization_russian() -> None:
    """13. Verify Russian localization dictionary contains matching keys."""
    assert set(UZ_MESSAGES.keys()) == set(RU_MESSAGES.keys())

    required_keys = [
        "choose_language",
        "consent_text",
        "ask_name",
        "ask_phone",
        "registration_complete",
        "main_menu_title",
        "btn_buy",
        "btn_settings",
        "feature_in_development",
        "help_text",
        "cancel_text",
    ]
    for key in required_keys:
        assert key in RU_MESSAGES
        assert len(RU_MESSAGES[key]) > 0
        assert get_text(key, "ru") == RU_MESSAGES[key]


def test_fallback_localization() -> None:
    """Verify fallback to Uzbek for unknown locales."""
    assert get_text("btn_buy", "unknown") == UZ_MESSAGES["btn_buy"]
    assert get_text("non_existent_key", "uz", default="default_text") == "default_text"


def test_localization_english() -> None:
    """Verify English localization dictionary contains matching keys."""
    assert set(UZ_MESSAGES.keys()) == set(EN_MESSAGES.keys())

    required_keys = [
        "choose_language",
        "consent_text",
        "ask_name",
        "ask_phone",
        "registration_complete",
        "main_menu_title",
        "btn_buy",
        "btn_settings",
        "feature_in_development",
        "help_text",
        "cancel_text",
    ]
    for key in required_keys:
        assert key in EN_MESSAGES
        assert len(EN_MESSAGES[key]) > 0
        assert get_text(key, "en") == EN_MESSAGES[key]


def test_property_attributes_localization() -> None:
    """Verify human-friendly translations for condition and cadastre across 3 languages."""
    # Condition: renovated should never show raw English enum in Uzbek/Russian
    assert format_condition("renovated", "uz") == "Ta'mirlangan (yaxshi)"
    assert format_condition("renovated", "ru") == "С ремонтом (хороший)"
    assert format_condition("renovated", "en") == "Renovated (good condition)"

    assert format_condition("new", "uz") == "Yangi ta'mir (evro)"
    assert format_condition("needs_renovation", "uz") == "Ta'mirtalab"
    assert format_condition("shell", "uz") == "Qora suvoq (korobka)"

    # Cadastre: available should never show raw English enum in Uzbek/Russian
    assert format_cadastre("available", "uz") == "Mavjud (bor)"
    assert format_cadastre("available", "ru") == "Есть (в наличии)"
    assert format_cadastre("available", "en") == "Available"

    assert format_cadastre("in_process", "uz") == "Jarayonda"
    assert format_cadastre("not_available", "uz") == "Mavjud emas (yo'q)"
    assert format_cadastre("unknown", "uz") == "Noma'lum"

    # Property type, listing type, furniture
    assert format_property_type("apartment", "uz") == "Kvartira"
    assert format_property_type("apartment", "en") == "Apartment"
    assert format_listing_type("sale", "uz") == "Sotuv"
    assert format_listing_type("rent", "en") == "Rent"
    assert format_furniture(True, "uz") == "Bor"
    assert format_furniture(False, "uz") == "Yo‘q"
    assert format_furniture(True, "en") == "Furnished"


def test_language_keyboard_options() -> None:
    """Verify 3 languages are presented: Uzbek, Russian, and English."""
    kb = get_language_keyboard()
    callback_data_list = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "lang:uz" in callback_data_list
    assert "lang:ru" in callback_data_list
    assert "lang:en" in callback_data_list
