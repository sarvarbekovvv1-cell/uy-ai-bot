"""Data mapping and transformation layer between UyAI and amoCRM.

Enforces strict data minimization, canonical phone normalization, and PII protection:
- Never includes customer password, Telegram auth hash, or Gemini chat history.
- Never includes property owner private contact data or phone numbers.
- Uses deterministic human-readable lead names without customer phone numbers.
"""


from app.config import Settings
from app.integrations.amocrm.constants import (
    DEFAULT_STAGE_TO_STATUS,
    DEFAULT_STATUS_TO_STAGE,
)
from app.models.lead import Lead
from app.models.user import User
from app.utils.phone import normalize_phone_number


class AmoCRMMapper:
    """Mapper translating internal UyAI domain objects into amoCRM payloads."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @staticmethod
    def normalize_phone(raw_phone: str | None) -> str | None:
        """Normalize raw phone to standard canonical E.164 (+998...) format."""
        if not raw_phone:
            return None
        return normalize_phone_number(raw_phone)

    @staticmethod
    def build_contact_name(user: User) -> str:
        """Build sanitized customer display name."""
        full = getattr(user, "full_name", None)
        if full and isinstance(full, str) and full.strip():
            return full.strip()
        first = getattr(user, "first_name", None)
        last = getattr(user, "last_name", None)
        name = " ".join(filter(None, [first, last])).strip()
        if not name and getattr(user, "username", None):
            name = f"@{user.username}"
        if not name:
            name = f"Mijoz #{user.id}"
        return name

    @staticmethod
    def build_lead_title(lead: Lead) -> str:
        """Construct deterministic lead name for amoCRM.

        Example: 'UyAI #105 — apartment — Chilonzor'
        Guarantees no customer phone or owner phone in lead title.
        """
        prop_type = lead.property.property_type if lead.property else "Mulk"
        district = lead.property.district if lead.property else "Toshkent"
        return f"UyAI #{lead.id} — {prop_type} — {district}"

    @staticmethod
    def build_property_summary_note(lead: Lead) -> str:
        """Format safe business context note about the property.

        Privacy rule: Strictly excludes property owner private contact data and phone numbers.
        """
        prop = lead.property
        if not prop:
            return f"UyAI Lead #{lead.id}"

        price_str = f"{prop.price:,} {prop.currency}" if prop.price else "Ko‘rsatilmagan"
        area = getattr(prop, "total_area", getattr(prop, "area_sqm", "-"))
        lines = [
            f"📌 Mulk ID: #{prop.id}",
            f"🏷 Sarlavha: {prop.title}",
            f"📋 Turi: {prop.property_type} ({prop.listing_type})",
            f"📍 Tuman: {prop.district or 'Noma’lum'}",
            f"🚪 Xonalar: {prop.rooms or '-'}",
            f"📐 Maydon: {area} m²",
            f"💰 Narx: {price_str}",
            f"🌐 Manba: {lead.source}",
        ]
        if lead.source_request:
            req = lead.source_request
            if req.preferred_date and req.preferred_time:
                lines.append(f"📅 Ko‘rish vaqti: {req.preferred_date} {req.preferred_time}")
            if req.customer_comment:
                lines.append(f"💬 Mijoz izohi: {req.customer_comment}")

        return "\n".join(lines)

    def resolve_status_id(self, stage: str) -> int | None:
        """Map internal Lead stage to amoCRM status_id."""
        configured = self.settings.get_amocrm_stage_mapping()
        if stage in configured:
            return configured[stage]
        return DEFAULT_STAGE_TO_STATUS.get(stage)

    def resolve_responsible_user_id(self, broker_user_id: int | None) -> int | None:
        """Map internal broker user_id to amoCRM responsible_user_id."""
        if broker_user_id is None:
            return self.settings.amocrm_default_responsible_user_id

        configured = self.settings.get_amocrm_broker_mapping()
        if broker_user_id in configured:
            return configured[broker_user_id]

        return self.settings.amocrm_default_responsible_user_id

    def resolve_stage_from_status_id(self, status_id: int) -> str | None:
        """Invert amoCRM status_id to internal Lead stage for webhooks."""
        configured = self.settings.get_amocrm_stage_mapping()
        inverted = {v: k for k, v in configured.items()}
        if status_id in inverted:
            return inverted[status_id]
        return DEFAULT_STATUS_TO_STAGE.get(status_id)
