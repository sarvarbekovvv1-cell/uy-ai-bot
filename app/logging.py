"""Centralized logging configuration with sensitive data sanitization."""

import logging
import re
import sys

from app.config import get_settings

# Regex patterns to sanitize sensitive credentials and personal data
SENSITIVE_PATTERNS = [
    (re.compile(r"bot\d+:[A-Za-z0-9_-]+", re.IGNORECASE), "bot[REDACTED_TOKEN]"),
    (re.compile(r"(password=)['\"][^'\"]*['\"]", re.IGNORECASE), r"\1'[REDACTED]'"),
    (
        re.compile(r"://([^:]+):([^@]+)@", re.IGNORECASE),
        r"://\1:[REDACTED]@",
    ),  # Redact DB URI passwords
    (
        re.compile(r"(bearer\s+)[A-Za-z0-9._-]+", re.IGNORECASE),
        r"\1[REDACTED]",
    ),  # Auth bearer tokens
    (
        re.compile(r"(?:AIzaSy|AQ\.)[A-Za-z0-9_-]{30,}", re.IGNORECASE),
        "[REDACTED_GEMINI_KEY]",
    ),  # Redact Gemini and Google API keys
    (
        re.compile(
            r"(?:api[-_]?key|gemini[-_]?key)\s*[:=]\s*['\"]?([A-Za-z0-9._-]+)['\"]?",
            re.IGNORECASE,
        ),
        "api_key='[REDACTED_KEY]'",
    ),  # Redact explicit API key parameters
    (
        re.compile(r"(\+?998\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2})"),
        "[REDACTED_PHONE]",
    ),  # Redact Uzbekistan phone numbers
    (
        re.compile(r"(phone(?:_number)?\s*[:=]\s*)['\"]?(\+?\d{9,15})['\"]?", re.IGNORECASE),
        r"\1'[REDACTED_PHONE]'",
    ),  # Redact labeled phone arguments
]


class SensitiveDataFilter(logging.Filter):
    """Logging filter that scrubs sensitive tokens, passwords, and secrets from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, replacement in SENSITIVE_PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)

        if record.args:
            if isinstance(record.args, dict):
                sanitized_args = {}
                for k, v in record.args.items():
                    if isinstance(v, str):
                        for pattern, replacement in SENSITIVE_PATTERNS:
                            v = pattern.sub(replacement, v)
                    sanitized_args[k] = v
                record.args = sanitized_args
            elif isinstance(record.args, tuple):
                sanitized_tuple = []
                for item in record.args:
                    if isinstance(item, str):
                        for pattern, replacement in SENSITIVE_PATTERNS:
                            item = pattern.sub(replacement, item)
                    sanitized_tuple.append(item)
                record.args = tuple(sanitized_tuple)

        return True


def setup_logging(log_level: str | None = None) -> None:
    """Configure structured logging for the application."""
    if log_level is None:
        settings = get_settings()
        log_level = settings.log_level

    level = getattr(logging, log_level.upper(), logging.INFO)

    log_format = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    formatter = logging.Formatter(fmt=log_format, datefmt="%Y-%m-%d %H:%M:%S")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(SensitiveDataFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicate log records
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Reduce verbosity of noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger with the sensitive data filter applied."""
    logger = logging.getLogger(name)
    return logger
