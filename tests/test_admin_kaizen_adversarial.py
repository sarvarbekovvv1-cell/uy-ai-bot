"""Hostile adversarial security and correctness test suite for Phase 12."""

import json
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.config import get_settings
from app.main import app
from app.models.kaizen import KaizenCycle, KaizenRecommendation
from app.models.lead import Lead, LeadFollowUp, LeadNote
from app.models.property import Property
from app.models.role import Role
from app.models.user import User
from app.services.admin_auth_service import AdminAuthService
from app.services.kaizen_analytics_service import KaizenAnalyticsService, KaizenDateRange
from app.services.kaizen_recommendation_service import KaizenRecommendationService
from app.services.kaizen_service import KaizenService


@pytest.fixture(autouse=True)
def setup_admin_db_dependencies(db_session: AsyncSession):
    async def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def setup_adversarial_context(db_session: AsyncSession):
    super_role = Role(name="superadmin", description="Super Admin")
    broker_role = Role(name="sales_broker", description="Sales Broker")
    buyer_role = Role(name="buyer", description="Buyer Role")
    db_session.add_all([super_role, broker_role, buyer_role])
    await db_session.flush()

    admin_user = User(
        telegram_id=90001,
        first_name="Audit",
        last_name="SuperAdmin",
        is_active=True,
    )
    admin_user.roles.append(super_role)
    db_session.add(admin_user)

    buyer_user = User(
        telegram_id=90002,
        first_name="Plain",
        last_name="Customer",
        is_active=True,
    )
    buyer_user.roles.append(buyer_role)
    db_session.add(buyer_user)

    await db_session.flush()

    auth_service = AdminAuthService(get_settings())
    await auth_service.create_or_update_staff_credential(
        db_session, user_id=admin_user.id, username="admin_audit", password="StrongPassword123!"
    )
    await db_session.commit()
    return admin_user, buyer_user


async def _get_auth_headers(
    async_client: AsyncClient, username: str = "admin_audit", password: str = "StrongPassword123!"
) -> dict[str, str]:
    login_resp = await async_client.post(
        "/api/admin/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert login_resp.status_code == 200
    csrf_token = login_resp.json()["csrf_token"]
    return {"x-csrf-token": csrf_token}


# -----------------------------------------------------------------------------
# 1. PDCA Illegal State Transitions & Immutability
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pdca_illegal_state_transitions(
    async_client: AsyncClient, setup_adversarial_context
) -> None:
    admin_user, _ = setup_adversarial_context
    headers = await _get_auth_headers(async_client)

    # Create draft cycle
    create_payload = {
        "title": "Adversarial Transition Test",
        "metric_key": "overall_win_rate",
        "target_value": 25.0,
        "plan_text": "Draft plan",
    }
    create_resp = await async_client.post(
        "/api/admin/v1/kaizen/cycles", json=create_payload, headers=headers
    )
    assert create_resp.status_code == 201
    cycle_id = create_resp.json()["id"]

    # 1. Illegal: draft -> complete directly without check
    resp = await async_client.post(
        f"/api/admin/v1/kaizen/cycles/{cycle_id}/complete",
        json={"outcome": "successful", "act_text": "Completed illegally"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "Invalid PDCA state transition" in resp.json()["detail"]

    # 2. Plan it: draft -> planned
    plan_resp = await async_client.post(
        f"/api/admin/v1/kaizen/cycles/{cycle_id}/plan",
        json={"plan_text": "Approved plan"},
        headers=headers,
    )
    assert plan_resp.status_code == 200
    assert plan_resp.json()["status"] == "planned"

    # 3. Illegal: planned -> checking directly
    resp = await async_client.post(
        f"/api/admin/v1/kaizen/cycles/{cycle_id}/check",
        json={},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "Invalid PDCA state transition" in resp.json()["detail"]

    # 4. Activate: planned -> active
    do_resp = await async_client.post(
        f"/api/admin/v1/kaizen/cycles/{cycle_id}/start",
        json={"do_text": "Executing plan"},
        headers=headers,
    )
    assert do_resp.status_code == 200
    assert do_resp.json()["status"] == "active"

    # 5. Illegal: active -> completed directly without checking
    resp = await async_client.post(
        f"/api/admin/v1/kaizen/cycles/{cycle_id}/complete",
        json={"outcome": "successful", "act_text": "Skipped checking"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "Invalid PDCA state transition" in resp.json()["detail"]

    # 6. Check: active -> checking
    check_resp = await async_client.post(
        f"/api/admin/v1/kaizen/cycles/{cycle_id}/check",
        json={"check_text": "Evaluated results"},
        headers=headers,
    )
    assert check_resp.status_code == 200
    assert check_resp.json()["cycle"]["status"] == "checking"

    # 7. Act: checking -> completed
    act_resp = await async_client.post(
        f"/api/admin/v1/kaizen/cycles/{cycle_id}/complete",
        json={"outcome": "successful", "act_text": "Fully completed"},
        headers=headers,
    )
    assert act_resp.status_code == 200
    assert act_resp.json()["status"] == "completed"

    # 8. Illegal: completed cycle cannot be cancelled
    cancel_resp = await async_client.post(
        f"/api/admin/v1/kaizen/cycles/{cycle_id}/cancel",
        json={"reason": "Cannot cancel completed"},
        headers=headers,
    )
    assert cancel_resp.status_code == 400
    assert "Invalid PDCA state transition" in cancel_resp.json()["detail"]


# -----------------------------------------------------------------------------
# 2. Baseline Snapshot Immutability (No Arbitrary Mutation)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_baseline_snapshot_immutability(
    async_client: AsyncClient, setup_adversarial_context
) -> None:
    _admin, _ = setup_adversarial_context
    headers = await _get_auth_headers(async_client)

    create_resp = await async_client.post(
        "/api/admin/v1/kaizen/cycles",
        json={
            "title": "Immutability Test",
            "metric_key": "overall_win_rate",
            "target_value": 30.0,
        },
        headers=headers,
    )
    cycle = create_resp.json()
    orig_snapshot = cycle["baseline_snapshot_json"]
    assert orig_snapshot is not None

    # Verify PUT is disallowed by design (405 Method Not Allowed)
    update_resp = await async_client.put(
        f"/api/admin/v1/kaizen/cycles/{cycle['id']}",
        json={"title": "New Title", "plan_text": "Updated plan"},
        headers=headers,
    )
    assert update_resp.status_code == 405

    # Refetch and verify baseline snapshot remains unchanged
    get_resp = await async_client.get(f"/api/admin/v1/kaizen/cycles/{cycle['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["baseline_snapshot_json"] == orig_snapshot


# -----------------------------------------------------------------------------
# 3. Progress Math (Lower is Better & Target == Baseline)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_progress_math_lower_is_better_and_target_equal_baseline(
    db_session: AsyncSession, setup_adversarial_context
) -> None:
    admin_user, _ = setup_adversarial_context

    # Case A: Lower-is-better metric (median_response_time)
    cycle_a = KaizenCycle(
        title="Speed up response time",
        metric_key="median_response_time",
        baseline_value=Decimal("40.0"),
        target_value=Decimal("20.0"),
        status="active",
        created_by_user_id=admin_user.id,
    )
    db_session.add(cycle_a)
    await db_session.flush()

    # If observed=30 (halfway between 40 and 20) -> progress should be 50%
    with patch.object(
        KaizenAnalyticsService,
        "get_metric_snapshot",
        new=AsyncMock(return_value={"value": 30.0, "unit": "minutes"}),
    ):
        result_a = await KaizenService.check_cycle(db_session, cycle_a.id, admin_user.id)
        assert result_a["suggested_outcome"] == "partially_successful"

    # Case B: Target == Baseline edge case (division by zero protection)
    cycle_b = KaizenCycle(
        title="Maintain zero failed events",
        metric_key="crm_failed_events",
        baseline_value=Decimal("0.0"),
        target_value=Decimal("0.0"),
        status="active",
        created_by_user_id=admin_user.id,
    )
    db_session.add(cycle_b)
    await db_session.flush()

    with patch.object(
        KaizenAnalyticsService,
        "get_metric_snapshot",
        new=AsyncMock(return_value={"value": 0.0, "unit": "count"}),
    ):
        result_b = await KaizenService.check_cycle(db_session, cycle_b.id, admin_user.id)
        assert result_b["suggested_outcome"] == "successful"


# -----------------------------------------------------------------------------
# 4. Property Media Upload & Streaming Preview Adversarial Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_property_media_upload_adversarial(
    async_client: AsyncClient, setup_adversarial_context
) -> None:
    _admin, _ = setup_adversarial_context
    headers = await _get_auth_headers(async_client)

    # 1. Empty file (0 bytes) rejected 400
    resp = await async_client.post(
        "/api/admin/v1/properties/upload-media",
        content=b"",
        headers={**headers, "content-type": "image/jpeg"},
    )
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()

    # 2. Mismatched magic bytes (declared image/jpeg, but content is text/html)
    resp = await async_client.post(
        "/api/admin/v1/properties/upload-media",
        content=b"<script>alert(1)</script>",
        headers={**headers, "content-type": "image/jpeg"},
    )
    assert resp.status_code == 400
    assert "magic bytes" in resp.json()["detail"].lower()

    # 3. Valid JPEG upload
    valid_jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb"
    resp = await async_client.post(
        "/api/admin/v1/properties/upload-media",
        content=valid_jpeg_bytes,
        headers={**headers, "content-type": "image/jpeg"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "media_unique_id" in data
    media_uid = data["media_unique_id"]

    # 4. Admin preview endpoint streaming
    prev_resp = await async_client.get(f"/api/admin/v1/properties/media/{media_uid}")
    assert prev_resp.status_code == 200
    assert prev_resp.headers["content-type"] == "image/jpeg"
    assert prev_resp.headers["x-content-type-options"] == "nosniff"
    assert prev_resp.content == valid_jpeg_bytes

    # 5. Mini App preview endpoint streaming
    mini_prev_resp = await async_client.get(f"/api/miniapp/v1/properties/media/{media_uid}")
    assert mini_prev_resp.status_code == 200
    assert mini_prev_resp.headers["content-type"] == "image/jpeg"
    assert mini_prev_resp.headers["x-content-type-options"] == "nosniff"
    assert mini_prev_resp.content == valid_jpeg_bytes

    # 6. Non-existent media preview returns 404
    missing_resp = await async_client.get("/api/admin/v1/properties/media/nonexistent_uid_12345")
    assert missing_resp.status_code == 404

    # 7. Path traversal rejected
    traversal_resp = await async_client.get("/api/admin/v1/properties/media/..%2F..%2Fetc%2Fpasswd")
    assert traversal_resp.status_code in (400, 404)


# -----------------------------------------------------------------------------
# 5. Admin Property Creation Owner Validation & Extra Forbidden
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_property_create_owner_validation(
    async_client: AsyncClient, setup_adversarial_context
) -> None:
    admin_user, buyer_user = setup_adversarial_context
    headers = await _get_auth_headers(async_client)

    # 1. Valid customer owner_user_id
    payload_valid = {
        "title": "Customer Owned Property",
        "property_type": "apartment",
        "listing_type": "sale",
        "region": "Toshkent",
        "district": "Chilonzor",
        "address": "Bunyodkor 10",
        "rooms": 2,
        "total_area": 55.0,
        "price": 60000.0,
        "currency": "USD",
        "condition": "renovated",
        "owner_user_id": buyer_user.id,
    }
    resp = await async_client.post(
        "/api/admin/v1/properties", json=payload_valid, headers=headers
    )
    assert resp.status_code == 201
    assert resp.json()["owner"]["id"] == buyer_user.id

    # 2. Non-existent owner_user_id -> 400
    payload_invalid = {**payload_valid, "owner_user_id": 9999999}
    resp = await async_client.post(
        "/api/admin/v1/properties", json=payload_invalid, headers=headers
    )
    assert resp.status_code == 400
    assert "not exist" in resp.json()["detail"].lower()

    # 3. Omitted owner_user_id -> defaults to staff user
    payload_omitted = {k: v for k, v in payload_valid.items() if k != "owner_user_id"}
    resp = await async_client.post(
        "/api/admin/v1/properties", json=payload_omitted, headers=headers
    )
    assert resp.status_code == 201
    assert resp.json()["owner"]["id"] == admin_user.id

    # 4. Extra fields rejected (extra="forbid") -> 422
    payload_extra = {**payload_valid, "malicious_injection_field": "exploit"}
    resp = await async_client.post(
        "/api/admin/v1/properties", json=payload_extra, headers=headers
    )
    assert resp.status_code == 422


# -----------------------------------------------------------------------------
# 6. Orphan Media Cleanup Sweep
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_orphan_media_cleanup(db_session: AsyncSession) -> None:
    cache_dir = os.path.join(os.getcwd(), ".cache", "media")
    os.makedirs(cache_dir, exist_ok=True)

    orphan_file = os.path.join(cache_dir, "admin_media_temp_orphan_test.jpg")
    with open(orphan_file, "wb") as f:
        f.write(b"\xff\xd8\xff\xe0_test_data")

    # Run cleanup with max_age_hours=0 to sweep immediately
    cleaned = await KaizenService.cleanup_orphan_media(db_session, max_age_hours=0)
    assert cleaned >= 1
    assert not os.path.exists(orphan_file)


# -----------------------------------------------------------------------------
# 7. Migration 008 SQLite BigInt Autoincrement PK
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_migration_008_sqlite_bigint_autoincrement(
    db_session: AsyncSession, setup_adversarial_context
) -> None:
    admin_user, _ = setup_adversarial_context

    cycle = KaizenCycle(
        title="Autoincrement Test",
        metric_key="overall_win_rate",
        created_by_user_id=admin_user.id,
    )
    db_session.add(cycle)
    await db_session.flush()
    assert cycle.id is not None
    assert isinstance(cycle.id, int)
    assert cycle.id > 0

    rec = KaizenRecommendation(
        metric_key="overall_win_rate",
        category="lead_conversion",
        title="Autoincrement Rec Test",
        description="Testing autoincrement PK",
        evidence_json="{}",
        recommendation_text="Ensure PK assigns correctly",
    )
    db_session.add(rec)
    await db_session.flush()
    assert rec.id is not None
    assert isinstance(rec.id, int)
    assert rec.id > 0


# -----------------------------------------------------------------------------
# 8. CSRF, Session and RBAC Attack Matrix
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_csrf_and_rbac_kaizen_adversarial(
    async_client: AsyncClient, setup_adversarial_context
) -> None:
    _admin, _buyer = setup_adversarial_context
    # 1. Anonymous access -> 401
    resp = await async_client.get("/api/admin/v1/kaizen/overview")
    assert resp.status_code == 401

    # 2. Anonymous post cycle -> 401
    resp = await async_client.post(
        "/api/admin/v1/kaizen/cycles",
        json={"title": "Hacked", "metric_key": "overall_win_rate"},
    )
    assert resp.status_code == 401

    # 3. Log in as superadmin
    login_resp = await async_client.post(
        "/api/admin/v1/auth/login",
        json={"username": "admin_audit", "password": "StrongPassword123!"},
    )
    assert login_resp.status_code == 200

    # 4. Invalid CSRF token on POST -> 403
    resp = await async_client.post(
        "/api/admin/v1/kaizen/cycles",
        json={"title": "CSRF Attack", "metric_key": "overall_win_rate"},
        headers={"x-csrf-token": "forged_invalid_csrf_token"},
    )
    assert resp.status_code == 403


# -----------------------------------------------------------------------------
# 9. Kaizen Analytics: Cumulative Funnel, Earliest Contact, & P90
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_kaizen_analytics_adversarial_cumulative_and_p90(
    db_session: AsyncSession, setup_adversarial_context
) -> None:
    admin_user, buyer_user = setup_adversarial_context

    prop = Property(
        owner_user_id=buyer_user.id,
        title="Analytics Test Property",
        property_type="apartment",
        listing_type="sale",
        region="Toshkent",
        district="Mirzo Ulugbek",
        address="Navoi 12",
        rooms=2,
        total_area=Decimal("60.0"),
        price=Decimal("70000"),
        currency="USD",
        condition="renovated",
        status="approved",
    )
    db_session.add(prop)
    await db_session.flush()

    now = datetime.now(UTC)
    t0 = now - timedelta(hours=5)

    # Lead 1: Contacted via lead.contacted_at, reached viewing, then lost
    lead_lost = Lead(
        customer_user_id=buyer_user.id,
        property_id=prop.id,
        source="broker_contact",
        stage="lost",
        created_at=t0,
        contacted_at=t0 + timedelta(minutes=15),
        viewing_at=t0 + timedelta(hours=1),
    )
    db_session.add(lead_lost)

    # Lead 2: Contacted via LeadNote created_at
    lead_note_contact = Lead(
        customer_user_id=buyer_user.id,
        property_id=prop.id,
        source="manual",
        stage="contacted",
        created_at=t0 + timedelta(minutes=30),
    )
    db_session.add(lead_note_contact)
    await db_session.flush()

    note = LeadNote(
        lead_id=lead_note_contact.id,
        author_user_id=admin_user.id,
        text="Called client",
        created_at=t0 + timedelta(minutes=45),
    )
    db_session.add(note)

    # Lead 3: Contacted via completed LeadFollowUp
    lead_fu_contact = Lead(
        customer_user_id=buyer_user.id,
        property_id=prop.id,
        source="viewing",
        stage="negotiation",
        created_at=t0 + timedelta(hours=1),
    )
    db_session.add(lead_fu_contact)
    await db_session.flush()

    fu = LeadFollowUp(
        lead_id=lead_fu_contact.id,
        broker_user_id=admin_user.id,
        task_type="call",
        due_at=now + timedelta(days=2),  # Future due_at MUST be ignored
        status="completed",
        completed_at=t0 + timedelta(hours=1, minutes=20),
    )
    db_session.add(fu)

    await db_session.commit()

    date_range = KaizenDateRange(days=7)
    overview = await KaizenAnalyticsService.get_kpi_overview(db_session, date_range)

    # Lead 1 reached contacted and viewing even though currently in stage "lost"
    assert overview["lead_funnel"]["reached_contacted"] >= 3
    assert overview["lead_funnel"]["reached_viewing"] >= 2

    # Response time sample size
    resp_stats = overview["response_time"]
    assert resp_stats["sample_size"] >= 3
    assert resp_stats["p90_seconds"] is not None
    assert resp_stats["median_seconds"] is not None


# -----------------------------------------------------------------------------
# 10. Kaizen Recommendations: Deduplication & Context Sanitization
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_kaizen_recommendations_deduplication_and_sanitization(
    db_session: AsyncSession, setup_adversarial_context
) -> None:
    _admin, _ = setup_adversarial_context

    # 1. Existing new recommendation in database
    existing_rec = KaizenRecommendation(
        metric_key="overall_win_rate",
        category="lead_conversion",
        title="Existing Recommendation Title",
        description="Active rec",
        evidence_json="{}",
        recommendation_text="Step 1",
        status="new",
    )
    db_session.add(existing_rec)
    await db_session.commit()

    # 2. Mock overview with sensitive broker and customer data
    mock_overview = {
        "date_from": "2026-09-26",
        "date_to": "2026-10-26",
        "lead_funnel": {
            "total_leads": 10,
            "won_leads": 1,
            "lost_leads": 9,
            "conversion_rates": {"overall_win_rate": 10.0},
        },
        "response_time": {"median_minutes": 45.0, "sample_size": 10},
        "viewings": {"completion_rate": 50.0, "total_viewings": 5, "cancelled": 2},
        "properties": {"moderation_backlog": 2},
        "brokers": {
            "total_active_brokers": 2,
            "total_overdue_followups": 3,
            "brokers": [
                {
                    "broker_id": 999,
                    "name": "Secret Broker Real Name",
                    "username": "secret_broker_username",
                    "assigned_leads": 5,
                    "won_leads": 1,
                }
            ],
        },
        "crm_health": {"failed_events": 0, "permanent_failed_events": 0},
    }

    # Verify Gemini context sanitization strips PII
    with patch(
        "app.services.kaizen_recommendation_service.GeminiLLMProvider"
    ) as mock_provider_class:
        mock_provider = MagicMock()
        mock_provider.model_name = "gemini-2.5-flash"
        mock_provider.client.aio.models.generate_content = AsyncMock(
            return_value=MagicMock(
                text=json.dumps(
                    {
                        "recommendations": [
                            {
                                "metric_key": "overall_win_rate",
                                "category": "lead_conversion",
                                "title": "Existing Recommendation Title",  # duplicate title
                                "description": "Duplicate test",
                                "recommendation_text": "Do something",
                                "confidence": 0.9,
                                "severity": "warning",
                            },
                            {
                                "metric_key": "invalid_fake_metric",  # invalid metric key
                                "category": "lead_conversion",
                                "title": "Fake metric rec",
                                "description": "Test",
                                "recommendation_text": "Test",
                                "confidence": 0.8,
                                "severity": "info",
                            },
                        ]
                    }
                )
            )
        )
        mock_provider_class.return_value = mock_provider

        recs = await KaizenRecommendationService.generate_gemini_insights(mock_overview)

        # Ensure call contents did NOT include secret broker name or username
        call_args = mock_provider.client.aio.models.generate_content.call_args
        prompt_sent = call_args.kwargs.get("contents", "")
        assert "Secret Broker Real Name" not in prompt_sent
        assert "secret_broker_username" not in prompt_sent

        # Ensure invalid metric was filtered out
        assert all(r["metric_key"] != "invalid_fake_metric" for r in recs)
