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
