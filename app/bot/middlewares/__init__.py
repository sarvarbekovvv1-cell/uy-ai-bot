"""Middleware package initialization."""

from app.bot.middlewares.db import DatabaseSessionMiddleware

__all__ = ["DatabaseSessionMiddleware"]
