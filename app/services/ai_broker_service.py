"""AI Broker business service integrating LLM intent extraction with UyAI core services."""

import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gemini_provider import GeminiLLMProvider
from app.ai.interfaces import LLMProvider
from app.ai.schemas import AIBrokerIntent, PropertySafeContext
from app.config import Settings, get_settings
from app.core.exceptions import (
    AIBrokerRateLimitError,
    AIBrokerTimeoutError,
    AIBrokerValidationError,
)
from app.logging import get_logger
from app.models.property import Property
from app.models.user import User
from app.repositories.property_repository import PropertyRepository
from app.repositories.user_repository import UserRepository
from app.schemas.property_search import PropertySearchFilters
from app.services.property_search_service import PropertySearchService

logger = get_logger(__name__)


def _get_text(key: str, lang: str = "uz") -> str:
    """Lazy localized string lookup to prevent circular import at module load."""
    from app.bot.locales import get_text

    return get_text(key, lang)


class AIBrokerResult:
    """Standardized response payload from AI Broker Service to presentation layer."""

    def __init__(
        self,
        action: str,
        text: str,
        properties: list[Property] | None = None,
        property_id: int | None = None,
        filters: PropertySearchFilters | None = None,
        needs_clarification: bool = False,
    ) -> None:
        # Action category: search_results, property_answer, route_viewing,
        # route_broker, favorites_help, general, clarification
        self.action = action
        self.text = text
        self.properties = properties or []
        self.property_id = property_id
        self.filters = filters
        self.needs_clarification = needs_clarification


class AIBrokerService:
    """Service coordinating NL query processing, grounding, and UyAI services."""

    def __init__(
        self,
        provider: LLMProvider | None = None,
        property_search_service: PropertySearchService | None = None,
        property_repo: PropertyRepository | None = None,
        user_repo: UserRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.provider = provider or GeminiLLMProvider(self.settings)
        self.search_service = property_search_service or PropertySearchService(
            property_repo=property_repo
        )
        self.property_repo = property_repo or PropertyRepository()
        self.user_repo = user_repo or UserRepository()

        # In-memory per-user rate limiting / cooldown tracker
        self._user_last_request: dict[int, float] = {}
        self._cooldown_seconds = 1.0

    def check_rate_limit(self, user_id: int) -> None:
        """Enforce cooldown between AI Broker requests to prevent rapid-fire abuse."""
        now = time.monotonic()
        last_time = self._user_last_request.get(user_id, 0.0)
        if now - last_time < self._cooldown_seconds:
            raise AIBrokerRateLimitError("Iltimos, xabarlar oralig‘ida biroz kuting.")
        self._user_last_request[user_id] = now

    def build_safe_property_context(self, prop: Property) -> str:
        """Construct sanitized factual representation of property.

        Strictly guarantees: NO owner PII, NO owner phone, NO customer phone,
        NO Telegram IDs, NO broker notes, NO lead events, and NO private cadastral data.
        """
        safe_ctx = PropertySafeContext(
            id=prop.id,
            listing_type=prop.listing_type,
            property_type=prop.property_type,
            title=prop.title,
            description=prop.description,
            price=prop.price,
            currency=prop.currency,
            rooms=prop.rooms,
            total_area=prop.total_area,
            floor=prop.floor,
            total_floors=prop.total_floors,
            condition=prop.condition,
            has_furniture=bool(prop.has_furniture),
            region=prop.region,
            district=prop.district,
            address=prop.address,
        )

        lines = [
            f"ID: #{safe_ctx.id}",
            f"Listing type: {safe_ctx.listing_type}",
            f"Property type: {safe_ctx.property_type}",
            f"Title: {safe_ctx.title}",
            f"Description: {safe_ctx.description or 'None'}",
            f"Price: {safe_ctx.price} {safe_ctx.currency}",
            f"Rooms: {safe_ctx.rooms}",
            f"Total area: {safe_ctx.total_area} sq.m.",
            (
                f"Floor: {safe_ctx.floor or 'Not specified'} / "
                f"{safe_ctx.total_floors or 'Not specified'}"
            ),
            f"Condition: {safe_ctx.condition or 'Standard'}",
            f"Furniture: {'Yes' if safe_ctx.has_furniture else 'No'}",
            f"Region: {safe_ctx.region}",
            f"District: {safe_ctx.district}",
        ]
        return "\n".join(lines)

    async def process_message(
        self,
        session: AsyncSession,
        user: User,
        message_text: str,
        history: list[dict[str, str]] | None = None,
    ) -> AIBrokerResult:
        """Orchestrate end-to-end processing of a user message inside AI Broker."""
        lang = user.language or "uz"
        self.check_rate_limit(user.id)

        # 1. Intent extraction
        try:
            intent = await self.provider.parse_intent(
                user_message=message_text,
                history=history,
                language=lang,
            )
        except (AIBrokerTimeoutError, AIBrokerValidationError) as err:
            logger.warning("AI Broker intent extraction issue", error=str(err))
            return AIBrokerResult(
                action="clarification",
                text=_get_text("ai_fallback_error", lang),
                needs_clarification=True,
            )

        # 2. Intent routing & database interaction
        if intent.intent == "search_property":
            return await self._handle_search_intent(session, intent, lang)

        if intent.intent == "property_question":
            return await self._handle_property_question(session, intent, message_text, lang)

        if intent.intent == "request_viewing":
            return await self._handle_request_viewing(session, intent, lang)

        if intent.intent == "request_broker":
            return await self._handle_request_broker(session, intent, lang)

        if intent.intent == "favorites_help":
            text = (
                "❤️ Saqlangan uylaringizni ko‘rish uchun asosiy menyudagi "
                "«❤️ Saqlangan uylar» tugmasini bosing."
                if lang == "uz"
                else "❤️ Чтобы посмотреть сохраненные объекты, нажмите кнопку "
                "«❤️ Избранное» в главном меню."
            )
            return AIBrokerResult(action="favorites_help", text=text)

        if intent.intent == "greeting":
            text = (
                "Assalomu alaykum! Men UyAI tizimining sun'iy intellekt brokeriman. "
                "Sizga Toshkent shahridan mos uy topishda, e'lonlar haqida savollarga "
                "javob berishda yoki ko‘rishga yozilishda yordam bera olaman. "
                "Menga qanday uy qidirayotganingizni yozing!"
                if lang == "uz"
                else "Здравствуйте! Я AI Брокер платформы UyAI. "
                "Я помогу вам найти подходящую недвижимость в Ташкенте, отвечу на вопросы "
                "по объектам или помогу записаться на просмотр. "
                "Опишите, какую квартиру или дом вы ищете!"
            )
            return AIBrokerResult(action="general", text=text)

        if intent.intent == "general_real_estate_help":
            disclaimer = _get_text("ai_general_disclaimer", lang)
            response_text = await self.provider.generate_grounded_response(
                query=message_text,
                context="General real estate inquiry in Tashkent.",
                language=lang,
            )
            return AIBrokerResult(action="general", text=f"{response_text}{disclaimer}")

        # Default fallback / unknown / clarification
        clarification_msg = intent.clarification_question or (
            "Iltimos, talabingizni aniqlashtiring "
            "(masalan: qaysi tuman, xonalar soni va narx oralig‘i)."
            if lang == "uz"
            else "Пожалуйста, уточните ваш запрос "
            "(например: район, количество комнат и желаемую цену)."
        )
        return AIBrokerResult(
            action="clarification",
            text=clarification_msg,
            needs_clarification=True,
        )

    async def _handle_search_intent(
        self,
        session: AsyncSession,
        intent: AIBrokerIntent,
        lang: str,
    ) -> AIBrokerResult:
        """Map structured intent to PropertySearchFilters and execute database search."""
        listing_type = intent.listing_type or "sale"
        currency = intent.currency
        if (intent.min_price is not None or intent.max_price is not None) and not currency:
            currency = "USD"

        search_filters = PropertySearchFilters(
            listing_type=listing_type,
            property_type=intent.property_type,
            region=intent.region,
            district=intent.district,
            rooms=intent.rooms,
            min_price=intent.min_price,
            max_price=intent.max_price,
            currency=currency,
            min_area=intent.min_area,
        )

        # Database is the sole source of truth; only approved properties can be returned
        results, _total_count, _total_pages = await self.search_service.search(
            session=session,
            filters=search_filters,
            page=1,
            page_size=self.settings.ai_max_search_results,
        )

        if not results:
            return AIBrokerResult(
                action="search_results",
                text=_get_text("ai_search_not_found", lang),
                properties=[],
                filters=search_filters,
            )

        intro = _get_text("ai_search_found", lang).format(count=len(results))
        return AIBrokerResult(
            action="search_results",
            text=intro,
            properties=results,
            filters=search_filters,
        )

    async def _handle_property_question(
        self,
        session: AsyncSession,
        intent: AIBrokerIntent,
        query: str,
        lang: str,
    ) -> AIBrokerResult:
        """Answer property-specific question using verified database context."""
        prop_id = intent.property_id
        if not prop_id:
            msg = (
                "Qaysi ko‘chmas mulk haqida ma'lumot olmoqchisiz? "
                "Iltimos, e'lon raqamini kiriting (masalan: #1)."
                if lang == "uz"
                else "О каком объекте вы хотите узнать? Укажите номер объявления (например: #1)."
            )
            return AIBrokerResult(action="clarification", text=msg, needs_clarification=True)

        prop = await self.property_repo.get_by_id(session, prop_id)
        # Protect unapproved/archived properties
        if not prop or prop.status != "approved":
            return AIBrokerResult(
                action="property_answer",
                text=_get_text("ai_property_not_found", lang),
                property_id=prop_id,
            )

        # Build safe context (guarantees NO owner/customer PII)
        verified_context = self.build_safe_property_context(prop)
        answer = await self.provider.generate_grounded_response(
            query=query,
            context=verified_context,
            language=lang,
        )
        return AIBrokerResult(
            action="property_answer",
            text=answer,
            property_id=prop_id,
            properties=[prop],
        )

    async def _handle_request_viewing(
        self,
        session: AsyncSession,
        intent: AIBrokerIntent,
        lang: str,
    ) -> AIBrokerResult:
        """Route viewing request into existing Phase 5 appointment flow."""
        prop_id = intent.property_id
        if not prop_id:
            msg = (
                "Qaysi uyni ko‘rishni xohlaysiz? "
                "Iltimos, e'lon raqamini ko‘rsating (masalan: #1 uyni ko‘rmoqchiman)."
                if lang == "uz"
                else "Какой объект вы хотите посмотреть? "
                "Укажите номер объявления (например: Хочу посмотреть #1)."
            )
            return AIBrokerResult(action="clarification", text=msg, needs_clarification=True)

        prop = await self.property_repo.get_by_id(session, prop_id)
        if not prop or prop.status != "approved":
            return AIBrokerResult(
                action="route_viewing",
                text=_get_text("ai_property_not_found", lang),
                property_id=prop_id,
            )

        msg = (
            f"📅 <b>#{prop.id} - {prop.title}</b> bo‘yicha ko‘rishga yozilishni tasdiqlaysizmi?"
            if lang == "uz"
            else f"📅 Хотите записаться на просмотр объекта <b>#{prop.id} - {prop.title}</b>?"
        )
        return AIBrokerResult(
            action="route_viewing",
            text=msg,
            property_id=prop.id,
            properties=[prop],
        )

    async def _handle_request_broker(
        self,
        session: AsyncSession,
        intent: AIBrokerIntent,
        lang: str,
    ) -> AIBrokerResult:
        """Route broker contact request into existing Phase 5 broker contact flow."""
        prop_id = intent.property_id
        prop = None
        if prop_id:
            prop = await self.property_repo.get_by_id(session, prop_id)

        if prop and prop.status == "approved":
            msg = (
                f"👨‍💼 <b>#{prop.id} - {prop.title}</b> "
                "bo‘yicha professional broker bilan bog‘lanishni tasdiqlaysizmi?"
                if lang == "uz"
                else (
                    f"👨‍💼 Хотите связаться с брокером по объекту "
                    f"<b>#{prop.id} - {prop.title}</b>?"
                )
            )
            return AIBrokerResult(
                action="route_broker",
                text=msg,
                property_id=prop.id,
                properties=[prop],
            )

        # General broker assistance request without specific property
        msg = (
            "👨‍💼 Ko‘chmas mulk bo‘yicha mutaxassis bilan bog‘lanish uchun, "
            "sizni qiziqtirgan e'lon sahifasida «👨‍💼 Broker bilan bog‘lanish» "
            "tugmasini bosing yoki e'lon raqamini yozing."
            if lang == "uz"
            else "👨‍💼 Чтобы связаться со специалистом по недвижимости, "
            "откройте карточку интересующего объекта и нажмите "
            "«👨‍💼 Связаться с брокером» или укажите номер объявления."
        )
        return AIBrokerResult(action="route_broker", text=msg)
