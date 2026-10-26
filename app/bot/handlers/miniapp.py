"""Telegram bot handler for launching the Telegram Mini App and map."""

from aiogram import F, Router
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.locales import LOCALES
from app.config import get_settings
from app.services.user_service import UserService

miniapp_router = Router(name="miniapp")

# Collect localized button labels for map button
MAP_BUTTON_TEXTS: set[str] = {
    locale_dict.get("btn_map", "📍 Xaritadan uy qidirish")
    for locale_dict in LOCALES.values()
    if "btn_map" in locale_dict
}
MAP_BUTTON_TEXTS.update({"📍 Xaritadan uy qidirish", "📍 Поиск по карте"})


@miniapp_router.message(F.text.in_(MAP_BUTTON_TEXTS) | F.text.in_({"/map", "/app", "/miniapp"}))
async def handle_miniapp_button(
    message: Message,
    session: AsyncSession,
) -> None:
    """Respond to map/miniapp button with WebAppInfo inline button or graceful fallback."""
    user_service = UserService()
    user = (
        await user_service.get_by_telegram_id(session, message.from_user.id)
        if message.from_user
        else None
    )
    lang = user.language if user else "uz"
    settings = get_settings()

    if settings.miniapp_url:
        title = (
            "🗺 <b>UyAI Xaritasi va Mini App</b>\n\n"
            "Interaktiv xarita orqali barcha tasdiqlangan ko‘chmas mulklarni ko‘rishingiz, "
            "filtrlar yordamida qidirishingiz va saqlab qo‘yishingiz mumkin.\n\n"
            "Ilovani ochish uchun quyidagi tugmani bosing:"
        )
        btn_label = "🗺 Xaritani ochish"
        if lang == "ru":
            title = (
                "🗺 <b>Карта и Mini App UyAI</b>\n\n"
                "Вы можете просматривать все проверенные объекты на интерактивной карте, "
                "использовать фильтry и сохранять в избранное.\n\n"
                "Нажмите кнопку ниже, чтобы открыть приложение:"
            )
            btn_label = "🗺 Открыть карту"

        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=btn_label,
                        web_app=WebAppInfo(url=settings.miniapp_url),
                    )
                ]
            ]
        )
        await message.answer(title, reply_markup=markup)
    else:
        fallback_msg = (
            "📍 <b>Xarita va Mini App tizimi</b>\n\n"
            "Interaktiv xarita va Mini App tizimi hozirda sozlanmoqda. "
            "Tez orada to‘liq ishga tushiriladi!\n\n"
            "Hozirda uylarni ro‘yxat bo‘yicha qidirishingiz yoki AI broker orqali "
            "topishingiz mumkin."
        )
        if lang == "ru":
            fallback_msg = (
                "📍 <b>Карта и Mini App</b>\n\n"
                "Интерактивная карта и Mini App в настоящее время настраиваются. "
                "Скоро сервис станет доступен!\n\n"
                "Вы можете воспользоваться обычным поиском или AI брокером."
            )
        await message.answer(fallback_msg)
