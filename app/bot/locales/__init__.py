"""Localization helper utilities."""

from app.bot.locales.ru import MESSAGES as RU_MESSAGES
from app.bot.locales.uz import MESSAGES as UZ_MESSAGES

LOCALES: dict[str, dict[str, str]] = {
    "uz": UZ_MESSAGES,
    "ru": RU_MESSAGES,
}


def get_text(key: str, lang: str = "uz", default: str = "") -> str:
    """Retrieve localized message string by key and language code."""
    locale = LOCALES.get(lang, UZ_MESSAGES)
    if key in locale:
        return locale[key]
    # Fallback to Uzbek, then to provided default
    return UZ_MESSAGES.get(key, default or key)


__all__ = ["get_text", "LOCALES", "UZ_MESSAGES", "RU_MESSAGES"]
