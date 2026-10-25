"""Tests for Lead, FollowUp, Note, and Event model structures and relationships."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import (
    ACTIVE_LEAD_STAGES,
    FOLLOWUP_STATUSES,
    FOLLOWUP_TYPES,
    LEAD_SOURCES,
    LEAD_STAGES,
    LOST_REASONS,
    TERMINAL_LEAD_STAGES,
    Lead,
    LeadEvent,
    LeadFollowUp,
    LeadNote,
)
from app.models.property import Property
from app.models.user import User
from app.models.viewing_request import ViewingRequest


def test_lead_domain_constants() -> None:
    """Verify canonical lead constants."""
    assert "broker_contact" in LEAD_SOURCES
    assert "viewing" in LEAD_SOURCES
    assert "manual" in LEAD_SOURCES

    assert "new" in LEAD_STAGES
    assert "contacted" in LEAD_STAGES
    assert "qualified" in LEAD_STAGES
    assert "viewing_scheduled" in LEAD_STAGES
    assert "negotiation" in LEAD_STAGES
    assert "won" in LEAD_STAGES
    assert "lost" in LEAD_STAGES

    assert "new" in ACTIVE_LEAD_STAGES
    assert "negotiation" in ACTIVE_LEAD_STAGES
    assert "won" not in ACTIVE_LEAD_STAGES
    assert "lost" not in ACTIVE_LEAD_STAGES

    assert "won" in TERMINAL_LEAD_STAGES
    assert "lost" in TERMINAL_LEAD_STAGES

    assert "call" in FOLLOWUP_TYPES
    assert "message" in FOLLOWUP_TYPES
    assert "meeting" in FOLLOWUP_TYPES
    assert "other" in FOLLOWUP_TYPES

    assert "pending" in FOLLOWUP_STATUSES
    assert "completed" in FOLLOWUP_STATUSES
    assert "cancelled" in FOLLOWUP_STATUSES

    assert "price" in LOST_REASONS
    assert "not_interested" in LOST_REASONS
    assert "competitor" in LOST_REASONS
    assert "property_unavailable" in LOST_REASONS
    assert "no_response" in LOST_REASONS
    assert "other" in LOST_REASONS


@pytest.mark.asyncio
async def test_lead_model_relationships(db_session: AsyncSession) -> None:
    """Verify Lead, FollowUp, Note, and Event model persistence and bidirectional links."""
    customer = User(
        telegram_id=991001,
        language="uz",
        first_name="Customer 1",
        consent_accepted_at=datetime.now(UTC),
    )
    broker = User(
        telegram_id=991002,
        language="uz",
        first_name="Broker 1",
        consent_accepted_at=datetime.now(UTC),
    )
    db_session.add_all([customer, broker])
    await db_session.flush()

    prop = Property(
        owner_user_id=customer.id,
        listing_type="sale",
        property_type="apartment",
        title="Lead Test Prop",
        region="Toshkent",
        district="Yunusobod",
        address="Amir Temur ko'chasi 10",
        rooms=3,
        total_area=85.0,
        condition="euro",
        cadastre_status="available",
        price=105000.0,
        currency="USD",
        status="approved",
    )
    db_session.add(prop)
    await db_session.flush()

    req = ViewingRequest(
        property_id=prop.id,
        customer_user_id=customer.id,
        broker_user_id=broker.id,
        request_type="viewing",
        status="accepted",
    )
    db_session.add(req)
    await db_session.flush()

    lead = Lead(
        customer_user_id=customer.id,
        property_id=prop.id,
        broker_user_id=broker.id,
        source_request_id=req.id,
        source="viewing",
        stage="new",
    )
    db_session.add(lead)
    await db_session.flush()

    followup = LeadFollowUp(
        lead_id=lead.id,
        broker_user_id=broker.id,
        task_type="call",
        due_at=datetime.now(UTC) + timedelta(days=1),
        note="Call customer to discuss viewing details",
    )
    note = LeadNote(
        lead_id=lead.id,
        author_user_id=broker.id,
        text="Customer interested in 3rd floor views",
    )
    event = LeadEvent(
        lead_id=lead.id,
        actor_user_id=broker.id,
        event_type="created",
        new_value="new",
    )
    db_session.add_all([followup, note, event])
    await db_session.flush()

    stmt = select(Lead).where(Lead.id == lead.id)
    res = await db_session.execute(stmt)
    loaded_lead = res.scalar_one()

    assert loaded_lead.id == lead.id
    assert loaded_lead.customer.id == customer.id
    assert loaded_lead.broker is not None and loaded_lead.broker.id == broker.id
    assert loaded_lead.property.id == prop.id
    assert loaded_lead.source_request is not None and loaded_lead.source_request.id == req.id
    assert len(loaded_lead.followups) == 1
    assert loaded_lead.followups[0].task_type == "call"
    assert len(loaded_lead.notes) == 1
    assert loaded_lead.notes[0].text == "Customer interested in 3rd floor views"
    assert len(loaded_lead.events) == 1
    assert loaded_lead.events[0].event_type == "created"

    # Verify back-populates on User and Property after refresh
    await db_session.refresh(customer, ["leads_as_customer"])
    await db_session.refresh(broker, ["leads_as_broker"])
    await db_session.refresh(prop, ["leads"])
    await db_session.refresh(req, ["leads"])
    assert len(customer.leads_as_customer) == 1
    assert len(broker.leads_as_broker) == 1
    assert len(prop.leads) == 1
    assert len(req.leads) == 1
