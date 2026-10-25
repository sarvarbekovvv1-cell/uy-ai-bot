"""Tests for LeadService business logic, RBAC, deduplication, followups, and audit trails."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InvalidLeadTransitionError,
    LeadPermissionError,
    LeadValidationError,
)
from app.models.property import Property
from app.models.role import Role
from app.models.user import User
from app.models.viewing_request import ViewingRequest
from app.repositories.role_repository import RoleRepository
from app.services.lead_service import LeadService


async def _create_user_with_role(
    session: AsyncSession,
    telegram_id: int,
    role_name: str,
    first_name: str = "TestUser",
    phone: str = "+998901234567",
) -> User:
    """Helper to create and persist user with specific role."""
    role_repo = RoleRepository()
    await role_repo.ensure_default_roles(session)
    role = await role_repo.get_by_name(session, role_name)
    if not role:
        role = Role(name=role_name, description=f"{role_name} role")
        session.add(role)
        await session.flush()

    user = User(
        telegram_id=telegram_id,
        first_name=first_name,
        phone=phone,
        language="uz",
        is_active=True,
        is_verified=True,
        consent_accepted_at=datetime.now(UTC),
    )
    user.roles.append(role)
    session.add(user)
    await session.flush()
    return user


async def _create_property(
    session: AsyncSession,
    owner_id: int,
    listing_type: str = "sale",
    status: str = "approved",
) -> Property:
    """Helper to create property."""
    prop = Property(
        owner_user_id=owner_id,
        listing_type=listing_type,
        property_type="apartment",
        title=f"Property {listing_type}",
        region="Toshkent",
        district="Chilonzor",
        address="Bunyodkor ko'chasi 1",
        rooms=2,
        total_area=65.0,
        condition="euro",
        cadastre_status="available",
        price=75000.0,
        currency="USD",
        status=status,
    )
    session.add(prop)
    await session.flush()
    return prop


@pytest.mark.asyncio
async def test_lead_service_rbac_boundaries(db_session: AsyncSession) -> None:
    """Verify RBAC listing type restrictions for brokers."""
    customer = await _create_user_with_role(db_session, 1001, "customer", "Customer")
    sales_broker = await _create_user_with_role(db_session, 1002, "sales_broker", "Sales Broker")
    rental_broker = await _create_user_with_role(db_session, 1003, "rental_broker", "Rental Broker")
    head_broker = await _create_user_with_role(db_session, 1004, "head_broker", "Head Broker")
    plain_customer = await _create_user_with_role(db_session, 1005, "customer", "Plain Customer")

    service = LeadService()

    # Allowed listing types
    assert await service.get_broker_allowed_listing_types(db_session, sales_broker.id) == ["sale"]
    assert await service.get_broker_allowed_listing_types(db_session, rental_broker.id) == ["rent"]
    assert sorted(await service.get_broker_allowed_listing_types(db_session, head_broker.id)) == [
        "rent",
        "sale",
    ]
    assert await service.get_broker_allowed_listing_types(db_session, plain_customer.id) == []

    sale_prop = await _create_property(db_session, customer.id, "sale")
    rent_prop = await _create_property(db_session, customer.id, "rent")

    sale_lead = await service.create_lead(
        db_session, customer_user_id=customer.id, property_id=sale_prop.id, source="manual"
    )
    rent_lead = await service.create_lead(
        db_session, customer_user_id=customer.id, property_id=rent_prop.id, source="manual"
    )

    # Sales broker can access sale_lead, denied on rent_lead
    loaded_sale = await service.get_lead(
        db_session, lead_id=sale_lead.id, broker_user_id=sales_broker.id
    )
    assert loaded_sale.id == sale_lead.id

    with pytest.raises(LeadPermissionError):
        await service.get_lead(db_session, lead_id=rent_lead.id, broker_user_id=sales_broker.id)

    # Rental broker can access rent_lead, denied on sale_lead
    loaded_rent = await service.get_lead(
        db_session, lead_id=rent_lead.id, broker_user_id=rental_broker.id
    )
    assert loaded_rent.id == rent_lead.id

    with pytest.raises(LeadPermissionError):
        await service.get_lead(db_session, lead_id=sale_lead.id, broker_user_id=rental_broker.id)

    # Head broker can access both
    assert (
        await service.get_lead(db_session, lead_id=sale_lead.id, broker_user_id=head_broker.id)
    ).id == sale_lead.id
    assert (
        await service.get_lead(db_session, lead_id=rent_lead.id, broker_user_id=head_broker.id)
    ).id == rent_lead.id


@pytest.mark.asyncio
async def test_lead_deduplication_policy(db_session: AsyncSession) -> None:
    """Verify active lead deduplication per (customer, property)."""
    customer = await _create_user_with_role(db_session, 2001, "customer", "Customer")
    broker = await _create_user_with_role(db_session, 2002, "sales_broker", "Broker")
    prop = await _create_property(db_session, customer.id, "sale")

    service = LeadService()

    # 1. First lead creation
    lead1 = await service.create_lead(
        db_session, customer_user_id=customer.id, property_id=prop.id, source="manual"
    )

    # 2. Duplicate attempt returns existing active lead
    lead2 = await service.create_lead(
        db_session, customer_user_id=customer.id, property_id=prop.id, source="viewing"
    )
    assert lead1.id == lead2.id

    # 3. Request linking via ensure_lead_for_request
    req = ViewingRequest(
        property_id=prop.id,
        customer_user_id=customer.id,
        request_type="viewing",
        status="pending",
    )
    db_session.add(req)
    await db_session.flush()

    lead3 = await service.ensure_lead_for_request(db_session, request=req, broker_user_id=broker.id)
    assert lead3.id == lead1.id
    assert lead3.broker_user_id == broker.id

    # 4. Close the lead (won), then a new request creates a new lead
    await service.update_stage(
        db_session, lead_id=lead1.id, broker_user_id=broker.id, target_stage="won"
    )

    lead4 = await service.create_lead(
        db_session, customer_user_id=customer.id, property_id=prop.id, source="manual"
    )
    assert lead4.id != lead1.id
    assert lead4.stage == "new"


@pytest.mark.asyncio
async def test_lead_stage_transitions_and_rules(db_session: AsyncSession) -> None:
    """Verify allowed and disallowed lead stage transitions."""
    customer = await _create_user_with_role(db_session, 3001, "customer", "Customer")
    broker = await _create_user_with_role(db_session, 3002, "sales_broker", "Broker")
    prop = await _create_property(db_session, customer.id, "sale")

    service = LeadService()
    lead = await service.create_lead(
        db_session,
        customer_user_id=customer.id,
        property_id=prop.id,
        broker_user_id=broker.id,
        source="manual",
    )

    assert lead.stage == "new"

    # Forward progression: new -> contacted
    lead = await service.update_stage(
        db_session, lead_id=lead.id, broker_user_id=broker.id, target_stage="contacted"
    )
    assert lead.stage == "contacted"
    assert lead.contacted_at is not None

    # contacted -> qualified
    lead = await service.update_stage(
        db_session, lead_id=lead.id, broker_user_id=broker.id, target_stage="qualified"
    )
    assert lead.stage == "qualified"
    assert lead.qualified_at is not None

    # qualified -> viewing_scheduled
    lead = await service.update_stage(
        db_session, lead_id=lead.id, broker_user_id=broker.id, target_stage="viewing_scheduled"
    )
    assert lead.stage == "viewing_scheduled"
    assert lead.viewing_at is not None

    # viewing_scheduled -> negotiation
    lead = await service.update_stage(
        db_session, lead_id=lead.id, broker_user_id=broker.id, target_stage="negotiation"
    )
    assert lead.stage == "negotiation"

    # Backwards progression allowed: negotiation -> contacted
    lead = await service.update_stage(
        db_session, lead_id=lead.id, broker_user_id=broker.id, target_stage="contacted"
    )
    assert lead.stage == "contacted"

    # Lost requires valid reason
    with pytest.raises(LeadValidationError):
        await service.update_stage(
            db_session, lead_id=lead.id, broker_user_id=broker.id, target_stage="lost"
        )

    # Valid lost close
    lead = await service.update_stage(
        db_session,
        lead_id=lead.id,
        broker_user_id=broker.id,
        target_stage="lost",
        close_reason="price",
    )
    assert lead.stage == "lost"
    assert lead.close_reason == "price"
    assert lead.closed_at is not None

    # Terminal state cannot be updated
    with pytest.raises(InvalidLeadTransitionError):
        await service.update_stage(
            db_session, lead_id=lead.id, broker_user_id=broker.id, target_stage="contacted"
        )


@pytest.mark.asyncio
async def test_followup_scheduling_and_filtering(db_session: AsyncSession) -> None:
    """Verify follow-up tasks lifecycle, overdue filtering, and completion."""
    customer = await _create_user_with_role(db_session, 4001, "customer", "Customer")
    broker = await _create_user_with_role(db_session, 4002, "sales_broker", "Broker")
    other_broker = await _create_user_with_role(db_session, 4003, "sales_broker", "Other Broker")
    prop = await _create_property(db_session, customer.id, "sale")

    service = LeadService()
    lead = await service.create_lead(
        db_session,
        customer_user_id=customer.id,
        property_id=prop.id,
        broker_user_id=broker.id,
        source="manual",
    )

    # Other broker cannot add follow-up
    with pytest.raises(LeadPermissionError):
        await service.create_followup(
            db_session,
            lead_id=lead.id,
            broker_user_id=other_broker.id,
            task_type="call",
            due_at=datetime.now(UTC) + timedelta(hours=2),
        )

    # Past due_at rejected
    with pytest.raises(LeadValidationError):
        await service.create_followup(
            db_session,
            lead_id=lead.id,
            broker_user_id=broker.id,
            task_type="call",
            due_at=datetime.now(UTC) - timedelta(hours=1),
        )

    # Valid task scheduled for today
    today_due = datetime.now(UTC) + timedelta(hours=2)
    task1 = await service.create_followup(
        db_session,
        lead_id=lead.id,
        broker_user_id=broker.id,
        task_type="call",
        due_at=today_due,
        note="Call customer to clarify budget",
    )
    assert task1.status == "pending"

    # List today's tasks
    today_tasks = await service.list_followups(
        db_session, broker_user_id=broker.id, filter_type="today"
    )
    assert len(today_tasks) == 1
    assert today_tasks[0].id == task1.id

    # Complete task
    completed = await service.complete_followup(
        db_session, followup_id=task1.id, broker_user_id=broker.id
    )
    assert completed.status == "completed"
    assert completed.completed_at is not None

    # Cancel task check
    task2 = await service.create_followup(
        db_session,
        lead_id=lead.id,
        broker_user_id=broker.id,
        task_type="message",
        due_at=datetime.now(UTC) + timedelta(days=2),
    )
    cancelled = await service.cancel_followup(
        db_session, followup_id=task2.id, broker_user_id=broker.id
    )
    assert cancelled.status == "cancelled"
    assert cancelled.cancelled_at is not None


@pytest.mark.asyncio
async def test_lead_notes_and_customer_privacy(db_session: AsyncSession) -> None:
    """Verify internal broker notes and phone visibility privacy rule."""
    customer = await _create_user_with_role(
        db_session, 5001, "customer", "Customer", phone="+998901112233"
    )
    assigned_broker = await _create_user_with_role(db_session, 5002, "sales_broker", "Assigned")
    other_broker = await _create_user_with_role(db_session, 5003, "sales_broker", "Other")
    head_broker = await _create_user_with_role(db_session, 5004, "head_broker", "Head")
    prop = await _create_property(db_session, customer.id, "sale")

    service = LeadService()
    lead = await service.create_lead(
        db_session,
        customer_user_id=customer.id,
        property_id=prop.id,
        broker_user_id=assigned_broker.id,
        source="manual",
    )

    # Privacy: assigned broker can see phone
    assert (
        await service.can_view_customer_phone(
            db_session, lead=lead, requester_user_id=assigned_broker.id
        )
        is True
    )

    # Privacy: other broker cannot see phone
    assert (
        await service.can_view_customer_phone(
            db_session, lead=lead, requester_user_id=other_broker.id
        )
        is False
    )

    # Privacy: head broker can see phone
    assert (
        await service.can_view_customer_phone(
            db_session, lead=lead, requester_user_id=head_broker.id
        )
        is True
    )

    # Add note
    note = await service.add_note(
        db_session,
        lead_id=lead.id,
        author_user_id=assigned_broker.id,
        text="Customer is applying for mortgage with Ipoteka Bank.",
    )
    assert note.text == "Customer is applying for mortgage with Ipoteka Bank."

    # Verify audit events exist
    events = await service.lead_repo.list_events(db_session, lead_id=lead.id)
    event_types = [e.event_type for e in events]
    assert "created" in event_types
    assert "note_added" in event_types
