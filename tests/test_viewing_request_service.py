"""Tests for ViewingRequestService lifecycle, RBAC, validations, and transitions."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DuplicateViewingRequestError,
    InvalidViewingTransitionError,
    PropertyUnavailableError,
    ViewingPermissionError,
    ViewingValidationError,
)
from app.models.property import Property
from app.models.user import User
from app.repositories.role_repository import RoleRepository
from app.services.viewing_request_service import ViewingRequestService


@pytest.fixture
async def seeded_entities(db_session: AsyncSession) -> dict[str, int]:
    """Seed users, roles, and properties for viewing tests."""
    role_repo = RoleRepository()
    await role_repo.ensure_default_roles(db_session)

    # 1. Customer
    customer = User(
        telegram_id=111001,
        language="uz",
        first_name="Customer",
        phone="+998901110001",
        consent_accepted_at=datetime.now(UTC),
    )
    # 2. Other customer
    other_customer = User(
        telegram_id=111002,
        language="uz",
        first_name="OtherCustomer",
        phone="+998901110002",
        consent_accepted_at=datetime.now(UTC),
    )
    # 3. Sales broker
    sales_broker = User(
        telegram_id=222001,
        language="uz",
        first_name="SalesBroker",
        phone="+998902220001",
        consent_accepted_at=datetime.now(UTC),
    )
    # 4. Rental broker
    rental_broker = User(
        telegram_id=222002,
        language="uz",
        first_name="RentalBroker",
        phone="+998902220002",
        consent_accepted_at=datetime.now(UTC),
    )
    # 5. Head broker
    head_broker = User(
        telegram_id=222003,
        language="uz",
        first_name="HeadBroker",
        phone="+998902220003",
        consent_accepted_at=datetime.now(UTC),
    )
    # 6. Regular buyer
    regular_buyer = User(
        telegram_id=333001,
        language="uz",
        first_name="BuyerOnly",
        phone="+998903330001",
        consent_accepted_at=datetime.now(UTC),
    )

    db_session.add_all(
        [customer, other_customer, sales_broker, rental_broker, head_broker, regular_buyer]
    )
    await db_session.flush()

    # Assign roles
    await role_repo.assign_role(db_session, customer.id, "buyer")
    await role_repo.assign_role(db_session, other_customer.id, "buyer")
    await role_repo.assign_role(db_session, sales_broker.id, "sales_broker")
    await role_repo.assign_role(db_session, rental_broker.id, "rental_broker")
    await role_repo.assign_role(db_session, head_broker.id, "head_broker")
    await role_repo.assign_role(db_session, regular_buyer.id, "buyer")

    # Properties
    prop_sale_approved = Property(
        owner_user_id=customer.id,
        listing_type="sale",
        property_type="apartment",
        title="Approved Sale Apartment",
        region="Toshkent",
        district="Yunusobod",
        address="Amir Temur ko‘chasi, 1",
        rooms=3,
        total_area=80.0,
        condition="euro",
        cadastre_status="available",
        price=100000,
        currency="USD",
        status="approved",
    )
    prop_rent_approved = Property(
        owner_user_id=customer.id,
        listing_type="rent",
        property_type="apartment",
        title="Approved Rent Apartment",
        region="Toshkent",
        district="Mirzo Ulug‘bek",
        address="Buyuk Ipak Yo‘li, 10",
        rooms=2,
        total_area=60.0,
        condition="euro",
        cadastre_status="available",
        price=500,
        currency="USD",
        status="approved",
    )
    prop_draft = Property(
        owner_user_id=customer.id,
        listing_type="sale",
        property_type="house",
        title="Draft House",
        region="Toshkent",
        district="Chilonzor",
        address="Chilonzor 1",
        rooms=4,
        total_area=150.0,
        condition="renovated",
        cadastre_status="available",
        price=120000,
        currency="USD",
        status="draft",
    )
    prop_sold = Property(
        owner_user_id=customer.id,
        listing_type="sale",
        property_type="apartment",
        title="Sold Apartment",
        region="Toshkent",
        district="Yunusobod",
        address="Yunusobod 4",
        rooms=1,
        total_area=40.0,
        condition="rough_finish",
        cadastre_status="available",
        price=50000,
        currency="USD",
        status="sold",
    )

    db_session.add_all([prop_sale_approved, prop_rent_approved, prop_draft, prop_sold])
    await db_session.flush()

    return {
        "customer_id": customer.id,
        "other_customer_id": other_customer.id,
        "sales_broker_id": sales_broker.id,
        "rental_broker_id": rental_broker.id,
        "head_broker_id": head_broker.id,
        "regular_buyer_id": regular_buyer.id,
        "prop_sale_approved_id": prop_sale_approved.id,
        "prop_rent_approved_id": prop_rent_approved.id,
        "prop_draft_id": prop_draft.id,
        "prop_sold_id": prop_sold.id,
    }


@pytest.mark.asyncio
async def test_create_viewing_request_success(
    db_session: AsyncSession, seeded_entities: dict[str, int]
) -> None:
    """Verify customer can create a viewing request for an approved property."""
    service = ViewingRequestService()
    tomorrow = datetime.now(UTC).date() + timedelta(days=1)

    req = await service.create_viewing_request(
        db_session,
        customer_user_id=seeded_entities["customer_id"],
        property_id=seeded_entities["prop_sale_approved_id"],
        preferred_date=tomorrow,
        preferred_time="15:00",
        customer_comment="Kechki payt qulayroq",
    )

    assert req.id is not None
    assert req.status == "pending"
    assert req.request_type == "viewing"
    assert req.preferred_date == tomorrow
    assert req.preferred_time == "15:00"
    assert req.customer_comment == "Kechki payt qulayroq"
    assert req.broker_user_id is None


@pytest.mark.asyncio
async def test_create_broker_contact_request_success(
    db_session: AsyncSession, seeded_entities: dict[str, int]
) -> None:
    """Verify customer can create a broker contact request."""
    service = ViewingRequestService()

    req = await service.create_broker_contact_request(
        db_session,
        customer_user_id=seeded_entities["customer_id"],
        property_id=seeded_entities["prop_sale_approved_id"],
        customer_comment="Ipoteka bo‘yicha savol bor",
    )

    assert req.id is not None
    assert req.status == "pending"
    assert req.request_type == "broker_contact"
    assert req.preferred_date is None
    assert req.preferred_time is None
    assert req.customer_comment == "Ipoteka bo‘yicha savol bor"


@pytest.mark.asyncio
async def test_viewing_eligibility_rejects_unapproved_property(
    db_session: AsyncSession, seeded_entities: dict[str, int]
) -> None:
    """Verify request is rejected if property is draft or sold."""
    service = ViewingRequestService()
    future = datetime.now(UTC).date() + timedelta(days=2)

    # 1. Draft
    with pytest.raises(PropertyUnavailableError):
        await service.create_viewing_request(
            db_session,
            customer_user_id=seeded_entities["customer_id"],
            property_id=seeded_entities["prop_draft_id"],
            preferred_date=future,
            preferred_time="11:00",
        )

    # 2. Sold
    with pytest.raises(PropertyUnavailableError):
        await service.create_viewing_request(
            db_session,
            customer_user_id=seeded_entities["customer_id"],
            property_id=seeded_entities["prop_sold_id"],
            preferred_date=future,
            preferred_time="11:00",
        )


@pytest.mark.asyncio
async def test_date_validation_rejects_past_date(
    db_session: AsyncSession, seeded_entities: dict[str, int]
) -> None:
    """Verify date cannot be in the past."""
    service = ViewingRequestService()
    yesterday = datetime.now(UTC).date() - timedelta(days=1)

    with pytest.raises(ViewingValidationError):
        await service.create_viewing_request(
            db_session,
            customer_user_id=seeded_entities["customer_id"],
            property_id=seeded_entities["prop_sale_approved_id"],
            preferred_date=yesterday,
            preferred_time="12:00",
        )


@pytest.mark.asyncio
async def test_duplicate_active_viewing_prevented(
    db_session: AsyncSession, seeded_entities: dict[str, int]
) -> None:
    """Verify identical active viewing request raises DuplicateViewingRequestError."""
    service = ViewingRequestService()
    target_date = datetime.now(UTC).date() + timedelta(days=3)

    await service.create_viewing_request(
        db_session,
        customer_user_id=seeded_entities["customer_id"],
        property_id=seeded_entities["prop_sale_approved_id"],
        preferred_date=target_date,
        preferred_time="14:00",
    )

    with pytest.raises(DuplicateViewingRequestError):
        await service.create_viewing_request(
            db_session,
            customer_user_id=seeded_entities["customer_id"],
            property_id=seeded_entities["prop_sale_approved_id"],
            preferred_date=target_date,
            preferred_time="14:00",
        )


@pytest.mark.asyncio
async def test_duplicate_active_broker_contact_prevented(
    db_session: AsyncSession, seeded_entities: dict[str, int]
) -> None:
    """Verify duplicate active broker_contact raises DuplicateViewingRequestError."""
    service = ViewingRequestService()

    await service.create_broker_contact_request(
        db_session,
        customer_user_id=seeded_entities["customer_id"],
        property_id=seeded_entities["prop_sale_approved_id"],
    )

    with pytest.raises(DuplicateViewingRequestError):
        await service.create_broker_contact_request(
            db_session,
            customer_user_id=seeded_entities["customer_id"],
            property_id=seeded_entities["prop_sale_approved_id"],
        )


@pytest.mark.asyncio
async def test_customer_cancellation_lifecycle(
    db_session: AsyncSession, seeded_entities: dict[str, int]
) -> None:
    """Verify customer can cancel own request, but cannot cancel other customer's request."""
    service = ViewingRequestService()
    target_date = datetime.now(UTC).date() + timedelta(days=2)

    req = await service.create_viewing_request(
        db_session,
        customer_user_id=seeded_entities["customer_id"],
        property_id=seeded_entities["prop_sale_approved_id"],
        preferred_date=target_date,
        preferred_time="10:00",
    )

    # 1. Other customer cannot cancel
    with pytest.raises(ViewingPermissionError):
        await service.cancel_customer_request(
            db_session,
            request_id=req.id,
            customer_user_id=seeded_entities["other_customer_id"],
        )

    # 2. Owner customer can cancel
    cancelled = await service.cancel_customer_request(
        db_session,
        request_id=req.id,
        customer_user_id=seeded_entities["customer_id"],
        reason="Vaqtim o‘zgardi",
    )
    assert cancelled.status == "cancelled"
    assert cancelled.cancelled_at is not None
    assert cancelled.cancellation_reason == "Vaqtim o‘zgardi"

    # 3. Cannot cancel already cancelled request
    with pytest.raises(InvalidViewingTransitionError):
        await service.cancel_customer_request(
            db_session,
            request_id=req.id,
            customer_user_id=seeded_entities["customer_id"],
        )

    # 4. Now a new request for the same date/time can be submitted
    new_req = await service.create_viewing_request(
        db_session,
        customer_user_id=seeded_entities["customer_id"],
        property_id=seeded_entities["prop_sale_approved_id"],
        preferred_date=target_date,
        preferred_time="10:00",
    )
    assert new_req.id != req.id
    assert new_req.status == "pending"


@pytest.mark.asyncio
async def test_broker_rbac_and_claiming(
    db_session: AsyncSession, seeded_entities: dict[str, int]
) -> None:
    """Verify broker role boundaries on claiming sale vs rent properties."""
    service = ViewingRequestService()
    target_date = datetime.now(UTC).date() + timedelta(days=2)

    # Create sale request
    sale_req = await service.create_viewing_request(
        db_session,
        customer_user_id=seeded_entities["customer_id"],
        property_id=seeded_entities["prop_sale_approved_id"],
        preferred_date=target_date,
        preferred_time="16:00",
    )

    # Create rent request
    rent_req = await service.create_viewing_request(
        db_session,
        customer_user_id=seeded_entities["customer_id"],
        property_id=seeded_entities["prop_rent_approved_id"],
        preferred_date=target_date,
        preferred_time="17:00",
    )

    # 1. Regular buyer cannot list or claim
    with pytest.raises(ViewingPermissionError):
        await service.list_broker_requests(db_session, seeded_entities["regular_buyer_id"])

    with pytest.raises(ViewingPermissionError):
        await service.claim_request(
            db_session,
            request_id=sale_req.id,
            broker_user_id=seeded_entities["regular_buyer_id"],
        )

    # 2. Sales broker cannot claim rent request
    with pytest.raises(ViewingPermissionError):
        await service.claim_request(
            db_session,
            request_id=rent_req.id,
            broker_user_id=seeded_entities["sales_broker_id"],
        )

    # 3. Rental broker cannot claim sale request
    with pytest.raises(ViewingPermissionError):
        await service.claim_request(
            db_session,
            request_id=sale_req.id,
            broker_user_id=seeded_entities["rental_broker_id"],
        )

    # 4. Sales broker can claim sale request
    claimed_sale = await service.claim_request(
        db_session,
        request_id=sale_req.id,
        broker_user_id=seeded_entities["sales_broker_id"],
    )
    assert claimed_sale.status == "assigned"
    assert claimed_sale.broker_user_id == seeded_entities["sales_broker_id"]

    # 5. Head broker can claim rent request
    claimed_rent = await service.claim_request(
        db_session,
        request_id=rent_req.id,
        broker_user_id=seeded_entities["head_broker_id"],
    )
    assert claimed_rent.status == "assigned"
    assert claimed_rent.broker_user_id == seeded_entities["head_broker_id"]


@pytest.mark.asyncio
async def test_broker_accept_reject_and_complete_lifecycle(
    db_session: AsyncSession, seeded_entities: dict[str, int]
) -> None:
    """Test full broker lifecycle: pending -> assigned -> accepted -> completed."""
    service = ViewingRequestService()
    target_date = datetime.now(UTC).date() + timedelta(days=4)

    req = await service.create_viewing_request(
        db_session,
        customer_user_id=seeded_entities["customer_id"],
        property_id=seeded_entities["prop_sale_approved_id"],
        preferred_date=target_date,
        preferred_time="11:00",
    )

    # Claim
    await service.claim_request(
        db_session,
        request_id=req.id,
        broker_user_id=seeded_entities["sales_broker_id"],
    )

    # Accept
    accepted = await service.accept_request(
        db_session,
        request_id=req.id,
        broker_user_id=seeded_entities["sales_broker_id"],
    )
    assert accepted.status == "accepted"
    assert accepted.accepted_at is not None

    # Cannot reject after accepted
    with pytest.raises(InvalidViewingTransitionError):
        await service.reject_request(
            db_session,
            request_id=req.id,
            broker_user_id=seeded_entities["sales_broker_id"],
            reason="Kech qoldingiz",
        )

    # Complete with invalid outcome rejected
    with pytest.raises(ViewingValidationError):
        await service.complete_request(
            db_session,
            request_id=req.id,
            broker_user_id=seeded_entities["sales_broker_id"],
            outcome="invalid_outcome",
        )

    # Complete with valid outcome
    completed = await service.complete_request(
        db_session,
        request_id=req.id,
        broker_user_id=seeded_entities["sales_broker_id"],
        outcome="interested",
    )
    assert completed.status == "completed"
    assert completed.completed_at is not None
    assert completed.outcome == "interested"

    # Terminal state cannot be re-accepted
    with pytest.raises(InvalidViewingTransitionError):
        await service.accept_request(
            db_session,
            request_id=req.id,
            broker_user_id=seeded_entities["sales_broker_id"],
        )


@pytest.mark.asyncio
async def test_broker_reject_with_reason(
    db_session: AsyncSession, seeded_entities: dict[str, int]
) -> None:
    """Test broker rejecting a viewing request with a required reason."""
    service = ViewingRequestService()
    target_date = datetime.now(UTC).date() + timedelta(days=5)

    req = await service.create_viewing_request(
        db_session,
        customer_user_id=seeded_entities["customer_id"],
        property_id=seeded_entities["prop_sale_approved_id"],
        preferred_date=target_date,
        preferred_time="15:00",
    )

    # Short/empty reason rejected
    with pytest.raises(ViewingValidationError):
        await service.reject_request(
            db_session,
            request_id=req.id,
            broker_user_id=seeded_entities["sales_broker_id"],
            reason="x",
        )

    # Valid reject
    rejected = await service.reject_request(
        db_session,
        request_id=req.id,
        broker_user_id=seeded_entities["sales_broker_id"],
        reason="Mulk egasi bu vaqtda bo‘sh emas ekan",
    )
    assert rejected.status == "rejected"
    assert rejected.rejected_at is not None
    assert rejected.rejection_reason == "Mulk egasi bu vaqtda bo‘sh emas ekan"


@pytest.mark.asyncio
async def test_accept_fails_if_property_becomes_unavailable(
    db_session: AsyncSession, seeded_entities: dict[str, int]
) -> None:
    """If property was sold before broker accepts, accept must fail
    with PropertyUnavailableError.
    """
    service = ViewingRequestService()
    target_date = datetime.now(UTC).date() + timedelta(days=2)

    req = await service.create_viewing_request(
        db_session,
        customer_user_id=seeded_entities["customer_id"],
        property_id=seeded_entities["prop_sale_approved_id"],
        preferred_date=target_date,
        preferred_time="12:00",
    )

    # Change property status to sold
    from app.repositories.property_repository import PropertyRepository

    prop_repo = PropertyRepository()
    await prop_repo.set_status(db_session, req.property_id, "sold")
    await db_session.flush()

    with pytest.raises(PropertyUnavailableError):
        await service.accept_request(
            db_session,
            request_id=req.id,
            broker_user_id=seeded_entities["sales_broker_id"],
        )
