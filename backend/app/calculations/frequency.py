"""Convert recorded recurrence to a deterministic annualized activity quantity."""
from decimal import Decimal

_ANNUAL_MULTIPLIERS = {
    "ONE_TIME": Decimal("1"),
    "DAILY": Decimal("365"),
    "WEEKLY": Decimal("52"),
    "MONTHLY": Decimal("12"),
    "QUARTERLY": Decimal("4"),
    "YEARLY": Decimal("1"),
}


def annualize(quantity: Decimal, frequency: str) -> Decimal:
    normalized = (frequency or "ONE_TIME").strip().upper()
    try:
        multiplier = _ANNUAL_MULTIPLIERS[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported activity frequency {frequency!r}") from exc
    if quantity < 0:
        raise ValueError("Activity quantity cannot be negative")
    return quantity * multiplier


def normalize_frequency(value: str | None) -> str:
    normalized = (value or "ONE_TIME").strip().upper()
    if normalized not in _ANNUAL_MULTIPLIERS:
        raise ValueError(f"frequency must be one of {', '.join(_ANNUAL_MULTIPLIERS)}")
    return normalized
