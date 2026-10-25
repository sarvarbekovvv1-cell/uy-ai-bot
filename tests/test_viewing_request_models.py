"""Tests for ViewingRequest model structure, constraints, and relationships."""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property import Property
from app.models.user import User
from app.models.viewing_request import (
    REQUEST_STATUSES,
    REQUEST_TYPES,
    VIEWING_OUTCOMES,
    ViewingRequest,
)


def test_viewing_request_constants() -> None:
    """Verify canonical constants for types, statuses, and outcomes."""
    assert "viewing" in REQUEST_TYPES
    assert "broker_contact" in REQUEST_TYPES

    assert "pending" in REQUEST_STATUSES
    assert "assigned" in REQUEST_STATUSES
    assert "accepted" in REQUEST_STATUSES
    assert "rejected" in REQUEST_STATUSES
    assert "cancelled" in REQUEST_STATUSES
    assert "completed" in REQUEST_STATUSES

    assert "interested" in VIEWING_OUTCOMES
    assert "not_interested" in VIEWING_OUTCOMES
    assert "reschedule_requested" in VIEWING_OUTCOMES
    assert "no_show" in VIEWING_OUTCOMES


@pytest.mark.asyncio
async def test_viewing_request_model_relationships(db_session: AsyncSession) -> None:
    """Verify ViewingRequest model persistence and bidirectional relationships."""
    customer = User(
        telegram_id=888001,
        language="uz",
        first_name="Customer",
        consent_accepted_at=datetime.now(UTC),
    )
    broker = User(
        telegram_id=888002,
        language="uz",
        first_name="Broker",
        consent_accepted_at=datetime.now(UTC),
    )
    db_session.add_all([customer, broker])
    await db_session.flush()

    prop = Property(
        owner_user_id=customer.id,
        listing_type="sale",
        property_type="apartment",
        title="Relationship Test Prop",
        region="Toshkent",
        district="Yunusobod",
        address="Ko‘cha 1",
        rooms=2,
        total_area=50.0,
        condition="euro",
        cadastre_status="available",
        price=60000,
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
        preferred_date=date(2026, 11, 1),
        preferred_time="11:00",
        customer_comment="Salom",
        status="pending",
    )
    db_session.add(req)
    await db_session.flush()

    assert req.id is not None
    assert req.property.id == prop.id
    assert req.customer.id == customer.id
    assert req.broker.id == broker.id

    # Check back-populates on Property
    res_prop = (
        await db_session.execute(select(Property).where(Property.id == prop.id))
    ).scalar_one()
    assert len(res_prop.viewing_requests) == 1
    assert res_prop.viewing_requests[0].id == req.id

    # Check back-populates on User
    res_cust = (await db_session.execute(select(User).where(User.id == customer.id))).scalar_one()
    assert len(res_cust.viewing_requests_as_customer) == 1

    res_broker = (await db_session.execute(select(User).where(User.id == broker.id))).scalar_one()
    assert len(res_broker.viewing_requests_as_broker) == 1
