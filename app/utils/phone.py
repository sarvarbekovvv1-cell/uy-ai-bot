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
