"""Unit tests for amoCRM data mapping, phone normalization, and PII protection."""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.config import Settings
from app.integrations.amocrm.mapper import AmoCRMMapper
from app.models.lead import Lead
from app.models.property import Property
from app.models.user import User


@pytest.fixture
def mapper() -> AmoCRMMapper:
    settings = Settings(
        AMOCRM_ENABLED=True,
        AMOCRM_DEFAULT_RESPONSIBLE_USER_ID=99990,
        AMOCRM_STAGE_MAPPING_JSON='{"new": 501, "contacted": 502, "won": 142}',
        AMOCRM_BROKER_MAPPING_JSON='{"10": 8801, "20": 8802}',
    )
    return AmoCRMMapper(settings=settings)


def test_phone_normalization(mapper: AmoCRMMapper) -> None:
    """Test canonical E.164 phone normalization across formats."""
    assert mapper.normalize_phone("90 123 45 67") == "+998901234567"
    assert mapper.normalize_phone("+998 (90) 123-45-67") == "+998901234567"
    assert mapper.normalize_phone("998901234567") == "+998901234567"
    assert mapper.normalize_phone("+14155552671") == "+14155552671"
    assert mapper.normalize_phone("invalid_phone") is None
    assert mapper.normalize_phone("") is None
    assert mapper.normalize_phone(None) is None


def test_contact_name_building(mapper: AmoCRMMapper) -> None:
    """Test safe customer display name construction."""
    user1 = MagicMock(
        spec=User, id=1, full_name="Ali Valiyev", first_name=None, last_name=None, username=None
    )
    assert mapper.build_contact_name(user1) == "Ali Valiyev"

    user2 = MagicMock(
        spec=User, id=2, full_name=None, first_name="Vali", last_name=None, username="valiy"
    )
    assert mapper.build_contact_name(user2) == "Vali"

    user3 = MagicMock(
        spec=User, id=3, full_name=None, first_name=None, last_name=None, username="testuser"
    )
    assert mapper.build_contact_name(user3) == "@testuser"

    user4 = MagicMock(
        spec=User, id=4, full_name=None, first_name=None, last_name=None, username=None
    )
    assert mapper.build_contact_name(user4) == "Mijoz #4"


def test_lead_title_construction_no_phone(mapper: AmoCRMMapper) -> None:
    """Test lead title is deterministic and never includes customer or owner phone."""
    prop = MagicMock(spec=Property, id=12, property_type="apartment", district="Yunusobod")
    lead = MagicMock(spec=Lead, id=456, property=prop)

    title = mapper.build_lead_title(lead)
    assert title == "UyAI #456 — apartment — Yunusobod"
    assert "998" not in title
    assert "+" not in title


def test_property_summary_note_data_minimization(mapper: AmoCRMMapper) -> None:
    """Test property summary context note strictly excludes owner PII."""
    prop = MagicMock(
        spec=Property,
        id=77,
        title="Shinam kvartira",
        property_type="apartment",
        listing_type="sale",
        district="Chilonzor",
        rooms=3,
        area_sqm=Decimal("75.5"),
        price=Decimal("85000"),
        currency="USD",
    )
    lead = MagicMock(
        spec=Lead,
        id=99,
        property=prop,
        source="broker_contact",
        source_request=None,
    )

    note = mapper.build_property_summary_note(lead)

    # Must contain public property specs
    assert "Mulk ID: #77" in note
    assert "Shinam kvartira" in note
    assert "apartment (sale)" in note
    assert "Chilonzor" in note
    assert "3" in note
    assert "85,000 USD" in note
    assert "broker_contact" in note

    # Must NOT contain private owner fields
    assert "owner" not in note.lower()
    assert "cadastre" not in note.lower()


def test_stage_and_broker_mapping(mapper: AmoCRMMapper) -> None:
    """Test resolution of stages and responsible brokers from settings."""
    # Configured stages
    assert mapper.resolve_status_id("new") == 501
    assert mapper.resolve_status_id("contacted") == 502
    assert mapper.resolve_status_id("won") == 142

    # Unconfigured intermediate stages return None to prevent corrupting pipeline
    assert mapper.resolve_status_id("qualified") is None
    assert mapper.resolve_status_id("lost") == 143

    # Reverse stage mapping
    assert mapper.resolve_stage_from_status_id(501) == "new"
    assert mapper.resolve_stage_from_status_id(502) == "contacted"
    assert mapper.resolve_stage_from_status_id(142) == "won"
    assert mapper.resolve_stage_from_status_id(143) == "lost"
    assert mapper.resolve_stage_from_status_id(999999) is None

    # Broker mapping
    assert mapper.resolve_responsible_user_id(10) == 8801
    assert mapper.resolve_responsible_user_id(20) == 8802
    # Unmapped broker falls back to default
    assert mapper.resolve_responsible_user_id(99) == 99990
    assert mapper.resolve_responsible_user_id(None) == 99990
