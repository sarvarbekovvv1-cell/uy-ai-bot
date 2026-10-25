"""Telegram bot keyboard builders for menus, registration, settings, and properties."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from app.bot.locales import LOCALES, get_text

MAIN_MENU_BUTTON_KEYS = (
    "btn_buy",
    "btn_rent",
    "btn_sell",
    "btn_lease",
    "btn_valuation",
    "btn_map",
    "btn_ai_broker",
    "btn_favorites",
    "btn_appointments",
    "btn_contact_broker",
    "btn_my_properties",
    "btn_settings",
)

MAIN_MENU_BUTTONS: set[str] = {
    locale_dict[key]
    for locale_dict in LOCALES.values()
    for key in MAIN_MENU_BUTTON_KEYS
    if key in locale_dict
} | {
    "🏠 Uy sotib olish",
    "🏠 Купить недвижимость",
    "🔑 Uy ijaraga olish",
    "🔑 Арендовать недвижимость",
    "🔑 Снять недвижимость",
    "💰 Uyimni sotish",
    "💰 Продать недвижимость",
    "🏡 Uyimni ijaraga berish",
    "🏡 Сдать в аренду",
    "❤️ Saqlangan uylar",
    "❤️ Сохраненные",
    "🏘 Mening e'lonlarim",
    "🏘 Мои объявления",
    "⚙️ Sozlamalar",
    "⚙️ Настройки",
}


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
                KeyboardButton(text=get_text("btn_my_properties", lang)),
                KeyboardButton(text=get_text("btn_settings", lang)),
            ],
        ],
        resize_keyboard=True,
        persistent=True,
    )


def get_property_type_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Build inline keyboard for property types."""
    labels = {
        "uz": {
            "apartment": "🏢 Kvartira",
            "house": "🏡 Hovli / Uy",
            "commercial": "🏬 Tijorat binosi",
            "land": "🌱 Yer uchastkasi",
        },
        "ru": {
            "apartment": "🏢 Квартира",
            "house": "🏡 Дом / Участок",
            "commercial": "🏬 Коммерческая",
            "land": "🌱 Земельный участок",
        },
    }
    loc = labels.get(lang, labels["uz"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=loc["apartment"], callback_data="proptype:apartment"),
                InlineKeyboardButton(text=loc["house"], callback_data="proptype:house"),
            ],
            [
                InlineKeyboardButton(text=loc["commercial"], callback_data="proptype:commercial"),
                InlineKeyboardButton(text=loc["land"], callback_data="proptype:land"),
            ],
        ]
    )


def get_location_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Build reply keyboard for sending location or skipping."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=get_text("btn_send_location", lang),
                    request_location=True,
                )
            ],
            [KeyboardButton(text=get_text("btn_skip", lang))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def get_condition_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Build inline keyboard for property conditions."""
    labels = {
        "uz": {
            "new": "✨ Yangi ta'mir",
            "renovated": "🛠 Yaxshi ta'mir",
            "needs_renovation": "🏚 Ta'mirtalab",
            "shell": "🧱 Qora suvoq",
        },
        "ru": {
            "new": "✨ Новый ремонт",
            "renovated": "🛠 Хороший ремонт",
            "needs_renovation": "🏚 Требует ремонта",
            "shell": "🧱 Черновая отделка",
        },
    }
    loc = labels.get(lang, labels["uz"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=loc["new"], callback_data="propcond:new"),
                InlineKeyboardButton(text=loc["renovated"], callback_data="propcond:renovated"),
            ],
            [
                InlineKeyboardButton(
                    text=loc["needs_renovation"], callback_data="propcond:needs_renovation"
                ),
                InlineKeyboardButton(text=loc["shell"], callback_data="propcond:shell"),
            ],
        ]
    )


def get_furniture_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Build inline keyboard for furniture presence."""
    labels = {
        "uz": {"yes": "🛋 Bor", "no": "❌ Yo‘q"},
        "ru": {"yes": "🛋 Есть", "no": "❌ Нет"},
    }
    loc = labels.get(lang, labels["uz"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=loc["yes"], callback_data="propfurn:yes"),
                InlineKeyboardButton(text=loc["no"], callback_data="propfurn:no"),
            ]
        ]
    )


def get_cadastre_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Build inline keyboard for cadastre status."""
    labels = {
        "uz": {
            "available": "📄 Mavjud",
            "in_process": "⏳ Jarayonda",
            "not_available": "❌ Mavjud emas",
            "unknown": "❓ Noma'lum",
        },
        "ru": {
            "available": "📄 Есть",
            "in_process": "⏳ В процессе",
            "not_available": "❌ Нет",
            "unknown": "❓ Неизвестно",
        },
    }
    loc = labels.get(lang, labels["uz"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=loc["available"], callback_data="propcad:available"),
                InlineKeyboardButton(text=loc["in_process"], callback_data="propcad:in_process"),
            ],
            [
                InlineKeyboardButton(
                    text=loc["not_available"], callback_data="propcad:not_available"
                ),
                InlineKeyboardButton(text=loc["unknown"], callback_data="propcad:unknown"),
            ],
        ]
    )


def get_currency_keyboard() -> InlineKeyboardMarkup:
    """Build inline keyboard for supported currencies."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💵 USD ($)", callback_data="propcurr:USD"),
                InlineKeyboardButton(text="🇺🇿 UZS (so‘m)", callback_data="propcurr:UZS"),
            ]
        ]
    )


def get_negotiable_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Build inline keyboard for negotiable price."""
    labels = {
        "uz": {"yes": "🤝 Kelishiladi", "no": "🔒 Bo‘lishi shu"},
        "ru": {"yes": "🤝 Торг уместен", "no": "🔒 Без торга"},
    }
    loc = labels.get(lang, labels["uz"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=loc["yes"], callback_data="propneg:yes"),
                InlineKeyboardButton(text=loc["no"], callback_data="propneg:no"),
            ]
        ]
    )


def get_photos_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Build reply keyboard during photo upload stage."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_text("btn_photos_ready", lang))],
            [KeyboardButton(text=get_text("btn_cancel_submit", lang))],
        ],
        resize_keyboard=True,
    )


def get_submission_confirm_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Build inline keyboard for final property listing confirmation."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("btn_confirm_submit", lang), callback_data="propsubmit:confirm"
                ),
                InlineKeyboardButton(
                    text=get_text("btn_cancel_submit", lang), callback_data="propsubmit:cancel"
                ),
            ]
        ]
    )


def get_review_action_keyboard(property_id: int) -> InlineKeyboardMarkup:
    """Build inline keyboard for staff review actions."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Tasdiqlash", callback_data=f"review_act:approve:{property_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Rad etish", callback_data=f"review_act:reject:{property_id}"
                ),
            ]
        ]
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


def get_search_property_type_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Build reply keyboard for selecting property type in search."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_text("btn_type_all", lang))],
            [
                KeyboardButton(text=get_text("type_apartment", lang)),
                KeyboardButton(text=get_text("type_house", lang)),
            ],
            [
                KeyboardButton(text=get_text("type_commercial", lang)),
                KeyboardButton(text=get_text("type_land", lang)),
            ],
            [KeyboardButton(text=get_text("btn_cancel_submit", lang))],
        ],
        resize_keyboard=True,
    )


def get_search_skip_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Build reply keyboard with a skip option."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_text("btn_skip", lang))],
            [KeyboardButton(text=get_text("btn_cancel_submit", lang))],
        ],
        resize_keyboard=True,
    )


def get_search_rooms_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Build reply keyboard for choosing rooms in search."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1"), KeyboardButton(text="2"), KeyboardButton(text="3")],
            [KeyboardButton(text="4"), KeyboardButton(text="5+")],
            [
                KeyboardButton(text=get_text("btn_rooms_any", lang)),
                KeyboardButton(text=get_text("btn_cancel_submit", lang)),
            ],
        ],
        resize_keyboard=True,
    )


def get_search_currency_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Build reply keyboard for currency selection with skip option."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="USD"), KeyboardButton(text="UZS")],
            [
                KeyboardButton(text=get_text("btn_skip", lang)),
                KeyboardButton(text=get_text("btn_cancel_submit", lang)),
            ],
        ],
        resize_keyboard=True,
    )


def get_property_card_keyboard(
    property_id: int, is_fav: bool = False, lang: str = "uz"
) -> InlineKeyboardMarkup:
    """Build inline keyboard for a search result card."""
    fav_btn_text = get_text("btn_fav_remove" if is_fav else "btn_fav_add", lang)
    fav_callback = f"search_prop:{'unfav' if is_fav else 'fav'}:{property_id}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("btn_details", lang),
                    callback_data=f"search_prop:view:{property_id}",
                ),
                InlineKeyboardButton(text=fav_btn_text, callback_data=fav_callback),
            ]
        ]
    )


def get_search_pagination_keyboard(
    current_page: int, total_pages: int, lang: str = "uz"
) -> InlineKeyboardMarkup:
    """Build pagination inline keyboard for search result pages."""
    nav_buttons: list[InlineKeyboardButton] = []
    if current_page > 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text=get_text("btn_prev", lang),
                callback_data=f"search_page:{current_page - 1}",
            )
        )
    nav_buttons.append(
        InlineKeyboardButton(
            text=f"{current_page}/{total_pages}",
            callback_data="search_nav:noop",
        )
    )
    if current_page < total_pages:
        nav_buttons.append(
            InlineKeyboardButton(
                text=get_text("btn_next", lang),
                callback_data=f"search_page:{current_page + 1}",
            )
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            nav_buttons,
            [
                InlineKeyboardButton(
                    text=get_text("btn_restart_search", lang),
                    callback_data="search_nav:restart",
                )
            ],
        ]
    )


def get_search_restart_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Build inline keyboard offering to restart search."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("btn_restart_search", lang),
                    callback_data="search_nav:restart",
                )
            ]
        ]
    )


def get_remove_keyboard() -> ReplyKeyboardRemove:
    """Return helper removing reply keyboard."""
    return ReplyKeyboardRemove()


# --- Phase 5: Appointments, Viewing, & Broker Contact Keyboards ---


def get_property_details_keyboard(
    property_id: int, is_fav: bool = False, lang: str = "uz"
) -> InlineKeyboardMarkup:
    """Build action keyboard for detailed property view."""
    fav_btn_text = get_text("btn_fav_remove" if is_fav else "btn_fav_add", lang)
    fav_callback = f"search_prop:{'unfav' if is_fav else 'fav'}:{property_id}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("btn_book_viewing", lang),
                    callback_data=f"viewing:create:{property_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("btn_contact_broker_action", lang),
                    callback_data=f"broker:contact:{property_id}",
                )
            ],
            [
                InlineKeyboardButton(text=fav_btn_text, callback_data=fav_callback),
            ],
        ]
    )


def get_viewing_date_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Build inline keyboard for viewing date selection."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("btn_date_today", lang),
                    callback_data="view_date:today",
                ),
                InlineKeyboardButton(
                    text=get_text("btn_date_tomorrow", lang),
                    callback_data="view_date:tomorrow",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=get_text("btn_date_custom", lang),
                    callback_data="view_date:custom",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("btn_cancel_request", lang),
                    callback_data="view_date:cancel",
                )
            ],
        ]
    )


def get_viewing_time_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Build inline keyboard for structured viewing time slots."""
    times = [
        "09:00",
        "10:00",
        "11:00",
        "12:00",
        "14:00",
        "15:00",
        "16:00",
        "17:00",
        "18:00",
    ]
    rows: list[list[InlineKeyboardButton]] = []
    current_row: list[InlineKeyboardButton] = []

    for t in times:
        current_row.append(InlineKeyboardButton(text=f"🕐 {t}", callback_data=f"view_time:{t}"))
        if len(current_row) == 3:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)

    rows.append(
        [
            InlineKeyboardButton(
                text=get_text("btn_cancel_request", lang),
                callback_data="view_time:cancel",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_viewing_confirm_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Build confirmation inline keyboard for submitting viewing request."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("btn_send_request", lang),
                    callback_data="view_confirm:yes",
                ),
                InlineKeyboardButton(
                    text=get_text("btn_cancel_request", lang),
                    callback_data="view_confirm:no",
                ),
            ]
        ]
    )


def get_broker_contact_confirm_keyboard(property_id: int, lang: str = "uz") -> InlineKeyboardMarkup:
    """Build inline keyboard to confirm broker contact request."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("btn_send_request", lang),
                    callback_data=f"broker_contact:confirm:{property_id}",
                ),
                InlineKeyboardButton(
                    text=get_text("btn_cancel_request", lang),
                    callback_data="broker_contact:cancel",
                ),
            ]
        ]
    )


def get_appointment_card_keyboard(
    request_id: int, cancellable: bool = True, lang: str = "uz"
) -> InlineKeyboardMarkup:
    """Build inline keyboard for customer appointment card."""
    buttons: list[list[InlineKeyboardButton]] = []
    if cancellable:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=get_text("btn_cancel_request", lang),
                    callback_data=f"req:cancel:{request_id}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_appointment_cancel_confirm_keyboard(
    request_id: int, lang: str = "uz"
) -> InlineKeyboardMarkup:
    """Build confirmation keyboard for cancelling appointment."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("btn_confirm_cancel", lang),
                    callback_data=f"req:cancel_confirm:{request_id}",
                ),
                InlineKeyboardButton(
                    text=get_text("btn_keep_request", lang),
                    callback_data="req:cancel_back",
                ),
            ]
        ]
    )


def get_broker_request_card_keyboard(
    request_id: int,
    status: str,
    is_assigned_to_me: bool = False,
    lang: str = "uz",
) -> InlineKeyboardMarkup:
    """Build actions keyboard for staff broker managing a viewing request."""
    rows: list[list[InlineKeyboardButton]] = []

    if status == "pending" and not is_assigned_to_me:
        rows.append(
            [
                InlineKeyboardButton(
                    text=get_text("btn_claim_request", lang),
                    callback_data=f"broker_req:claim:{request_id}",
                )
            ]
        )
    elif status in ("pending", "assigned") and is_assigned_to_me:
        rows.append(
            [
                InlineKeyboardButton(
                    text=get_text("btn_accept_request", lang),
                    callback_data=f"broker_req:accept:{request_id}",
                ),
                InlineKeyboardButton(
                    text=get_text("btn_reject_request", lang),
                    callback_data=f"broker_req:reject:{request_id}",
                ),
            ]
        )
    elif status == "accepted":
        rows.append(
            [
                InlineKeyboardButton(
                    text=get_text("btn_complete_request", lang),
                    callback_data=f"broker_req:complete:{request_id}",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_broker_outcome_keyboard(request_id: int, lang: str = "uz") -> InlineKeyboardMarkup:
    """Build outcome selection keyboard for completing a viewing."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("outcome_interested", lang),
                    callback_data=f"broker_out:interested:{request_id}",
                ),
                InlineKeyboardButton(
                    text=get_text("outcome_not_interested", lang),
                    callback_data=f"broker_out:not_interested:{request_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=get_text("outcome_reschedule", lang),
                    callback_data=f"broker_out:reschedule_requested:{request_id}",
                ),
                InlineKeyboardButton(
                    text=get_text("outcome_no_show", lang),
                    callback_data=f"broker_out:no_show:{request_id}",
                ),
            ],
        ]
    )
