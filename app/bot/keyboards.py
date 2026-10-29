"""Telegram bot keyboard builders for menus, registration, settings, and properties."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
)

from app.bot.locales import LOCALES, get_text
from app.config import get_settings

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
    "🏠 Buy property",
    "🔑 Rent property",
    "💰 Sell my property",
    "🏡 Lease my property",
    "📊 Estimate property value",
    "📍 Search on map",
    "🤖 AI broker",
    "❤️ Saved properties",
    "📅 My viewings",
    "👨‍💼 Contact broker",
    "🏘 My listings",
    "⚙️ Settings",
}


def get_language_keyboard() -> InlineKeyboardMarkup:
    """Build inline keyboard for language selection."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇿 O‘zbekcha", callback_data="lang:uz"),
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
                InlineKeyboardButton(text="🇺🇸 English", callback_data="lang:en"),
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
    settings = get_settings()
    if settings.miniapp_url and settings.miniapp_url.startswith("https://"):
        map_btn = KeyboardButton(
            text=get_text("btn_map", lang),
            web_app=WebAppInfo(url=settings.miniapp_url),
        )
    else:
        map_btn = KeyboardButton(text=get_text("btn_map", lang))

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
                map_btn,
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
        "en": {
            "apartment": "🏢 Apartment",
            "house": "🏡 House / Villa",
            "commercial": "🏬 Commercial",
            "land": "🌱 Land plot",
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
        "en": {
            "new": "✨ Newly renovated",
            "renovated": "🛠 Renovated",
            "needs_renovation": "🏚 Needs renovation",
            "shell": "🧱 Shell & core",
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
        "en": {"yes": "🛋 Furnished", "no": "❌ Unfurnished"},
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
        "en": {
            "available": "📄 Available",
            "in_process": "⏳ In process",
            "not_available": "❌ Not available",
            "unknown": "❓ Unknown",
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
        "en": {"yes": "🤝 Negotiable", "no": "🔒 Fixed price"},
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


# --- Phase 6: Broker Cabinet & Leads Keyboards ---


def get_broker_cabinet_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Build root menu keyboard for Broker Cabinet."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("btn_unassigned_leads", lang),
                    callback_data="broker_cab:unassigned:0",
                ),
                InlineKeyboardButton(
                    text=get_text("btn_my_leads", lang),
                    callback_data="broker_cab:my:0",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=get_text("btn_tasks_today", lang),
                    callback_data="broker_cab:tasks_today:0",
                ),
                InlineKeyboardButton(
                    text=get_text("btn_tasks_overdue", lang),
                    callback_data="broker_cab:tasks_overdue:0",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=get_text("btn_lead_stats", lang),
                    callback_data="broker_cab:stats",
                )
            ],
        ]
    )


def get_broker_leads_list_keyboard(
    leads: list,
    page: int,
    total_pages: int,
    category: str,
    lang: str = "uz",
) -> InlineKeyboardMarkup:
    """Build list of leads with pagination buttons."""
    rows: list[list[InlineKeyboardButton]] = []

    for lead in leads:
        stage_title = get_text(f"stage_{lead.stage}", lang)
        btn_text = f"#{lead.id} • {stage_title} • #{lead.property_id}"
        rows.append(
            [
                InlineKeyboardButton(
                    text=btn_text,
                    callback_data=f"lead_view:{lead.id}",
                )
            ]
        )

    # Navigation buttons
    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️ Oldingi",
                callback_data=f"broker_cab:{category}:{page - 1}",
            )
        )
    if page < total_pages - 1:
        nav_row.append(
            InlineKeyboardButton(
                text="Keyingi ➡️",
                callback_data=f"broker_cab:{category}:{page + 1}",
            )
        )
    if nav_row:
        rows.append(nav_row)

    rows.append(
        [
            InlineKeyboardButton(
                text=get_text("btn_back_to_cabinet", lang),
                callback_data="broker_cab:home",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_lead_card_keyboard(
    lead_id: int,
    stage: str,
    is_assigned_to_me: bool = False,
    is_unassigned: bool = False,
    lang: str = "uz",
) -> InlineKeyboardMarkup:
    """Build action buttons for a single lead card."""
    rows: list[list[InlineKeyboardButton]] = []

    if is_unassigned:
        rows.append(
            [
                InlineKeyboardButton(
                    text=get_text("btn_claim_lead", lang),
                    callback_data=f"lead_act:claim:{lead_id}",
                )
            ]
        )
    elif is_assigned_to_me:
        if stage not in ("won", "lost"):
            rows.append(
                [
                    InlineKeyboardButton(
                        text=get_text("btn_change_stage", lang),
                        callback_data=f"lead_act:stages:{lead_id}",
                    ),
                    InlineKeyboardButton(
                        text=get_text("btn_add_task", lang),
                        callback_data=f"lead_act:add_task:{lead_id}",
                    ),
                ]
            )
            rows.append(
                [
                    InlineKeyboardButton(
                        text=get_text("btn_add_note", lang),
                        callback_data=f"lead_act:add_note:{lead_id}",
                    ),
                    InlineKeyboardButton(
                        text=get_text("btn_lead_history", lang),
                        callback_data=f"lead_act:history:{lead_id}",
                    ),
                ]
            )
        else:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=get_text("btn_lead_history", lang),
                        callback_data=f"lead_act:history:{lead_id}",
                    )
                ]
            )

    rows.append(
        [
            InlineKeyboardButton(
                text=get_text("btn_back_to_cabinet", lang),
                callback_data="broker_cab:home",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_lead_stage_choice_keyboard(lead_id: int, lang: str = "uz") -> InlineKeyboardMarkup:
    """Build keyboard for choosing next stage."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"📞 {get_text('stage_contacted', lang)}",
                    callback_data=f"lead_setstage:{lead_id}:contacted",
                ),
                InlineKeyboardButton(
                    text=f"🎯 {get_text('stage_qualified', lang)}",
                    callback_data=f"lead_setstage:{lead_id}:qualified",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"📅 {get_text('stage_viewing_scheduled', lang)}",
                    callback_data=f"lead_setstage:{lead_id}:viewing_scheduled",
                ),
                InlineKeyboardButton(
                    text=f"🤝 {get_text('stage_negotiation', lang)}",
                    callback_data=f"lead_setstage:{lead_id}:negotiation",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"🎉 {get_text('stage_won', lang)}",
                    callback_data=f"lead_setstage:{lead_id}:won",
                ),
                InlineKeyboardButton(
                    text=f"❌ {get_text('stage_lost', lang)}",
                    callback_data=f"lead_setstage:{lead_id}:lost",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Orqaga",
                    callback_data=f"lead_view:{lead_id}",
                )
            ],
        ]
    )


def get_lead_lost_reason_keyboard(lead_id: int, lang: str = "uz") -> InlineKeyboardMarkup:
    """Build keyboard for selecting lost reason."""
    reasons = [
        "price",
        "not_interested",
        "competitor",
        "property_unavailable",
        "no_response",
        "other",
    ]
    buttons = [
        [
            InlineKeyboardButton(
                text=get_text(f"lost_reason_{r}", lang),
                callback_data=f"lead_lost:{lead_id}:{r}",
            )
        ]
        for r in reasons
    ]
    buttons.append(
        [
            InlineKeyboardButton(
                text="⬅️ Bekor qilish",
                callback_data=f"lead_view:{lead_id}",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_followup_type_keyboard(lead_id: int, lang: str = "uz") -> InlineKeyboardMarkup:
    """Build keyboard for choosing task type."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("task_call", lang),
                    callback_data=f"fu_type:{lead_id}:call",
                ),
                InlineKeyboardButton(
                    text=get_text("task_message", lang),
                    callback_data=f"fu_type:{lead_id}:message",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=get_text("task_meeting", lang),
                    callback_data=f"fu_type:{lead_id}:meeting",
                ),
                InlineKeyboardButton(
                    text=get_text("task_other", lang),
                    callback_data=f"fu_type:{lead_id}:other",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Bekor qilish",
                    callback_data=f"lead_view:{lead_id}",
                )
            ],
        ]
    )


def get_followup_time_shortcuts_keyboard(
    lead_id: int,
    task_type: str,
    lang: str = "uz",  # noqa: ARG001
) -> InlineKeyboardMarkup:
    """Build shortcut keyboard for scheduling task time."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⏱ 1 soatdan keyin",
                    callback_data=f"fu_time:{lead_id}:{task_type}:1h",
                ),
                InlineKeyboardButton(
                    text="⏱ 3 soatdan keyin",
                    callback_data=f"fu_time:{lead_id}:{task_type}:3h",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🌅 Ertaga 10:00",
                    callback_data=f"fu_time:{lead_id}:{task_type}:tomorrow_10",
                ),
                InlineKeyboardButton(
                    text="🌆 Ertaga 15:00",
                    callback_data=f"fu_time:{lead_id}:{task_type}:tomorrow_15",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📅 2 kundan keyin",
                    callback_data=f"fu_time:{lead_id}:{task_type}:2d",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Bekor qilish",
                    callback_data=f"lead_view:{lead_id}",
                )
            ],
        ]
    )


def get_followup_actions_keyboard(
    followup_id: int, lead_id: int, lang: str = "uz"
) -> InlineKeyboardMarkup:
    """Build action buttons for a follow-up task card."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Bajarildi",
                    callback_data=f"fu_act:done:{followup_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Bekor qilish",
                    callback_data=f"fu_act:cancel:{followup_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📌 Leadga o‘tish",
                    callback_data=f"lead_view:{lead_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("btn_back_to_cabinet", lang),
                    callback_data="broker_cab:home",
                )
            ],
        ]
    )


def get_lead_history_back_keyboard(
    lead_id: int,
    lang: str = "uz",  # noqa: ARG001
) -> InlineKeyboardMarkup:
    """Build back button for lead history/notes view."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Leadga qaytish",
                    callback_data=f"lead_view:{lead_id}",
                )
            ]
        ]
    )


def get_ai_broker_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Build conversational reply keyboard while chatting with AI Broker."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=get_text("btn_ai_exit", lang)),
            ]
        ],
        resize_keyboard=True,
        persistent=True,
    )


# --- Phase 8: Property Valuation Keyboards ---


def get_valuation_listing_type_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Build inline keyboard for valuation listing type (sale vs rent)."""
    labels = {
        "uz": {"sale": "💰 Sotish", "rent": "🔑 Ijara"},
        "ru": {"sale": "💰 Продажа", "rent": "🔑 Аренда"},
        "en": {"sale": "💰 Sale", "rent": "🔑 Rent"},
    }
    loc = labels.get(lang, labels["uz"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=loc["sale"], callback_data="val_lt:sale"),
                InlineKeyboardButton(text=loc["rent"], callback_data="val_lt:rent"),
            ]
        ]
    )


def get_valuation_property_type_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Build inline keyboard for valuation property type."""
    labels = {
        "uz": {
            "apartment": "🏢 Kvartira",
            "house": "🏡 Hovli / Uy",
            "commercial": "🏬 Tijorat",
            "land": "🌾 Yer uchastkasi",
        },
        "ru": {
            "apartment": "🏢 Квартира",
            "house": "🏡 Дом / Участок",
            "commercial": "🏬 Коммерческая",
            "land": "🌾 Земельный участок",
        },
        "en": {
            "apartment": "🏢 Apartment",
            "house": "🏡 House / Villa",
            "commercial": "🏬 Commercial",
            "land": "🌾 Land plot",
        },
    }
    loc = labels.get(lang, labels["uz"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=loc["apartment"], callback_data="val_pt:apartment"),
                InlineKeyboardButton(text=loc["house"], callback_data="val_pt:house"),
            ],
            [
                InlineKeyboardButton(text=loc["commercial"], callback_data="val_pt:commercial"),
                InlineKeyboardButton(text=loc["land"], callback_data="val_pt:land"),
            ],
        ]
    )


def get_valuation_districts_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:  # noqa: ARG001
    """Build inline keyboard of popular Tashkent districts."""
    districts = [
        ("Chilonzor", "Yunusobod"),
        ("Mirzo Ulug‘bek", "Mirobod"),
        ("Yakkasaroy", "Shayxontohur"),
        ("Olmazor", "Uchtepa"),
        ("Yashnobod", "Sergeli"),
    ]
    rows = []
    for d1, d2 in districts:
        rows.append(
            [
                InlineKeyboardButton(text=d1, callback_data=f"val_dst:{d1}"),
                InlineKeyboardButton(text=d2, callback_data=f"val_dst:{d2}"),
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_valuation_rooms_keyboard() -> InlineKeyboardMarkup:
    """Build inline keyboard for room counts."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1", callback_data="val_rooms:1"),
                InlineKeyboardButton(text="2", callback_data="val_rooms:2"),
                InlineKeyboardButton(text="3", callback_data="val_rooms:3"),
                InlineKeyboardButton(text="4", callback_data="val_rooms:4"),
                InlineKeyboardButton(text="5+", callback_data="val_rooms:5"),
            ]
        ]
    )


def get_valuation_condition_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Build inline keyboard for condition selection."""
    labels = {
        "uz": {
            "new": "✨ Yangi / Yevroremont",
            "renovated": "🛠 Ta'mirlangan (yaxshi)",
            "needs_renovation": "🏚 Ta'mirga muhtoj",
            "shell": "🧱 Qora suvoq (korobka)",
        },
        "ru": {
            "new": "✨ Новый / Евроремонт",
            "renovated": "🛠 С хорошим ремонтом",
            "needs_renovation": "🏚 Требует ремонта",
            "shell": "🧱 Черновая отделка",
        },
        "en": {
            "new": "✨ Newly renovated",
            "renovated": "🛠 Renovated (good)",
            "needs_renovation": "🏚 Needs renovation",
            "shell": "🧱 Shell & core",
        },
    }
    loc = labels.get(lang, labels["uz"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=loc["new"], callback_data="val_cond:new"),
            ],
            [
                InlineKeyboardButton(text=loc["renovated"], callback_data="val_cond:renovated"),
            ],
            [
                InlineKeyboardButton(
                    text=loc["needs_renovation"], callback_data="val_cond:needs_renovation"
                ),
            ],
            [
                InlineKeyboardButton(text=loc["shell"], callback_data="val_cond:shell"),
            ],
        ]
    )


def get_valuation_floor_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Build inline keyboard allowing user to skip floor input."""
    labels = {
        "uz": "⏭ O‘tkazib yuborish",
        "ru": "⏭ Пропустить",
        "en": "⏭ Skip",
    }
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=labels.get(lang, labels["uz"]),
                    callback_data="val_floor:skip",
                )
            ]
        ]
    )


def get_valuation_currency_keyboard() -> InlineKeyboardMarkup:
    """Build inline keyboard for currency selection."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇸 USD ($)", callback_data="val_curr:USD"),
                InlineKeyboardButton(text="🇺🇿 UZS (so‘m)", callback_data="val_curr:UZS"),
            ]
        ]
    )


def get_valuation_actions_keyboard(
    has_comps: bool,
    listing_type: str,
    lang: str = "uz",
) -> InlineKeyboardMarkup:
    """Build action buttons below valuation card."""
    labels = {
        "uz": {
            "comps": "🏘 Taqqoslangan e'lonlar",
            "search": "🔎 O‘xshash e'lonlarni qidirish",
            "submit_sale": "💰 Uyimni sotishga qo‘yish",
            "submit_rent": "🏡 Uyimni ijaraga berish",
            "broker": "👨‍💼 Broker bilan bog‘lanish",
            "menu": "⬅️ Asosiy menyu",
        },
        "ru": {
            "comps": "🏘 Сравненные объявления",
            "search": "🔎 Найти похожие объявления",
            "submit_sale": "💰 Выставить на продажу",
            "submit_rent": "🏡 Сдать в аренду",
            "broker": "👨‍💼 Связаться с брокером",
            "menu": "⬅️ Главное меню",
        },
        "en": {
            "comps": "🏘 Comparable listings",
            "search": "🔎 Search similar listings",
            "submit_sale": "💰 List for sale",
            "submit_rent": "🏡 List for rent",
            "broker": "👨‍💼 Contact broker",
            "menu": "⬅️ Main menu",
        },
    }
    loc = labels.get(lang, labels["uz"])
    rows = []
    if has_comps:
        rows.append([InlineKeyboardButton(text=loc["comps"], callback_data="val_act:comps")])

    rows.append([InlineKeyboardButton(text=loc["search"], callback_data="val_act:search")])

    submit_text = loc["submit_sale"] if listing_type == "sale" else loc["submit_rent"]
    rows.append([InlineKeyboardButton(text=submit_text, callback_data="val_act:submit")])
    rows.append([InlineKeyboardButton(text=loc["broker"], callback_data="val_act:broker")])
    rows.append([InlineKeyboardButton(text=loc["menu"], callback_data="val_act:menu")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_valuation_payment_keyboard(
    order_id: str,
    click_url: str | None = None,
    payme_url: str | None = None,
    lang: str = "uz",
) -> InlineKeyboardMarkup:
    """Build payment options inline keyboard for monetized property valuation."""
    click_label = (
        "💳 Click orqali to‘lash"
        if lang == "uz"
        else ("💳 Оплатить через Click" if lang == "ru" else "💳 Pay via Click")
    )
    payme_label = (
        "💳 Payme orqali to‘lash"
        if lang == "uz"
        else ("💳 Оплатить через Payme" if lang == "ru" else "💳 Pay via Payme")
    )
    check_label = (
        "🔄 To‘lovni tekshirish"
        if lang == "uz"
        else ("🔄 Проверить оплату" if lang == "ru" else "🔄 Check payment")
    )
    cancel_label = (
        "❌ Bekor qilish"
        if lang == "uz"
        else ("❌ Отменить" if lang == "ru" else "❌ Cancel")
    )

    rows: list[list[InlineKeyboardButton]] = []

    # Click button
    if click_url:
        rows.append([InlineKeyboardButton(text=click_label, url=click_url)])
    else:
        rows.append(
            [InlineKeyboardButton(text=click_label, callback_data=f"val_pay_click:{order_id}")]
        )

    # Payme button
    if payme_url:
        rows.append([InlineKeyboardButton(text=payme_label, url=payme_url)])
    else:
        rows.append(
            [InlineKeyboardButton(text=payme_label, callback_data=f"val_pay_payme:{order_id}")]
        )

    # Check status button
    rows.append(
        [InlineKeyboardButton(text=check_label, callback_data=f"val_check_pay:{order_id}")]
    )

    # Cancel button
    rows.append(
        [InlineKeyboardButton(text=cancel_label, callback_data=f"val_cancel_pay:{order_id}")]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_valuation_package_keyboard(
    standard_price: int,
    premium_price: int,
    lang: str = "uz",
) -> InlineKeyboardMarkup:
    """Build keyboard for choosing valuation service package."""
    std_fmt = f"{standard_price:,}".replace(",", " ")
    prem_fmt = f"{premium_price:,}".replace(",", " ")

    if lang == "ru":
        std_text = f"⚡ Стандарт — {std_fmt} сум"
        prem_text = f"🚀 Эксперт — {prem_fmt} сум"
        cancel_text = "❌ Отмена"
    else:
        std_text = f"⚡ Standart — {std_fmt} so‘m"
        prem_text = f"🚀 Ekspert — {prem_fmt} so‘m"
        cancel_text = "❌ Bekor qilish"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=std_text, callback_data="val_pkg:standard")],
            [InlineKeyboardButton(text=prem_text, callback_data="val_pkg:premium")],
            [InlineKeyboardButton(text=cancel_text, callback_data="val_cancel")],
        ]
    )


def get_valuation_receipt_keyboard(order_id: str, lang: str = "uz") -> InlineKeyboardMarkup:
    """Build keyboard shown when waiting for receipt upload."""
    if lang == "ru":
        cancel_text = "❌ Отмена"
    elif lang == "uz":
        cancel_text = "❌ Bekor qilish"
    else:
        cancel_text = "❌ Cancel"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=cancel_text, callback_data=f"val_cancel_pay:{order_id}")]
        ]
    )


