"""Cryptographic verification of Telegram Mini App initData."""

import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import parse_qsl

from app.core.exceptions import (
    TelegramAuthExpiredError,
    TelegramAuthInvalidSignatureError,
    TelegramAuthMalformedError,
)
from app.logging import get_logger

logger = get_logger(__name__)


def verify_telegram_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = 86400,
) -> dict[str, Any]:
    """Cryptographically verify Telegram Mini App initData signature using bot token.

    CRITICAL SECURITY SPECIFICATION:
    1. Extracts 'hash' from initData query string.
    2. Builds data-check-string from remaining key-value pairs sorted alphabetically.
    3. Derives secret key using HMAC-SHA256(b"WebAppData", bot_token).
    4. Computes HMAC-SHA256(secret_key, data_check_string).
    5. Uses hmac.compare_digest for timing-safe signature comparison.
    6. Validates 'auth_date' freshness against max_age_seconds and clock skew.
    7. Parses and returns the authenticated user payload.
    """
    if not init_data or not isinstance(init_data, str):
        raise TelegramAuthMalformedError("Empty or invalid initData string.")

    if not bot_token:
        raise TelegramAuthInvalidSignatureError("Bot token is not configured.")

    try:
        parsed_items = parse_qsl(init_data, keep_blank_values=True)
    except Exception as e:
        raise TelegramAuthMalformedError(f"Failed to parse initData query string: {e}") from e

    data_dict: dict[str, str] = {}
    provided_hash: str | None = None

    for k, v in parsed_items:
        if k == "hash":
            provided_hash = v
        else:
            data_dict[k] = v

    if not provided_hash:
        raise TelegramAuthMalformedError("Missing required 'hash' parameter in initData.")

    # Sort remaining key-value pairs alphabetically
    sorted_pairs = sorted(data_dict.items(), key=lambda x: x[0])
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted_pairs)

    # Derive secret key: HMAC-SHA256 with key "WebAppData"
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()

    # Calculate expected signature
    calculated_hash = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    # Timing-safe comparison
    if not hmac.compare_digest(calculated_hash, provided_hash):
        logger.warning("Telegram Mini App initData signature verification failed")
        raise TelegramAuthInvalidSignatureError("Invalid Telegram Mini App signature.")

    # Freshness check
    auth_date_str = data_dict.get("auth_date")
    if not auth_date_str:
        raise TelegramAuthMalformedError("Missing required 'auth_date' parameter in initData.")

    try:
        auth_date = int(auth_date_str)
    except ValueError as val_err:
        msg = "Invalid non-integer 'auth_date' in initData."
        raise TelegramAuthMalformedError(msg) from val_err

    current_time = int(time.time())
    # Reject expired payloads
    if current_time - auth_date > max_age_seconds:
        logger.warning(
            "Telegram initData expired (age=%ds, max=%ds)",
            current_time - auth_date,
            max_age_seconds,
        )
        raise TelegramAuthExpiredError("Telegram authentication data has expired.")

    # Reject future timestamps beyond reasonable clock skew (60s)
    if auth_date > current_time + 60:
        skew = auth_date - current_time
        logger.warning("Telegram initData auth_date is in the future (skew=%ds)", skew)
        raise TelegramAuthExpiredError("Telegram authentication auth_date is in the future.")

    # Extract user dictionary
    user_json = data_dict.get("user")
    if not user_json:
        raise TelegramAuthMalformedError("Missing required 'user' field in initData.")

    try:
        user_data = json.loads(user_json)
    except json.JSONDecodeError as jde:
        raise TelegramAuthMalformedError("Malformed JSON in 'user' field of initData.") from jde

    if not isinstance(user_data, dict) or "id" not in user_data:
        raise TelegramAuthMalformedError("'user' payload must be a JSON object containing an 'id'.")

    return {
        "user": user_data,
        "auth_date": auth_date,
        "query_id": data_dict.get("query_id"),
        "raw_data": data_dict,
    }
