"""SQLAlchemy database models for UyAI."""

from app.models.admin_auth import AdminAuditEvent, AdminSession, StaffCredential
from app.models.crm_sync import (
    CRM_EVENT_STATUSES,
    CRM_PROVIDERS,
    CRMEntityLink,
    CRMSyncEvent,
)
from app.models.favorite import Favorite
from app.models.kaizen import (
    KAIZEN_CYCLE_STATUSES,
    KAIZEN_OUTCOMES,
    KAIZEN_RECOMMENDATION_STATUSES,
    KAIZEN_SEVERITIES,
    KaizenCycle,
    KaizenRecommendation,
)
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
from app.models.payment_card_setting import PaymentCardSetting
from app.models.payment_transaction import PaymentTransaction
from app.models.property import (
    CADASTRE_STATUSES,
    LISTING_TYPES,
    PROPERTY_CONDITIONS,
    PROPERTY_STATUSES,
    PROPERTY_TYPES,
    SUPPORTED_CURRENCIES,
    Property,
)
from app.models.property_media import PropertyMedia
from app.models.role import DEFAULT_CUSTOMER_ROLE, SYSTEM_ROLES, Role, UserRole
from app.models.user import User
from app.models.valuation_order import (
    PAYMENT_PROVIDERS,
    VALUATION_PAYMENT_STATUSES,
    VALUATION_STATUSES,
    ValuationOrder,
)
from app.models.viewing_request import (
    REQUEST_STATUSES,
    REQUEST_TYPES,
    VIEWING_OUTCOMES,
    ViewingRequest,
)

__all__ = [
    "User",
    "Role",
    "UserRole",
    "SYSTEM_ROLES",
    "DEFAULT_CUSTOMER_ROLE",
    "Property",
    "PropertyMedia",
    "Favorite",
    "ViewingRequest",
    "Lead",
    "LeadFollowUp",
    "LeadNote",
    "LeadEvent",
    "LEAD_SOURCES",
    "LEAD_STAGES",
    "ACTIVE_LEAD_STAGES",
    "TERMINAL_LEAD_STAGES",
    "FOLLOWUP_TYPES",
    "FOLLOWUP_STATUSES",
    "LOST_REASONS",
    "REQUEST_TYPES",
    "REQUEST_STATUSES",
    "VIEWING_OUTCOMES",
    "LISTING_TYPES",
    "PROPERTY_TYPES",
    "PROPERTY_CONDITIONS",
    "CADASTRE_STATUSES",
    "PROPERTY_STATUSES",
    "SUPPORTED_CURRENCIES",
    "CRMSyncEvent",
    "CRMEntityLink",
    "CRM_EVENT_STATUSES",
    "CRM_PROVIDERS",
    "StaffCredential",
    "AdminSession",
    "AdminAuditEvent",
    "KaizenCycle",
    "KaizenRecommendation",
    "KAIZEN_CYCLE_STATUSES",
    "KAIZEN_OUTCOMES",
    "KAIZEN_RECOMMENDATION_STATUSES",
    "KAIZEN_SEVERITIES",
    "ValuationOrder",
    "PaymentTransaction",
    "PaymentCardSetting",
    "VALUATION_PAYMENT_STATUSES",
    "VALUATION_STATUSES",
    "PAYMENT_PROVIDERS",
]
