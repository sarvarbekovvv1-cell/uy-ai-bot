"""Localization helper utilities and property attribute formatters."""

from app.bot.locales.en import MESSAGES as EN_MESSAGES
from app.bot.locales.ru import MESSAGES as RU_MESSAGES
from app.bot.locales.uz import MESSAGES as UZ_MESSAGES

LOCALES: dict[str, dict[str, str]] = {
    "uz": UZ_MESSAGES,
    "ru": RU_MESSAGES,
    "en": EN_MESSAGES,
}


def get_text(key: str, lang: str = "uz", default: str = "") -> str:
    """Retrieve localized message string by key and language code."""
    locale = LOCALES.get(lang, UZ_MESSAGES)
    if key in locale:
        return locale[key]
    # Fallback to Uzbek, then to provided default
    return UZ_MESSAGES.get(key, default or key)


CONDITION_TRANSLATIONS: dict[str, dict[str, str]] = {
    "uz": {
        "new": "Yangi ta'mir (evro)",
        "renovated": "Ta'mirlangan (yaxshi)",
        "needs_renovation": "Ta'mirtalab",
        "shell": "Qora suvoq (korobka)",
    },
    "ru": {
        "new": "Новый ремонт (евро)",
        "renovated": "С ремонтом (хороший)",
        "needs_renovation": "Требует ремонта",
        "shell": "Черновая отделка (коробка)",
    },
    "en": {
        "new": "Newly renovated",
        "renovated": "Renovated (good condition)",
        "needs_renovation": "Needs renovation",
        "shell": "Shell & core (rough finish)",
    },
}

CADASTRE_TRANSLATIONS: dict[str, dict[str, str]] = {
    "uz": {
        "available": "Mavjud (bor)",
        "in_process": "Jarayonda",
        "not_available": "Mavjud emas (yo'q)",
        "unknown": "Noma'lum",
    },
    "ru": {
        "available": "Есть (в наличии)",
        "in_process": "В процессе оформления",
        "not_available": "Нет",
        "unknown": "Неизвестно",
    },
    "en": {
        "available": "Available",
        "in_process": "In process",
        "not_available": "Not available",
        "unknown": "Unknown",
    },
}

PROPERTY_TYPE_TRANSLATIONS: dict[str, dict[str, str]] = {
    "uz": {
        "apartment": "Kvartira",
        "house": "Hovli / Uy",
        "commercial": "Tijorat",
        "land": "Yer uchastkasi",
    },
    "ru": {
        "apartment": "Квартира",
        "house": "Дом / Коттедж",
        "commercial": "Коммерческая",
        "land": "Земельный участок",
    },
    "en": {
        "apartment": "Apartment",
        "house": "House / Villa",
        "commercial": "Commercial",
        "land": "Land plot",
    },
}

LISTING_TYPE_TRANSLATIONS: dict[str, dict[str, str]] = {
    "sale": {
        "uz": "Sotuv",
        "ru": "Продажа",
        "en": "Sale",
    },
    "rent": {
        "uz": "Ijara",
        "ru": "Аренда",
        "en": "Rent",
    },
    "lease": {
        "uz": "Ijara",
        "ru": "Аренда",
        "en": "Rent",
    },
}

FURNITURE_TRANSLATIONS: dict[str, dict[bool, str]] = {
    "uz": {True: "Bor", False: "Yo‘q"},
    "ru": {True: "Есть", False: "Нет"},
    "en": {True: "Furnished", False: "Unfurnished"},
}


def format_condition(condition: str | None, lang: str = "uz") -> str:
    """Format property condition into human-readable localized text."""
    if not condition:
        return "—"
    key = str(condition).strip().lower()
    loc_dict = CONDITION_TRANSLATIONS.get(lang, CONDITION_TRANSLATIONS["uz"])
    if key in loc_dict:
        return loc_dict[key]
    return CONDITION_TRANSLATIONS["uz"].get(key, condition.capitalize())


def format_cadastre(cadastre_status: str | None, lang: str = "uz") -> str:
    """Format cadastre status into human-readable localized text."""
    if not cadastre_status:
        return "—"
    key = str(cadastre_status).strip().lower()
    loc_dict = CADASTRE_TRANSLATIONS.get(lang, CADASTRE_TRANSLATIONS["uz"])
    if key in loc_dict:
        return loc_dict[key]
    return CADASTRE_TRANSLATIONS["uz"].get(key, cadastre_status)


def format_property_type(prop_type: str | None, lang: str = "uz") -> str:
    """Format property type into human-readable localized text."""
    if not prop_type:
        return "—"
    key = str(prop_type).strip().lower()
    loc_dict = PROPERTY_TYPE_TRANSLATIONS.get(lang, PROPERTY_TYPE_TRANSLATIONS["uz"])
    if key in loc_dict:
        return loc_dict[key]
    return PROPERTY_TYPE_TRANSLATIONS["uz"].get(key, prop_type.capitalize())


def format_listing_type(listing_type: str | None, lang: str = "uz") -> str:
    """Format listing type into human-readable localized text."""
    if not listing_type:
        return "—"
    key = str(listing_type).strip().lower()
    type_dict = LISTING_TYPE_TRANSLATIONS.get(key)
    if type_dict:
        return type_dict.get(lang, type_dict.get("uz", listing_type.upper()))
    return listing_type.upper()


def format_furniture(has_furniture: bool | None, lang: str = "uz") -> str:
    """Format furniture presence into human-readable localized text."""
    val = bool(has_furniture)
    loc_dict = FURNITURE_TRANSLATIONS.get(lang, FURNITURE_TRANSLATIONS["uz"])
    return loc_dict.get(val, "Bor" if val else "Yo‘q")


__all__ = [
    "get_text",
    "LOCALES",
    "UZ_MESSAGES",
    "RU_MESSAGES",
    "EN_MESSAGES",
    "format_condition",
    "format_cadastre",
    "format_property_type",
    "format_listing_type",
    "format_furniture",
]
