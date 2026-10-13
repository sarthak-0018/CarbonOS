from decimal import Decimal
from dataclasses import dataclass
from app.calculations.engine import DeterministicCalculationEngine, METHODOLOGY_VERSION
from app.calculations.unit_conversion import convert

def calculate_electricity(kwh: Decimal, factor: Decimal, factor_id: str, version: int):
    from app.calculations.contracts import CalculationInput
    return DeterministicCalculationEngine().calculate(CalculationInput(kwh, "kWh", factor, "kWh", factor_id, version, METHODOLOGY_VERSION))


@dataclass(frozen=True)
class ElectricityConsumption:
    annual_kwh: Decimal
    source_kind: str


def annual_consumption(*, annual_kwh: Decimal | None = None, monthly_kwh: Decimal | None = None) -> Decimal:
    if (annual_kwh is None) == (monthly_kwh is None):
        raise ValueError("Provide exactly one of annual_kwh or monthly_kwh")
    value = annual_kwh if annual_kwh is not None else monthly_kwh * 12
    if value < 0:
        raise ValueError("Electricity consumption cannot be negative")
    return value


def normalize_consumption(quantity: Decimal, unit: str, *, period: str = "annual") -> Decimal:
    """Explicitly normalize bill usage to annual kWh."""
    kwh = convert(quantity, unit, "kWh")
    if period == "monthly":
        return kwh * Decimal("12")
    if period != "annual":
        raise ValueError("period must be 'monthly' or 'annual'")
    return kwh


def prefer_actual_electricity(*, actual_annual_kwh: Decimal | None, estimated_appliance_kwh: list[Decimal]) -> ElectricityConsumption:
    """Actual metered consumption replaces appliance estimates to avoid double counting."""
    if actual_annual_kwh is not None:
        return ElectricityConsumption(annual_consumption(annual_kwh=actual_annual_kwh), "ACTUAL")
    estimated = sum(estimated_appliance_kwh, Decimal("0"))
    return ElectricityConsumption(annual_consumption(annual_kwh=estimated), "ESTIMATED")
