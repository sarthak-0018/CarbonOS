from decimal import Decimal
from app.calculations.electricity import calculate_electricity

def estimated_appliance_kwh(estimated_kwh_year: Decimal | None) -> Decimal:
    if estimated_kwh_year is None:
        raise ValueError("Appliance has no documented annual consumption estimate")
    if estimated_kwh_year < 0:
        raise ValueError("Estimated consumption cannot be negative")
    return estimated_kwh_year

__all__ = ["calculate_electricity", "estimated_appliance_kwh"]
