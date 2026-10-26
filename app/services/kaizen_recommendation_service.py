"""Kaizen Recommendation Engine combining deterministic rules and Gemini AI advisor."""

import json
from datetime import UTC, datetime
from typing import Any

from google.genai import types
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gemini_provider import GeminiLLMProvider
from app.config import get_settings
from app.logging import get_logger
from app.models.kaizen import KAIZEN_SEVERITIES, KaizenRecommendation
from app.services.admin_auth_service import AdminAuthService
from app.services.kaizen_analytics_service import KaizenAnalyticsService, KaizenDateRange

logger = get_logger(__name__)

VALID_METRIC_KEYS: tuple[str, ...] = (
    "overall_win_rate",
    "lead_to_contacted_rate",
    "median_response_time",
    "viewing_completion_rate",
    "viewing_cancellation_rate",
    "crm_failed_events",
    "overdue_followups",
    "moderation_backlog",
)


class AIKaizenRecommendationItem(BaseModel):
    metric_key: str = Field(
        ..., description="Canonical metric key, e.g. overall_win_rate, median_response_time"
    )
    category: str = Field(
        ..., description="Category, e.g. lead_conversion, response_time, operational, crm_health"
    )
    title: str = Field(..., description="Concise title of the recommendation in Uzbek")
    description: str = Field(
        ..., description="Detailed description of what the data shows in Uzbek"
    )
    recommendation_text: str = Field(
        ..., description="Specific, actionable improvement step in Uzbek"
    )
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    severity: str = Field(default="info", description="Severity: info, warning, critical")


class AIKaizenRecommendationList(BaseModel):
    recommendations: list[AIKaizenRecommendationItem] = Field(default_factory=list)


KAIZEN_ADVISOR_SYSTEM_PROMPT = (
    "Siz UyAI ko'chmas mulk platformasining boshqaruv tahlilchisi (Kaizen / PDCA Advisor)siz.\n"
    "Sizga tizimning operatsion ma'lumotlaridan DETERMINISTIK KPI beriladi.\n\n"
    "QAT'IY QOIDALAR (ANTI-HALLUCINATION & SAFETY):\n"
    "1. Faqat sizga taqdim etilgan haqiqiy ma'lumotlarga va raqamlarga tayaning.\n"
    "2. Hech qanday raqam yoki hodisani o'zingizdan TO'QIB CHIQARMANG (NO FABRICATION).\n"
    "3. Taqdim etilgan qiymatlarni o'zgartirmang.\n"
    "4. Foydalanuvchilarning shaxsiy hayoti, jinsi, yoshi haqida xulosa qilmang.\n"
    "5. Har bir tavsiya nima uchun kerakligini (EVIDENCE) va maqsadni aniq ifodalang.\n"
    "6. Agar ma'lumot yetarli bo'lmasa, 'insufficient data' deb qabul qiling.\n"
    "7. Barcha matnlar o'zbek tilida, professional boshqaruv uslubida bo'lsin.\n"
)


class KaizenRecommendationService:
    """Generates explainable Kaizen recommendations using deterministic rules and Gemini."""

    @classmethod
    def generate_deterministic_rules(cls, overview: dict[str, Any]) -> list[dict[str, Any]]:
        """Run deterministic heuristic evaluation on calculated KPIs."""
        recs: list[dict[str, Any]] = []

        # 1. Lead Funnel: Overall Win Rate check
        win_rate = overview["lead_funnel"]["conversion_rates"]["overall_win_rate"]
        closed_leads = overview["lead_funnel"]["won_leads"] + overview["lead_funnel"]["lost_leads"]
        if win_rate is not None and closed_leads >= 3 and win_rate < 15.0:
            won_cnt = overview["lead_funnel"]["won_leads"]
            recs.append(
                {
                    "metric_key": "overall_win_rate",
                    "category": "lead_conversion",
                    "title": f"Lidlar konversiyasi pasaygan (Win rate: {win_rate}%)",
                    "description": (
                        f"Yopilgan {closed_leads} ta liddan faqat {won_cnt} tasi yutildi. "
                        f"Standart ko'rsatkich 20% dan yuqori bo'lishi lozim."
                    ),
                    "evidence_json": json.dumps(
                        {
                            "win_rate": win_rate,
                            "won_leads": won_cnt,
                            "closed_leads": closed_leads,
                        }
                    ),
                    "recommendation_text": (
                        "Lidlar malakasini (qualification) tezlashtirish va muzokara "
                        "bosqichidagi mijozlarga tajribali sales brokerlarni jalb qilish lozim."
                    ),
                    "confidence": 0.95,
                    "severity": "warning",
                }
            )

        # 2. Response Time: Slow first contact
        resp_med = overview["response_time"]["median_minutes"]
        sample_size = overview["response_time"]["sample_size"]
        if resp_med is not None and sample_size >= 3 and resp_med > 30.0:
            recs.append(
                {
                    "metric_key": "median_response_time",
                    "category": "response_time",
                    "title": f"Mijoz bilan birinchi aloqa vaqti yuqori ({resp_med} daqiqa)",
                    "description": (
                        f"{sample_size} ta lid bo'yicha javob berishning median vaqti "
                        f"{resp_med} daqiqani tashkil etmoqda. Standart — 15 daqiqadan kam."
                    ),
                    "evidence_json": json.dumps(
                        {"median_minutes": resp_med, "sample_size": sample_size}
                    ),
                    "recommendation_text": (
                        "Yangi kelgan lidlar haqida brokerlarga darhol bildirishnoma yetkazish "
                        "va navbatchi broker tizimini joriy etish tavsiya etiladi."
                    ),
                    "confidence": 0.98,
                    "severity": "critical",
                }
            )

        # 3. Overdue Followups: Operational debt
        overdue_count = overview["brokers"]["total_overdue_followups"]
        if overdue_count > 0:
            recs.append(
                {
                    "metric_key": "overdue_followups",
                    "category": "operational",
                    "title": f"Muddati o'tgan follow-up vazifalari mavjud ({overdue_count} ta)",
                    "description": (
                        f"Brokerlar tomonidan rejalashtirilgan {overdue_count} ta "
                        f"aloqa vazifasi o'z vaqtida bajarilmagan."
                    ),
                    "evidence_json": json.dumps({"overdue_followups": overdue_count}),
                    "recommendation_text": (
                        "Bosh broker tomonidan kechikkan vazifalar auditini o'tkazish "
                        "va faol bo'lmagan lidlarni qayta taqsimlash zarur."
                    ),
                    "confidence": 1.0,
                    "severity": "warning",
                }
            )

        # 4. Viewings: Cancellation rate check
        viewing_cancellation = overview["viewings"]["cancellation_rate"]
        total_viewings = overview["viewings"]["total_viewings"]
        if viewing_cancellation is not None and total_viewings >= 3 and viewing_cancellation > 20.0:
            cancelled_cnt = overview["viewings"]["cancelled"]
            recs.append(
                {
                    "metric_key": "viewing_cancellation_rate",
                    "category": "viewings",
                    "title": (
                        f"Ko'rishlarning bekor qilinish darajasi yuqori ({viewing_cancellation}%)"
                    ),
                    "description": (
                        f"Jami {total_viewings} ta ko'rishdan {cancelled_cnt} tasi bekor qilingan."
                    ),
                    "evidence_json": json.dumps(
                        {
                            "cancellation_rate": viewing_cancellation,
                            "cancelled": cancelled_cnt,
                            "total_viewings": total_viewings,
                        }
                    ),
                    "recommendation_text": (
                        "Ko'rish uchrashuvidan 2 soat oldin mijozga avtomatik eslatma "
                        "va tasdiqlash so'rovi yuborishni yo'lga qo'yish kerak."
                    ),
                    "confidence": 0.9,
                    "severity": "warning",
                }
            )

        # 5. CRM Health: Outbox failures
        crm_failed = overview["crm_health"]["failed_events"]
        crm_perm = overview["crm_health"]["permanent_failed_events"]
        if crm_failed > 0:
            recs.append(
                {
                    "metric_key": "crm_failed_events",
                    "category": "crm_health",
                    "title": f"amoCRM outbox sinxronizatsiya xatoliklari mavjud ({crm_failed} ta)",
                    "description": (
                        f"Tizimda amoCRM'ga yetib bormagan {crm_failed} ta hodisa mavjud "
                        f"(shundan {crm_perm} tasi doimiy xatolik)."
                    ),
                    "evidence_json": json.dumps(
                        {"failed_events": crm_failed, "permanent_failed": crm_perm}
                    ),
                    "recommendation_text": (
                        "amoCRM Outbox bo'limidan xatolik sababini tekshirib, muvaffaqiyatsiz "
                        "hodisalarni qayta urinish (Retry) lozim."
                    ),
                    "confidence": 1.0,
                    "severity": "critical" if crm_perm > 0 else "warning",
                }
            )

        # 6. Property Inventory: Moderation backlog
        mod_backlog = overview["properties"]["moderation_backlog"]
        if mod_backlog > 0:
            recs.append(
                {
                    "metric_key": "moderation_backlog",
                    "category": "moderation",
                    "title": f"Moderatsiya kutilayotgan e'lonlar mavjud ({mod_backlog} ta)",
                    "description": (
                        f"Foydalanuvchilar tomonidan yuborilgan {mod_backlog} ta "
                        f"e'lon tekshiruv navbatida turibdi."
                    ),
                    "evidence_json": json.dumps({"moderation_backlog": mod_backlog}),
                    "recommendation_text": (
                        "E'lonlar va Moderatsiya bo'limiga kirib, yangi e'lonlarni tasdiqlash "
                        "orqali katalog faolligini oshiring."
                    ),
                    "confidence": 1.0,
                    "severity": "info",
                }
            )

        return recs

    @classmethod
    async def generate_gemini_insights(
        cls,
        overview: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Call Gemini LLM with sanitized, aggregated KPI context for recommendations."""
        settings = get_settings()
        if not settings.ai_broker_enabled or not settings.gemini_api_key:
            return []

        try:
            provider = GeminiLLMProvider(settings=settings)
            # Remove any staff/broker names or identifiers to guarantee zero customer PII
            brokers_obj = overview.get("brokers", {})
            sanitized_overview = {
                "date_from": overview.get("date_from"),
                "date_to": overview.get("date_to"),
                "lead_funnel": overview.get("lead_funnel"),
                "response_time": overview.get("response_time"),
                "viewings": overview.get("viewings"),
                "properties": overview.get("properties"),
                "brokers": {
                    "total_active_brokers": brokers_obj.get("total_active_brokers", 0),
                    "total_overdue_followups": brokers_obj.get("total_overdue_followups", 0),
                    # broker performance aggregated without names/usernames
                    "brokers_summary": [
                        {
                            "assigned_leads": b.get("assigned_leads", 0),
                            "active_leads": b.get("active_leads", 0),
                            "won_leads": b.get("won_leads", 0),
                            "win_rate": b.get("win_rate"),
                            "completed_viewings": b.get("completed_viewings", 0),
                            "overdue_followups": b.get("overdue_followups", 0),
                        }
                        for b in brokers_obj.get("brokers", [])
                    ],
                },
                "crm_health": overview.get("crm_health"),
            }
            sanitized_context = json.dumps(sanitized_overview, default=str)

            config = types.GenerateContentConfig(
                system_instruction=KAIZEN_ADVISOR_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=AIKaizenRecommendationList,
                temperature=0.1,
                max_output_tokens=2048,
            )

            prompt = (
                f"QUYIDAGI OPERATSION KPI MA'LUMOTLARINI TAHLIL QILING VA STRUKTURALASHGAN "
                f"KAIZEN TAVSIYALARI RO'YXATINI QAYTARING:\n\n{sanitized_context}"
            )

            response = await provider.client.aio.models.generate_content(
                model=provider.model_name,
                contents=prompt,
                config=config,
            )

            if not response.text:
                return []

            parsed = AIKaizenRecommendationList.model_validate_json(response.text)
            ai_recs = []
            for item in parsed.recommendations:
                # Strict validation against valid metric keys and severities
                if item.metric_key not in VALID_METRIC_KEYS:
                    continue
                severity = item.severity if item.severity in KAIZEN_SEVERITIES else "info"

                ai_recs.append(
                    {
                        "metric_key": item.metric_key,
                        "category": item.category,
                        "title": item.title,
                        "description": item.description,
                        "evidence_json": json.dumps(
                            {"source": "gemini_advisor", "metric_key": item.metric_key}
                        ),
                        "recommendation_text": item.recommendation_text,
                        "confidence": float(item.confidence),
                        "severity": severity,
                    }
                )
            return ai_recs

        except Exception as e:
            logger.warning("Gemini Kaizen advisor generation failed or skipped: %s", e)
            return []

    @classmethod
    async def generate_and_persist_recommendations(
        cls,
        session: AsyncSession,
        staff_user_id: int,
        date_range: KaizenDateRange | None = None,
        use_ai: bool = True,
        ip_address: str | None = None,
    ) -> list[KaizenRecommendation]:
        """Generate recommendations, deduplicate against active ones, and persist."""
        rng = date_range or KaizenDateRange(days=30)
        overview = await KaizenAnalyticsService.get_kpi_overview(session, rng)

        # 1. Deterministic recommendations (primary)
        candidate_recs = cls.generate_deterministic_rules(overview)

        # 2. Optional Gemini AI enhancement
        if use_ai:
            ai_recs = await cls.generate_gemini_insights(overview)
            # Add AI recommendations that don't duplicate existing deterministic items
            existing_titles = {r["title"].lower() for r in candidate_recs}
            existing_pairs = {(r["metric_key"], r["category"]) for r in candidate_recs}
            for ar in ai_recs:
                if (
                    ar["title"].lower() not in existing_titles
                    and (ar["metric_key"], ar["category"]) not in existing_pairs
                ):
                    candidate_recs.append(ar)

        # 3. Deduplicate against active 'new' recommendations already in DB
        existing_new_stmt = select(
            KaizenRecommendation.title,
            KaizenRecommendation.metric_key,
            KaizenRecommendation.category,
        ).where(KaizenRecommendation.status == "new")
        existing_rows = (await session.execute(existing_new_stmt)).all()
        already_saved_titles = {r[0].lower() for r in existing_rows}
        already_saved_pairs = {(r[1], r[2]) for r in existing_rows}

        seen_titles = set(already_saved_titles)
        seen_pairs = set(already_saved_pairs)

        saved_records: list[KaizenRecommendation] = []
        for cand in candidate_recs:
            cand_title_lower = cand["title"].lower()
            cand_pair = (cand["metric_key"], cand["category"])

            if cand_title_lower in seen_titles or cand_pair in seen_pairs:
                continue

            seen_titles.add(cand_title_lower)
            seen_pairs.add(cand_pair)

            rec = KaizenRecommendation(
                metric_key=cand["metric_key"],
                category=cand["category"],
                title=cand["title"],
                description=cand["description"],
                evidence_json=cand["evidence_json"],
                recommendation_text=cand["recommendation_text"],
                confidence=cand["confidence"],
                severity=cand["severity"],
                status="new",
            )
            session.add(rec)
            saved_records.append(rec)

        if saved_records:
            await session.flush()
            await AdminAuthService.record_audit_event(
                session,
                actor_user_id=staff_user_id,
                action="kaizen.recommendations_generate",
                entity_type="kaizen_recommendations",
                entity_id=saved_records[0].id if saved_records else None,
                metadata={"count": len(saved_records)},
                ip_address=ip_address,
            )
            await session.commit()
            for r in saved_records:
                await session.refresh(r)

        return saved_records

    @classmethod
    async def list_recommendations(
        cls,
        session: AsyncSession,
        status_filter: str | None = None,
        category: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[KaizenRecommendation], int]:
        """Fetch paginated Kaizen recommendations."""
        stmt = select(KaizenRecommendation)
        if status_filter:
            stmt = stmt.where(KaizenRecommendation.status == status_filter)
        if category:
            stmt = stmt.where(KaizenRecommendation.category == category)

        from sqlalchemy import func

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await session.execute(count_stmt)).scalar_one() or 0

        stmt = (
            stmt.order_by(KaizenRecommendation.generated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list((await session.execute(stmt)).scalars().all())
        return items, total

    @classmethod
    async def review_recommendation(
        cls,
        session: AsyncSession,
        recommendation_id: int,
        staff_user_id: int,
        action: str,  # 'accept' or 'dismiss'
        ip_address: str | None = None,
    ) -> KaizenRecommendation:
        """Mark recommendation as accepted or dismissed."""
        rec = await session.get(KaizenRecommendation, recommendation_id)
        if not rec:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=404, detail=f"Recommendation #{recommendation_id} not found."
            )

        new_status = "accepted" if action == "accept" else "dismissed"
        rec.status = new_status
        rec.reviewed_by_user_id = staff_user_id
        rec.reviewed_at = datetime.now(UTC)

        await AdminAuthService.record_audit_event(
            session,
            actor_user_id=staff_user_id,
            action=f"kaizen.recommendation_{action}",
            entity_type="kaizen_recommendation",
            entity_id=rec.id,
            metadata={"status": new_status},
            ip_address=ip_address,
        )

        await session.commit()
        await session.refresh(rec)
        return rec
