"""Telegram bot handlers aggregation."""

from app.bot.handlers.appointments import appointments_router
from app.bot.handlers.broker_requests import broker_requests_router
from app.bot.handlers.common import common_router
from app.bot.handlers.favorites import favorites_router
from app.bot.handlers.menu import menu_router
from app.bot.handlers.my_properties import my_properties_router
from app.bot.handlers.property_search import search_router
from app.bot.handlers.property_submission import property_submission_router
from app.bot.handlers.registration import registration_router
from app.bot.handlers.review import review_router
from app.bot.handlers.settings import settings_router
from app.bot.handlers.start import start_router

__all__ = [
    "common_router",
    "start_router",
    "registration_router",
    "property_submission_router",
    "search_router",
    "favorites_router",
    "appointments_router",
    "broker_requests_router",
    "my_properties_router",
    "review_router",
    "settings_router",
    "menu_router",
]
