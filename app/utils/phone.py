"""Phone number parsing and normalization utilities."""

import re


def normalize_phone_number(raw_phone: str) -> str | None:
    """Normalize raw phone string into standard E.164 format.

    Supports Uzbekistan numbers (+998...) primarily, as well as valid international numbers.
    Returns normalized string (e.g., '+998901234567') or None if invalid.
    """
    if not raw_phone or not isinstance(raw_phone, str):
        return None

    # Strip whitespace, dashes, parentheses
    cleaned = re.sub(r"[\s\-\(\)\.]", "", raw_phone.strip())

    # If starts with +, check digits
    if cleaned.startswith("+"):
        digits = cleaned[1:]
    else:
        digits = cleaned

    if not digits.isdigit():
        return None

    # Uzbekistan number handling:
    # 9 digits without country code (e.g. '901234567') -> '+998901234567'
    if len(digits) == 9:
        return f"+998{digits}"

    # 12 digits starting with 998 (e.g. '998901234567') -> '+998901234567'
    if len(digits) == 12 and digits.startswith("998"):
        return f"+{digits}"

    # General international E.164 (between 10 and 15 digits)
    if 10 <= len(digits) <= 15:
        return f"+{digits}"

    return None


def format_uzbek_phone(raw_phone: str) -> str | None:
    """Format phone number into readable display format (+998 XX XXX XX XX).

    If the number is a valid 12-digit Uzbekistan number (+998XXXXXXXXX), formats it as:
    +998 71 200 00 00 or +998 90 123 45 67.
    If it is a valid international number, returns normalized E.164 string.
    Returns None if raw_phone is invalid.
    """
    normalized = normalize_phone_number(raw_phone)
    if not normalized:
        return None

    if normalized.startswith("+998") and len(normalized) == 13:
        return (
            f"{normalized[:4]} {normalized[4:6]} {normalized[6:9]} "
            f"{normalized[9:11]} {normalized[11:]}"
        )

    return normalized

