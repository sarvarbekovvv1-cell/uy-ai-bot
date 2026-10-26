"""Provider abstraction and fake implementation for amoCRM operations."""

from typing import Any, Protocol

from app.integrations.amocrm.client import AmoCRMClient
from app.integrations.amocrm.exceptions import (
    AmoCRMAuthError,
    AmoCRMRateLimitError,
    AmoCRMTemporaryError,
    AmoCRMValidationError,
)
from app.logging import get_logger

logger = get_logger(__name__)


class AmoCRMProviderProtocol(Protocol):
    """Protocol defining CRM operations required by UyAI business synchronization."""

    async def create_or_update_contact(
        self,
        name: str,
        phone: str,
        lang: str | None = None,
    ) -> str:
        """Create or update external CRM contact. Returns external contact ID string."""
        ...

    async def create_lead(
        self,
        title: str,
        status_id: int | None,
        pipeline_id: int | None,
        contact_id: str | None = None,
        price: int = 0,
        responsible_user_id: int | None = None,
        custom_fields: list[dict[str, Any]] | None = None,
    ) -> str:
        """Create external CRM lead linked to contact. Returns external lead ID string."""
        ...

    async def update_lead_stage(
        self,
        external_lead_id: str,
        status_id: int,
        pipeline_id: int | None = None,
    ) -> None:
        """Update stage / status_id of existing external CRM lead."""
        ...

    async def add_lead_note(
        self,
        external_lead_id: str,
        note_text: str,
    ) -> None:
        """Attach note to existing external CRM lead."""
        ...

    async def get_pipeline_statuses(
        self,
        pipeline_id: int | None = None,
    ) -> dict[str, int]:
        """Fetch status mapping dictionary for configured pipeline."""
        ...


class RealAmoCRMProvider:
    """Production provider delegating to AmoCRMClient."""

    def __init__(self, client: AmoCRMClient) -> None:
        self.client = client

    async def create_or_update_contact(
        self,
        name: str,
        phone: str,
        lang: str | None = None,
    ) -> str:
        # Check if contact already exists in amoCRM to reconcile crash windows
        existing_id = await self.client.find_contact_by_phone(phone)
        if existing_id:
            logger.info("Reconciled existing amoCRM contact id=%s for phone=%s", existing_id, phone)
            return existing_id

        # Standard amoCRM phone custom field
        custom_fields: list[dict[str, Any]] = [
            {
                "field_code": "PHONE",
                "values": [{"value": phone, "enum_code": "MOB"}],
            }
        ]
        if lang:
            custom_fields.append(
                {
                    "field_code": "LANGUAGE",
                    "values": [{"value": lang}],
                }
            )

        payload = {
            "name": name,
            "custom_fields_values": custom_fields,
        }
        return await self.client.create_contact(payload)

    async def create_lead(
        self,
        title: str,
        status_id: int | None,
        pipeline_id: int | None,
        contact_id: str | None = None,
        price: int = 0,
        responsible_user_id: int | None = None,
        custom_fields: list[dict[str, Any]] | None = None,
    ) -> str:
        # Check if lead already exists in amoCRM to reconcile crash windows
        existing_id = await self.client.find_lead_by_title(title)
        if existing_id:
            logger.info("Reconciled existing amoCRM lead id=%s for title=%s", existing_id, title)
            return existing_id

        payload: dict[str, Any] = {
            "name": title,
            "price": price,
        }
        if status_id is not None:
            payload["status_id"] = status_id
        if pipeline_id is not None:
            payload["pipeline_id"] = pipeline_id
        if responsible_user_id is not None:
            payload["responsible_user_id"] = responsible_user_id
        if contact_id:
            payload["_embedded"] = {"contacts": [{"id": int(contact_id)}]}
        if custom_fields:
            payload["custom_fields_values"] = custom_fields

        return await self.client.create_lead(payload)

    async def update_lead_stage(
        self,
        external_lead_id: str,
        status_id: int,
        pipeline_id: int | None = None,
    ) -> None:
        payload: dict[str, Any] = {"status_id": status_id}
        if pipeline_id is not None:
            payload["pipeline_id"] = pipeline_id
        await self.client.update_lead(external_lead_id, payload)

    async def add_lead_note(
        self,
        external_lead_id: str,
        note_text: str,
    ) -> None:
        await self.client.add_lead_note(external_lead_id, note_text)

    async def get_pipeline_statuses(
        self,
        pipeline_id: int | None = None,
    ) -> dict[str, int]:
        return await self.client.get_pipeline_statuses(pipeline_id)


class FakeAmoCRMProvider:
    """Deterministic in-memory amoCRM provider for testing.

    Captures sent payloads for data minimization and privacy verification.
    Provides controllable fault simulation (401, 429, 500, timeout, validation errors).
    """

    def __init__(self) -> None:
        self.contacts: dict[str, dict[str, Any]] = {}
        self.leads: dict[str, dict[str, Any]] = {}
        self.notes: list[dict[str, Any]] = []
        self.sent_payloads: list[dict[str, Any]] = []

        self._next_contact_id: int = 1000
        self._next_lead_id: int = 5000

        # Fault injection controls
        self.simulate_401: bool = False
        self.simulate_429: bool = False
        self.simulate_429_retry_after: float = 45.0
        self.simulate_500: bool = False
        self.simulate_timeout: bool = False
        self.simulate_validation_error: bool = False
        self.simulate_crash_on_lead_create: bool = False

    def _check_fault_injection(self, operation: str) -> None:
        if self.simulate_401:
            raise AmoCRMAuthError(f"Simulated 401 Unauthorized during {operation}")
        if self.simulate_429:
            raise AmoCRMRateLimitError(
                f"Simulated 429 Rate Limit during {operation}",
                retry_after=self.simulate_429_retry_after,
            )
        if self.simulate_500:
            raise AmoCRMTemporaryError(f"Simulated 500 Server Error during {operation}")
        if self.simulate_timeout:
            raise AmoCRMTemporaryError(f"Simulated network timeout during {operation}")
        if self.simulate_validation_error:
            raise AmoCRMValidationError(f"Simulated 400 Validation Error during {operation}")

    async def create_or_update_contact(
        self,
        name: str,
        phone: str,
        lang: str | None = None,
    ) -> str:
        self._check_fault_injection("create_or_update_contact")

        self.sent_payloads.append(
            {
                "type": "contact",
                "name": name,
                "phone": phone,
                "lang": lang,
            }
        )

        # Check existing contact by phone (idempotent lookup)
        for cid, contact in self.contacts.items():
            if contact.get("phone") == phone:
                contact["name"] = name
                contact["lang"] = lang
                return cid

        self._next_contact_id += 1
        cid = str(self._next_contact_id)
        self.contacts[cid] = {
            "id": cid,
            "name": name,
            "phone": phone,
            "lang": lang,
        }
        return cid

    async def create_lead(
        self,
        title: str,
        status_id: int | None,
        pipeline_id: int | None,
        contact_id: str | None = None,
        price: int = 0,
        responsible_user_id: int | None = None,
        custom_fields: list[dict[str, Any]] | None = None,
    ) -> str:
        self._check_fault_injection("create_lead")

        payload = {
            "type": "lead",
            "title": title,
            "status_id": status_id,
            "pipeline_id": pipeline_id,
            "contact_id": contact_id,
            "price": price,
            "responsible_user_id": responsible_user_id,
            "custom_fields": custom_fields or [],
        }
        self.sent_payloads.append(payload)

        # Check existing lead by title (crash-window idempotency lookup)
        for lid, lead_data in self.leads.items():
            if lead_data.get("title") == title:
                return lid

        if self.simulate_crash_on_lead_create:
            # Create remote record in provider but simulate worker failure before local DB ack
            self._next_lead_id += 1
            lid = str(self._next_lead_id)
            self.leads[lid] = {
                "id": lid,
                **payload,
            }
            raise AmoCRMTemporaryError("Worker simulated crash after remote creation")

        self._next_lead_id += 1
        lid = str(self._next_lead_id)
        self.leads[lid] = {
            "id": lid,
            **payload,
        }
        return lid

    async def update_lead_stage(
        self,
        external_lead_id: str,
        status_id: int,
        pipeline_id: int | None = None,
    ) -> None:
        self._check_fault_injection("update_lead_stage")

        self.sent_payloads.append(
            {
                "type": "update_stage",
                "external_lead_id": external_lead_id,
                "status_id": status_id,
                "pipeline_id": pipeline_id,
            }
        )

        if external_lead_id in self.leads:
            self.leads[external_lead_id]["status_id"] = status_id
            if pipeline_id is not None:
                self.leads[external_lead_id]["pipeline_id"] = pipeline_id

    async def add_lead_note(
        self,
        external_lead_id: str,
        note_text: str,
    ) -> None:
        self._check_fault_injection("add_lead_note")

        payload = {
            "external_lead_id": external_lead_id,
            "note_text": note_text,
        }
        self.sent_payloads.append(payload)
        self.notes.append(payload)

    async def get_pipeline_statuses(
        self,
        pipeline_id: int | None = None,
    ) -> dict[str, int]:
        self._check_fault_injection("get_pipeline_statuses")
        _ = pipeline_id
        return {
            "new": 10001,
            "contacted": 10002,
            "qualified": 10003,
            "viewing_scheduled": 10004,
            "negotiation": 10005,
            "won": 142,
            "lost": 143,
        }
