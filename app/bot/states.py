"""Finite State Machine (FSM) state groups for UyAI Telegram bot."""

from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Temporary workflow states for user onboarding and registration."""

    choosing_language = State()
    waiting_consent = State()
    waiting_name = State()
    waiting_phone = State()


class SettingsStates(StatesGroup):
    """Temporary workflow states for user settings."""

    changing_language = State()


class PropertySubmissionStates(StatesGroup):
    """Workflow states for creating a property listing."""

    waiting_property_type = State()
    waiting_region = State()
    waiting_district = State()
    waiting_address = State()
    waiting_location = State()
    waiting_rooms = State()
    waiting_total_area = State()
    waiting_floor = State()
    waiting_total_floors = State()
    waiting_condition = State()
    waiting_furniture = State()
    waiting_cadastre = State()
    waiting_price = State()
    waiting_currency = State()
    waiting_negotiable = State()
    waiting_description = State()
    waiting_photos = State()
    waiting_confirmation = State()


class PropertyReviewStates(StatesGroup):
    """Workflow states for staff property listing review."""

    waiting_rejection_reason = State()


class PropertySearchStates(StatesGroup):
    """Workflow states for customer property discovery and search."""

    choosing_property_type = State()
    waiting_region = State()
    waiting_district = State()
    choosing_rooms = State()
    waiting_min_price = State()
    waiting_max_price = State()
    choosing_currency = State()
    waiting_min_area = State()
    showing_results = State()


class ViewingRequestStates(StatesGroup):
    """Workflow states for scheduling a property viewing."""

    choosing_date = State()
    waiting_custom_date = State()
    choosing_time = State()
    waiting_comment = State()
    confirming = State()


class BrokerViewingStates(StatesGroup):
    """Workflow states for broker managing viewing requests."""

    waiting_rejection_reason = State()


class BrokerCabinetStates(StatesGroup):
    """Workflow states for Broker Cabinet and Lead management."""

    waiting_lost_reason = State()
    waiting_followup_type = State()
    waiting_followup_date = State()
    waiting_followup_note = State()
    waiting_note_text = State()
