"""Telegram bot keyboard builders for menus, registration, and settings."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from app.bot.locales import get_text


def get_language_keyboard() -> InlineKeyboardMarkup:
    """Build inline keyboard for language selection."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇿 O‘zbekcha", callback_data="lang:uz"),
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
            ]
        ]
    )


def get_consent_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Build inline keyboard for terms and privacy consent."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("btn_consent_accept", lang), callback_data="consent:accept"
                ),
                InlineKeyboardButton(
                    text=get_text("btn_consent_decline", lang), callback_data="consent:decline"
                ),
            ]
        ]
    )


def get_phone_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Build reply keyboard requesting contact with phone number."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=get_text("btn_send_phone", lang),
                    request_contact=True,
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def get_main_menu_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Build main customer navigation reply keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=get_text("btn_buy", lang)),
                KeyboardButton(text=get_text("btn_rent", lang)),
            ],
            [
                KeyboardButton(text=get_text("btn_sell", lang)),
                KeyboardButton(text=get_text("btn_lease", lang)),
            ],
            [
                KeyboardButton(text=get_text("btn_valuation", lang)),
                KeyboardButton(text=get_text("btn_map", lang)),
            ],
            [
                KeyboardButton(text=get_text("btn_ai_broker", lang)),
                KeyboardButton(text=get_text("btn_favorites", lang)),
            ],
            [
                KeyboardButton(text=get_text("btn_appointments", lang)),
                KeyboardButton(text=get_text("btn_contact_broker", lang)),
            ],
            [
                KeyboardButton(text=get_text("btn_settings", lang)),
            ],
        ],
        resize_keyboard=True,
        persistent=True,
    )


def get_settings_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Build inline keyboard for settings management."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("btn_change_language", lang),
                    callback_data="settings:change_lang",
                )
            ]
        ]
    )


def get_remove_keyboard() -> ReplyKeyboardRemove:
    """Return helper removing reply keyboard."""
    return ReplyKeyboardRemove()
