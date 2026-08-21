"""Calendar arithmetic the stdlib doesn't give us (python-dateutil is not a
dependency, and one helper is cheaper than adding it)."""
from calendar import monthrange
from datetime import date


def add_months(start: date, months: int) -> date:
    """`start` shifted forward by whole calendar months.

    Clamps the day to the target month's length, so 31 Jan + 1 month is
    28/29 Feb rather than an invalid date — the alternative (365-day years)
    drifts, and a tag issued on the 15th must expire on the 15th.
    """
    total = start.month - 1 + months
    year = start.year + total // 12
    month = total % 12 + 1
    day = min(start.day, monthrange(year, month)[1])
    return date(year, month, day)
