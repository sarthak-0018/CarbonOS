"""Small deterministic normalizers for canonical activity keys and unit labels."""

import re


def normalize_activity_key(value: str) -> str:
    key = re.sub(r"[\s-]+", "_", value.strip().lower())
    if not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", key):
        raise ValueError("activity_type must be a simple normalized key")
    return key


_UNIT_ALIASES = {
    "kwh": "kWh", "kilowatt_hour": "kWh", "kilowatt_hours": "kWh", "unit": "kWh", "units": "kWh",
    "km": "km", "kilometer": "km", "kilometers": "km", "kilometre": "km", "kilometres": "km",
    "kg": "kg", "kilogram": "kg", "kilograms": "kg",
    "l": "litre", "liter": "litre", "liters": "litre", "litre": "litre", "litres": "litre",
    "passenger_km": "passenger_km", "passenger-km": "passenger_km",
}


def normalize_unit(value: str) -> str:
    original = value.strip()
    canonical = _UNIT_ALIASES.get(original.lower())
    if canonical is None:
        raise ValueError(f"Unsupported unit label {value!r}; use an explicitly supported canonical unit")
    return canonical
