import re

from django.core.exceptions import ValidationError


CNIC_DIGITS = 13


def format_cnic_digits(digits: str) -> str:
    return f"{digits[:5]}-{digits[5:12]}-{digits[12:]}"


def normalize_cnic(value: str | None, *, required: bool = False) -> str:
    """Return Pakistani CNIC as XXXXX-XXXXXXX-X."""
    raw = (value or '').strip()
    digits = re.sub(r'\D', '', raw)
    if not digits:
        if required:
            raise ValidationError("CNIC is required.")
        return ''
    if len(digits) != CNIC_DIGITS:
        raise ValidationError("CNIC must be 13 digits.")
    return format_cnic_digits(digits)
