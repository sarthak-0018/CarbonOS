"""Explicit, deterministic unit conversions. No implicit density/efficiency assumptions."""
from decimal import Decimal

CONVERSIONS = {
    ("Wh", "kWh"): Decimal("0.001"),
    ("kWh", "Wh"): Decimal("1000"),
    ("m", "km"): Decimal("0.001"),
    ("km", "m"): Decimal("1000"),
    ("g", "kg"): Decimal("0.001"),
    ("kg", "g"): Decimal("1000"),
    ("mile", "km"): Decimal("1.609344"),
    ("km", "mile"): Decimal("0.621371192237334"),
    ("tonne", "kg"): Decimal("1000"),
    ("kg", "tonne"): Decimal("0.001"),
    ("gallon_us", "litre"): Decimal("3.785411784"),
    ("litre", "gallon_us"): Decimal("0.264172052358148"),
    ("miles", "km"): Decimal("1.609344"),
    ("km", "miles"): Decimal("0.621371192237334"),
    ("gallons", "litre"): Decimal("3.785411784"),
    ("litre", "gallons"): Decimal("0.264172052358148"),
    ("tonnes", "kg"): Decimal("1000"),
    ("kg", "tonnes"): Decimal("0.001"),
    ("grams", "kg"): Decimal("0.001"),
    ("kg", "grams"): Decimal("1000"),
}

def convert(value: Decimal, from_unit: str, to_unit: str) -> Decimal:
    if from_unit == to_unit:
        return value
    try:
        return value * CONVERSIONS[(from_unit, to_unit)]
    except KeyError as exc:
        raise ValueError(f"Unsupported conversion: {from_unit} to {to_unit}") from exc
