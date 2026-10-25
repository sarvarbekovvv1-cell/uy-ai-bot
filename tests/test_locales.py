"""Tests for localization dictionaries and phone normalization utility."""

from app.bot.locales import get_text
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
