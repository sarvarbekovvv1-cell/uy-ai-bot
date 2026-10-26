"""Unit tests for Telegram Mini App initData cryptographic verification."""

import hashlib
import hmac
import json
import time
import urllib.parse

import pytest

from app.core.exceptions import (
    TelegramAuthExpiredError,
    TelegramAuthInvalidSignatureError,
    TelegramAuthMalformedError,
)
from app.services.miniapp.auth import verify_telegram_init_data

TEST_BOT_TOKEN = "123456789:mock_telegram_bot_test_token"


def make_init_data(
    bot_token: str,
    user_dict: dict | None,
    auth_date: int | None = None,
    query_id: str = "AAG_test_query",
    start_param: str | None = None,
    tamper_hash: bool = False,
    tamper_data: bool = False,
) -> str:
    """Generate cryptographically valid initData query string for testing."""
    if auth_date is None:
        auth_date = int(time.time())

    data: dict[str, str] = {
        "auth_date": str(auth_date),
        "query_id": query_id,
    }
    if start_param is not None:
        data["start_param"] = start_param
    if user_dict is not None:
        data["user"] = json.dumps(user_dict, separators=(",", ":"))

    sorted_pairs = sorted(data.items(), key=lambda x: x[0])
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted_pairs)

    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    params = dict(data)
    if tamper_hash:
        params["hash"] = "deadbeef1234567890abcdefdeadbeef1234567890abcdef"
    else:
        params["hash"] = calc_hash

    if tamper_data:
        # Tamper user payload after calculating hash
        params["user"] = json.dumps({"id": 99999999, "first_name": "Hacker"}, separators=(",", ":"))

    return urllib.parse.urlencode(params)


def test_valid_init_data_verifies_successfully() -> None:
    """Verify cryptographically signed initData is validated and user extracted."""
    user_payload = {
        "id": 12345678,
        "first_name": "Aziz",
        "username": "aziz_dev",
        "language_code": "uz",
    }
    init_data = make_init_data(TEST_BOT_TOKEN, user_payload)

    result = verify_telegram_init_data(init_data, TEST_BOT_TOKEN, max_age_seconds=3600)
    assert result["user"]["id"] == 12345678
    assert result["user"]["first_name"] == "Aziz"
    assert result["user"]["username"] == "aziz_dev"


def test_invalid_signature_raises_error() -> None:
    """Verify tampered hash raises TelegramAuthInvalidSignatureError."""
    user_payload = {"id": 12345678, "first_name": "Aziz"}
    tampered_init_data = make_init_data(TEST_BOT_TOKEN, user_payload, tamper_hash=True)

    with pytest.raises(TelegramAuthInvalidSignatureError):
        verify_telegram_init_data(tampered_init_data, TEST_BOT_TOKEN)


@pytest.mark.parametrize(
    ("tamper_key", "tamper_value"),
    [
        ("auth_date", "1700000000"),
        ("query_id", "MALICIOUS_QUERY_ID"),
        ("start_param", "tampered_ref"),
    ],
)
def test_individual_field_tampering_fails(tamper_key: str, tamper_value: str) -> None:
    """Tampering with any single parameter after hash generation must cause verification failure."""
    user_payload = {"id": 12345678, "first_name": "Aziz", "username": "aziz_dev"}
    init_data = make_init_data(TEST_BOT_TOKEN, user_payload, start_param="ref123")
    params = dict(urllib.parse.parse_qsl(init_data))
    params[tamper_key] = tamper_value
    tampered_url = urllib.parse.urlencode(params)

    with pytest.raises(TelegramAuthInvalidSignatureError):
        verify_telegram_init_data(tampered_url, TEST_BOT_TOKEN)


@pytest.mark.parametrize(
    ("field", "new_val"),
    [
        ("id", 87654321),
        ("username", "evil_user"),
        ("first_name", "Malicious"),
    ],
)
def test_user_json_individual_field_tampering_fails(field: str, new_val: object) -> None:
    """Tampering with fields inside the user JSON without re-signing must fail."""
    user_payload = {"id": 12345678, "first_name": "Aziz", "username": "aziz_dev"}
    init_data = make_init_data(TEST_BOT_TOKEN, user_payload)
    params = dict(urllib.parse.parse_qsl(init_data))
    user_dict = json.loads(params["user"])
    user_dict[field] = new_val
    params["user"] = json.dumps(user_dict, separators=(",", ":"))
    tampered_url = urllib.parse.urlencode(params)

    with pytest.raises(TelegramAuthInvalidSignatureError):
        verify_telegram_init_data(tampered_url, TEST_BOT_TOKEN)


def test_auth_date_boundary_conditions() -> None:
    """Test auth_date boundary conditions: fresh, exact boundary, skew, far-future."""
    now = int(time.time())
    user_payload = {"id": 12345678, "first_name": "Aziz"}

    # 1. Fresh (passes)
    fresh = make_init_data(TEST_BOT_TOKEN, user_payload, auth_date=now - 100)
    res = verify_telegram_init_data(fresh, TEST_BOT_TOKEN, max_age_seconds=3600)
    assert res["user"]["id"] == 12345678

    # 2. Within allowed clock skew (now + 30s passes)
    skewed = make_init_data(TEST_BOT_TOKEN, user_payload, auth_date=now + 30)
    res_skew = verify_telegram_init_data(skewed, TEST_BOT_TOKEN, max_age_seconds=3600)
    assert res_skew["user"]["id"] == 12345678

    # 3. Far future (now + 3600s fails)
    far_future = make_init_data(TEST_BOT_TOKEN, user_payload, auth_date=now + 3600)
    with pytest.raises(TelegramAuthExpiredError):
        verify_telegram_init_data(far_future, TEST_BOT_TOKEN, max_age_seconds=3600)

    # 4. Expired (now - 3601s fails)
    expired = make_init_data(TEST_BOT_TOKEN, user_payload, auth_date=now - 3601)
    with pytest.raises(TelegramAuthExpiredError):
        verify_telegram_init_data(expired, TEST_BOT_TOKEN, max_age_seconds=3600)


def test_malformed_auth_date_inputs() -> None:
    """Non-integer or missing auth_date must fail closed with TelegramAuthMalformedError."""
    user_payload = {"id": 12345678, "first_name": "Aziz"}

    # Missing auth_date
    data = {"query_id": "123", "user": json.dumps(user_payload), "hash": "abc"}
    with pytest.raises(TelegramAuthInvalidSignatureError):
        verify_telegram_init_data(urllib.parse.urlencode(data), TEST_BOT_TOKEN)

    # Non-integer auth_date signed properly
    data_bad = {"auth_date": "not_an_int", "query_id": "123", "user": json.dumps(user_payload)}
    sorted_pairs = sorted(data_bad.items(), key=lambda x: x[0])
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted_pairs)
    secret_key = hmac.new(b"WebAppData", TEST_BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
    data_bad["hash"] = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    with pytest.raises(TelegramAuthMalformedError):
        verify_telegram_init_data(urllib.parse.urlencode(data_bad), TEST_BOT_TOKEN)


def test_malformed_hashes_fail_closed() -> None:
    """Missing, empty, or invalid hashes fail closed."""
    with pytest.raises(TelegramAuthMalformedError):
        verify_telegram_init_data("", TEST_BOT_TOKEN)

    with pytest.raises(TelegramAuthMalformedError):
        verify_telegram_init_data("auth_date=123&query_id=123", TEST_BOT_TOKEN)

    with pytest.raises(TelegramAuthMalformedError):
        verify_telegram_init_data("auth_date=123&hash=&query_id=123", TEST_BOT_TOKEN)


def test_malformed_user_payloads_fail_closed() -> None:
    """User payloads with missing id, null, non-dict, or broken JSON fail closed."""
    now = int(time.time())

    # User is null
    data1 = {"auth_date": str(now), "user": "null"}
    sorted_pairs = sorted(data1.items(), key=lambda x: x[0])
    chk = "\n".join(f"{k}={v}" for k, v in sorted_pairs)
    sk = hmac.new(b"WebAppData", TEST_BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
    data1["hash"] = hmac.new(sk, chk.encode("utf-8"), hashlib.sha256).hexdigest()

    with pytest.raises(TelegramAuthMalformedError):
        verify_telegram_init_data(urllib.parse.urlencode(data1), TEST_BOT_TOKEN)

    # User missing id
    data2 = {"auth_date": str(now), "user": json.dumps({"first_name": "NoID"})}
    sorted_pairs2 = sorted(data2.items(), key=lambda x: x[0])
    chk2 = "\n".join(f"{k}={v}" for k, v in sorted_pairs2)
    data2["hash"] = hmac.new(sk, chk2.encode("utf-8"), hashlib.sha256).hexdigest()

    with pytest.raises(TelegramAuthMalformedError):
        verify_telegram_init_data(urllib.parse.urlencode(data2), TEST_BOT_TOKEN)


def test_missing_bot_token_raises_invalid_signature_error() -> None:
    """Empty or None bot token must raise TelegramAuthInvalidSignatureError."""
    with pytest.raises(TelegramAuthInvalidSignatureError):
        verify_telegram_init_data("hash=abc&auth_date=123", "")
