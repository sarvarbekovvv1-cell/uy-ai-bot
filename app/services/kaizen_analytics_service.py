"""Deterministic Kaizen / PDCA Analytics and KPI Calculation Engine.

All operational KPIs are computed deterministically via SQL aggregates and Python statistics.
AI/LLM is never used to fabricate or alter numerical figures.
"""

import statistics
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.crm_sync import CRMSyncEvent
from app.models.lead import ACTIVE_LEAD_STAGES, Lead, LeadFollowUp
from app.models.property import Property
from app.models.role import Role
from app.models.user import User
from app.models.viewing_request import ViewingRequest

BROKER_ROLE_NAMES = ("head_broker", "sales_broker", "rental_broker")


class KaizenDateRange:
    """Encapsulates validated, timezone-aware date range boundaries."""

    def __init__(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
        days: int = 30,
    ) -> None:
        now_utc = datetime.now(UTC)
        today_utc = now_utc.date()

        if date_to is None:
            self.date_to = today_utc
        else:
            self.date_to = date_to

        if date_from is None:
            self.date_from = self.date_to - timedelta(days=days)
        else:
            self.date_from = date_from

        if self.date_from > self.date_to:
            raise ValueError(
                f"date_from ({self.date_from}) cannot be after date_to ({self.date_to})"
            )

        self.start_dt = datetime.combine(self.date_from, time.min, tzinfo=UTC)
        self.end_dt = datetime.combine(self.date_to, time.max, tzinfo=UTC)


class KaizenAnalyticsService:
    """Service providing deterministic KPI computations and metrics snapshots."""

    @staticmethod
    def _safe_percentage(numerator: int | float, denominator: int | float) -> float | None:
        """Calculate percentage safely. Return None if denominator is zero."""
        if not denominator or denominator <= 0:
            return None
        return round((float(numerator) / float(denominator)) * 100.0, 2)

    @staticmethod
    def _to_utc(dt: datetime | None) -> datetime | None:
        """Ensure datetime is UTC timezone-aware for safe cross-database comparisons."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

    @classmethod
    async def get_kpi_overview(
        cls,
        session: AsyncSession,
        date_range: KaizenDateRange,
    ) -> dict[str, Any]:
        """Compute full deterministic operational KPI payload for the requested timeframe."""
        start_dt = date_range.start_dt
        end_dt = date_range.end_dt

        # ---------------------------------------------------------------------
        # 1. Lead Funnel KPIs (Cumulative & Account for Terminal Stages)
        # ---------------------------------------------------------------------
        now_utc = datetime.now(UTC)
        leads_stmt = (
            select(Lead)
            .options(
                selectinload(Lead.events),
                selectinload(Lead.notes),
                selectinload(Lead.followups),
            )
            .where(Lead.created_at >= start_dt, Lead.created_at <= end_dt)
        )
        leads = list((await session.execute(leads_stmt)).scalars().all())

        total_leads = len(leads)
        new_leads = sum(1 for lead_item in leads if lead_item.stage == "new")
        contacted_leads = sum(1 for lead_item in leads if lead_item.stage == "contacted")
        qualified_leads = sum(1 for lead_item in leads if lead_item.stage == "qualified")
        viewing_scheduled_leads = sum(
            1 for lead_item in leads if lead_item.stage == "viewing_scheduled"
        )
        negotiation_leads = sum(1 for lead_item in leads if lead_item.stage == "negotiation")
        won_leads = sum(1 for lead_item in leads if lead_item.stage == "won")
        lost_leads = sum(1 for lead_item in leads if lead_item.stage == "lost")
        active_leads = sum(1 for lead_item in leads if lead_item.stage in ACTIVE_LEAD_STAGES)

        # Cumulative checks: did the lead ever reach or pass each stage?
        def _reached_contacted(lead_obj: Lead) -> bool:
            if lead_obj.stage in (
                "contacted",
                "qualified",
                "viewing_scheduled",
                "negotiation",
                "won",
            ):
                return True
            if (
                lead_obj.contacted_at is not None
                or lead_obj.qualified_at is not None
                or lead_obj.viewing_at is not None
            ):
                return True
            return any(
                ev.new_value in (
                    "contacted",
                    "qualified",
                    "viewing_scheduled",
                    "negotiation",
                    "won",
                )
                for ev in lead_obj.events
            )

        def _reached_qualified(lead_obj: Lead) -> bool:
            if lead_obj.stage in ("qualified", "viewing_scheduled", "negotiation", "won"):
                return True
            if lead_obj.qualified_at is not None or lead_obj.viewing_at is not None:
                return True
            return any(
                ev.new_value in ("qualified", "viewing_scheduled", "negotiation", "won")
                for ev in lead_obj.events
            )

        def _reached_viewing(lead_obj: Lead) -> bool:
            if lead_obj.stage in ("viewing_scheduled", "negotiation", "won"):
                return True
            if lead_obj.viewing_at is not None:
                return True
            return any(
                ev.new_value in ("viewing_scheduled", "negotiation", "won")
                for ev in lead_obj.events
            )

        def _reached_negotiation(lead_obj: Lead) -> bool:
            if lead_obj.stage in ("negotiation", "won"):
                return True
            return any(
                ev.new_value in ("negotiation", "won")
                for ev in lead_obj.events
            )

        reached_contacted_or_more = sum(1 for lead_item in leads if _reached_contacted(lead_item))
        reached_qualified_or_more = sum(1 for lead_item in leads if _reached_qualified(lead_item))
        reached_viewing_or_more = sum(1 for lead_item in leads if _reached_viewing(lead_item))
        reached_negotiation_or_more = sum(
            1 for lead_item in leads if _reached_negotiation(lead_item)
        )

        closed_leads = won_leads + lost_leads
        overall_win_rate = cls._safe_percentage(
            won_leads, closed_leads if closed_leads > 0 else total_leads
        )
        lead_to_contacted_rate = cls._safe_percentage(reached_contacted_or_more, total_leads)
        contacted_to_qualified_rate = cls._safe_percentage(
            reached_qualified_or_more, reached_contacted_or_more
        )
        qualified_to_viewing_rate = cls._safe_percentage(
            reached_viewing_or_more, reached_qualified_or_more
        )
        viewing_to_negotiation_rate = cls._safe_percentage(
            reached_negotiation_or_more, reached_viewing_or_more
        )
        negotiation_to_won_rate = cls._safe_percentage(won_leads, reached_negotiation_or_more)

        lead_funnel = {
            "total_leads": total_leads,
            "new_leads": new_leads,
            "contacted_leads": contacted_leads,
            "qualified_leads": qualified_leads,
            "viewing_scheduled_leads": viewing_scheduled_leads,
            "negotiation_leads": negotiation_leads,
            "won_leads": won_leads,
            "lost_leads": lost_leads,
            "active_leads": active_leads,
            "reached_contacted": reached_contacted_or_more,
            "reached_qualified": reached_qualified_or_more,
            "reached_viewing": reached_viewing_or_more,
            "reached_negotiation": reached_negotiation_or_more,
            "conversion_rates": {
                "overall_win_rate": overall_win_rate,
                "lead_to_contacted_rate": lead_to_contacted_rate,
                "contacted_to_qualified_rate": contacted_to_qualified_rate,
                "qualified_to_viewing_rate": qualified_to_viewing_rate,
                "viewing_to_negotiation_rate": viewing_to_negotiation_rate,
                "negotiation_to_won_rate": negotiation_to_won_rate,
            },
        }

        # ---------------------------------------------------------------------
        # 2. Response Time KPIs (Earliest genuine contact event)
        # ---------------------------------------------------------------------
        durations_sec: list[float] = []
        for lead_item in leads:
            candidates: list[datetime] = []
            if lead_item.contacted_at:
                candidates.append(lead_item.contacted_at)
            for ev in lead_item.events:
                if (
                    ev.event_type == "stage_change"
                    and ev.new_value in (
                        "contacted",
                        "qualified",
                        "viewing_scheduled",
                        "negotiation",
                        "won",
                    )
                ) or (ev.old_value == "new" and ev.new_value != "new"):
                    candidates.append(ev.created_at)
            for note in lead_item.notes:
                candidates.append(note.created_at)
            for fu in lead_item.followups:
                # Exclude pending/scheduled future due_at, exclude cancelled.
                # Only completed followups count as genuine past contact.
                if fu.status == "completed" and fu.completed_at:
                    candidates.append(fu.completed_at)

            # Strict bounds check: lead.created_at <= contact <= now_utc
            lead_created = cls._to_utc(lead_item.created_at)
            valid_contacts = [
                c
                for ts in candidates
                if (c := cls._to_utc(ts)) is not None
                and lead_created is not None
                and lead_created <= c <= now_utc
            ]
            if valid_contacts and lead_created is not None:
                first_contact = min(valid_contacts)
                diff = (first_contact - lead_created).total_seconds()
                if diff >= 0:
                    durations_sec.append(diff)

        if durations_sec:
            durations_sec.sort()
            avg_resp = round(statistics.mean(durations_sec), 1)
            med_resp = round(statistics.median(durations_sec), 1)
            if len(durations_sec) >= 2:
                # 90th percentile using inclusive decile calculation
                quantiles_list = statistics.quantiles(durations_sec, n=10, method="inclusive")
                p90_resp = round(quantiles_list[8], 1)
            else:
                p90_resp = round(durations_sec[0], 1)
        else:
            avg_resp = None
            med_resp = None
            p90_resp = None

        response_time = {
            "sample_size": len(durations_sec),
            "average_seconds": avg_resp,
            "median_seconds": med_resp,
            "p90_seconds": p90_resp,
            "average_minutes": round(avg_resp / 60.0, 1) if avg_resp is not None else None,
            "median_minutes": round(med_resp / 60.0, 1) if med_resp is not None else None,
            "p90_minutes": round(p90_resp / 60.0, 1) if p90_resp is not None else None,
            "insufficient_data": len(durations_sec) < 3,
        }

        # ---------------------------------------------------------------------
        # 3. Viewing KPIs
        # ---------------------------------------------------------------------
        viewing_stmt = (
            select(ViewingRequest.status, func.count(ViewingRequest.id))
            .where(ViewingRequest.created_at >= start_dt, ViewingRequest.created_at <= end_dt)
            .group_by(ViewingRequest.status)
        )
        viewing_counts = dict((await session.execute(viewing_stmt)).all())

        total_viewings = sum(viewing_counts.values())
        pending_viewings = viewing_counts.get("pending", 0)
        accepted_viewings = viewing_counts.get("accepted", 0)
        rejected_viewings = viewing_counts.get("rejected", 0)
        cancelled_viewings = viewing_counts.get("cancelled", 0)
        completed_viewings = viewing_counts.get("completed", 0)

        viewing_completion_rate = cls._safe_percentage(completed_viewings, total_viewings)
        viewing_cancellation_rate = cls._safe_percentage(cancelled_viewings, total_viewings)

        # Viewing to Won: count distinct leads won that originated from a completed viewing
        won_from_viewing_stmt = (
            select(func.count(distinct(Lead.id)))
            .join(ViewingRequest, Lead.source_request_id == ViewingRequest.id)
            .where(
                Lead.created_at >= start_dt,
                Lead.created_at <= end_dt,
                Lead.stage == "won",
                ViewingRequest.status == "completed",
            )
        )
        won_from_viewing_count = (await session.execute(won_from_viewing_stmt)).scalar_one() or 0
        viewing_to_won_rate = cls._safe_percentage(won_from_viewing_count, completed_viewings)

        viewings_kpi = {
            "total_viewings": total_viewings,
            "pending": pending_viewings,
            "accepted": accepted_viewings,
            "rejected": rejected_viewings,
            "cancelled": cancelled_viewings,
            "completed": completed_viewings,
            "completion_rate": viewing_completion_rate,
            "cancellation_rate": viewing_cancellation_rate,
            "viewing_to_won_rate": viewing_to_won_rate,
        }

        # ---------------------------------------------------------------------
        # 4. Property Inventory & Moderation KPIs
        # ---------------------------------------------------------------------
        prop_status_stmt = (
            select(Property.status, func.count(Property.id))
            .where(Property.created_at >= start_dt, Property.created_at <= end_dt)
            .group_by(Property.status)
        )
        prop_status_counts = dict((await session.execute(prop_status_stmt)).all())

        total_properties = sum(prop_status_counts.values())
        approved_props = prop_status_counts.get("approved", 0)
        submitted_props = prop_status_counts.get("submitted", 0)
        under_review_props = prop_status_counts.get("under_review", 0)
        rejected_props = prop_status_counts.get("rejected", 0)
        archived_props = prop_status_counts.get("archived", 0)
        sold_props = prop_status_counts.get("sold", 0)
        rented_props = prop_status_counts.get("rented", 0)

        moderation_backlog = submitted_props + under_review_props

        # Breakdown by listing_type
        listing_type_stmt = (
            select(Property.listing_type, func.count(Property.id))
            .where(Property.created_at >= start_dt, Property.created_at <= end_dt)
            .group_by(Property.listing_type)
        )
        by_listing_type = dict((await session.execute(listing_type_stmt)).all())

        # Breakdown by property_type
        prop_type_stmt = (
            select(Property.property_type, func.count(Property.id))
            .where(Property.created_at >= start_dt, Property.created_at <= end_dt)
            .group_by(Property.property_type)
        )
        by_property_type = dict((await session.execute(prop_type_stmt)).all())

        # Top 5 districts
        district_stmt = (
            select(Property.district, func.count(Property.id))
            .where(
                Property.created_at >= start_dt,
                Property.created_at <= end_dt,
                Property.district.is_not(None),
            )
            .group_by(Property.district)
            .order_by(func.count(Property.id).desc())
            .limit(5)
        )
        by_district = dict((await session.execute(district_stmt)).all())

        properties_kpi = {
            "total_properties": total_properties,
            "approved": approved_props,
            "moderation_backlog": moderation_backlog,
            "submitted": submitted_props,
            "under_review": under_review_props,
            "rejected": rejected_props,
            "archived": archived_props,
            "sold": sold_props,
            "rented": rented_props,
            "by_listing_type": by_listing_type,
            "by_property_type": by_property_type,
            "top_districts": by_district,
        }

        # ---------------------------------------------------------------------
        # 5. Broker Operational KPIs (Explainable & Non-discriminatory)
        # ---------------------------------------------------------------------
        now_utc = datetime.now(UTC)

        # Fetch active staff with broker roles
        brokers_stmt = (
            select(User)
            .join(User.roles)
            .options(selectinload(User.roles))
            .where(Role.name.in_(BROKER_ROLE_NAMES), User.is_active.is_(True))
            .distinct()
        )
        broker_users = list((await session.execute(brokers_stmt)).scalars().all())

        # Total overdue followups across system
        total_overdue_stmt = select(func.count(LeadFollowUp.id)).where(
            LeadFollowUp.status == "pending",
            LeadFollowUp.due_at < now_utc,
        )
        total_overdue_followups = (await session.execute(total_overdue_stmt)).scalar_one() or 0

        broker_metrics_list = []
        for b_user in broker_users:
            b_leads_stmt = (
                select(Lead.stage, func.count(Lead.id))
                .where(
                    Lead.broker_user_id == b_user.id,
                    Lead.created_at >= start_dt,
                    Lead.created_at <= end_dt,
                )
                .group_by(Lead.stage)
            )
            b_stages = dict((await session.execute(b_leads_stmt)).all())
            b_assigned = sum(b_stages.values())
            b_won = b_stages.get("won", 0)
            b_lost = b_stages.get("lost", 0)
            b_active = sum(b_stages.get(s, 0) for s in ACTIVE_LEAD_STAGES)

            # Broker overdue followups
            b_overdue_stmt = select(func.count(LeadFollowUp.id)).where(
                LeadFollowUp.broker_user_id == b_user.id,
                LeadFollowUp.status == "pending",
                LeadFollowUp.due_at < now_utc,
            )
            b_overdue = (await session.execute(b_overdue_stmt)).scalar_one() or 0

            # Broker completed viewings
            b_viewings_stmt = select(func.count(ViewingRequest.id)).where(
                ViewingRequest.broker_user_id == b_user.id,
                ViewingRequest.created_at >= start_dt,
                ViewingRequest.created_at <= end_dt,
                ViewingRequest.status == "completed",
            )
            b_completed_viewings = (await session.execute(b_viewings_stmt)).scalar_one() or 0

            b_name = (
                f"{b_user.first_name or ''} {b_user.last_name or ''}".strip()
                or f"Broker #{b_user.id}"
            )

            broker_metrics_list.append(
                {
                    "broker_id": b_user.id,
                    "name": b_name,
                    "username": b_user.username,
                    "assigned_leads": b_assigned,
                    "active_leads": b_active,
                    "won_leads": b_won,
                    "lost_leads": b_lost,
                    "win_rate": cls._safe_percentage(
                        b_won, (b_won + b_lost) if (b_won + b_lost) > 0 else b_assigned
                    ),
                    "completed_viewings": b_completed_viewings,
                    "overdue_followups": b_overdue,
                }
            )

        brokers_kpi = {
            "total_active_brokers": len(broker_users),
            "total_overdue_followups": total_overdue_followups,
            "brokers": broker_metrics_list,
        }

        # ---------------------------------------------------------------------
        # 6. CRM Health KPIs (amoCRM outbox synchronization)
        # ---------------------------------------------------------------------
        crm_status_stmt = (
            select(CRMSyncEvent.status, func.count(CRMSyncEvent.id))
            .where(CRMSyncEvent.provider == "amocrm")
            .group_by(CRMSyncEvent.status)
        )
        crm_status_counts = dict((await session.execute(crm_status_stmt)).all())

        pending_crm = crm_status_counts.get("pending", 0)
        processing_crm = crm_status_counts.get("processing", 0)
        succeeded_crm = crm_status_counts.get("succeeded", 0)
        failed_crm = crm_status_counts.get("failed", 0)

        # Permanent failed (attempt_count >= 5)
        perm_failed_stmt = select(func.count(CRMSyncEvent.id)).where(
            CRMSyncEvent.provider == "amocrm",
            CRMSyncEvent.status == "failed",
            CRMSyncEvent.attempt_count >= 5,
        )
        perm_failed_crm = (await session.execute(perm_failed_stmt)).scalar_one() or 0

        total_crm_closed = succeeded_crm + failed_crm
        crm_success_rate = cls._safe_percentage(succeeded_crm, total_crm_closed)

        crm_kpi = {
            "pending_events": pending_crm,
            "processing_events": processing_crm,
            "succeeded_events": succeeded_crm,
            "failed_events": failed_crm,
            "permanent_failed_events": perm_failed_crm,
            "sync_success_rate": crm_success_rate,
        }

        return {
            "date_from": str(date_range.date_from),
            "date_to": str(date_range.date_to),
            "lead_funnel": lead_funnel,
            "response_time": response_time,
            "viewings": viewings_kpi,
            "properties": properties_kpi,
            "brokers": brokers_kpi,
            "crm_health": crm_kpi,
        }

    @classmethod
    async def get_metric_snapshot(
        cls,
        session: AsyncSession,
        metric_key: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict[str, Any]:
        """Compute a single point-in-time deterministic metric snapshot for a PDCA cycle."""
        date_range = KaizenDateRange(date_from=date_from, date_to=date_to)
        overview = await cls.get_kpi_overview(session, date_range)

        # Map known metric keys
        metric_val: float | int | None = None
        numerator: int | float | None = None
        denominator: int | float | None = None
        unit = "percentage"
        insufficient = False

        if metric_key == "overall_win_rate":
            metric_val = overview["lead_funnel"]["conversion_rates"]["overall_win_rate"]
            numerator = overview["lead_funnel"]["won_leads"]
            denominator = (
                overview["lead_funnel"]["won_leads"] + overview["lead_funnel"]["lost_leads"]
            )
            unit = "percentage"
            insufficient = (denominator or 0) < 3

        elif metric_key == "lead_to_contacted_rate":
            metric_val = overview["lead_funnel"]["conversion_rates"]["lead_to_contacted_rate"]
            numerator = overview["lead_funnel"]["reached_contacted"]
            denominator = overview["lead_funnel"]["total_leads"]
            unit = "percentage"
            insufficient = (denominator or 0) < 3

        elif metric_key == "median_response_time":
            metric_val = overview["response_time"]["median_minutes"]
            numerator = overview["response_time"]["median_seconds"]
            denominator = overview["response_time"]["sample_size"]
            unit = "minutes"
            insufficient = overview["response_time"]["insufficient_data"]

        elif metric_key == "viewing_completion_rate":
            metric_val = overview["viewings"]["completion_rate"]
            numerator = overview["viewings"]["completed"]
            denominator = overview["viewings"]["total_viewings"]
            unit = "percentage"
            insufficient = (denominator or 0) < 3

        elif metric_key == "viewing_cancellation_rate":
            metric_val = overview["viewings"]["cancellation_rate"]
            numerator = overview["viewings"]["cancelled"]
            denominator = overview["viewings"]["total_viewings"]
            unit = "percentage"
            insufficient = (denominator or 0) < 3

        elif metric_key == "crm_failed_events":
            metric_val = overview["crm_health"]["failed_events"]
            numerator = overview["crm_health"]["failed_events"]
            denominator = None
            unit = "count"
            insufficient = False

        elif metric_key == "overdue_followups":
            metric_val = overview["brokers"]["total_overdue_followups"]
            numerator = overview["brokers"]["total_overdue_followups"]
            denominator = None
            unit = "count"
            insufficient = False

        elif metric_key == "moderation_backlog":
            metric_val = overview["properties"]["moderation_backlog"]
            numerator = overview["properties"]["moderation_backlog"]
            denominator = None
            unit = "count"
            insufficient = False

        else:
            raise ValueError(f"Unknown Kaizen metric key: '{metric_key}'")

        return {
            "metric_key": metric_key,
            "value": metric_val,
            "numerator": numerator,
            "denominator": denominator,
            "unit": unit,
            "insufficient_data": insufficient,
            "date_from": str(date_range.date_from),
            "date_to": str(date_range.date_to),
            "captured_at": datetime.now(UTC).isoformat(),
        }
