from decimal import Decimal

import pytest

from app.calculations.contracts import CalculationInput
from app.calculations.engine import DeterministicCalculationEngine, UnitMismatchError
from app.calculations.transport import fuel_litres
from app.calculations.unit_conversion import convert
from app.calculations.electricity import annual_consumption, prefer_actual_electricity


def test_engine_uses_decimal_arithmetic_and_stable_rounding():
    result = DeterministicCalculationEngine().calculate(CalculationInput(
        activity_value=Decimal("2.5"), activity_unit="kWh",
        factor_value_kg_co2e_per_unit=Decimal("0.123456789"), factor_activity_unit="kWh",
        factor_id="factor-1", factor_version=2, methodology_version="test-v1",
    ))
    assert result.emissions_kg_co2e == Decimal("0.308642")


def test_engine_rejects_unit_mismatch_and_negative_inputs():
    engine = DeterministicCalculationEngine()
    with pytest.raises(UnitMismatchError):
        engine.calculate(CalculationInput(Decimal("1"), "km", Decimal("1"), "kWh", "f", 1, "v1"))
    with pytest.raises(ValueError):
        engine.calculate(CalculationInput(Decimal("-1"), "km", Decimal("1"), "km", "f", 1, "v1"))


def test_fuel_conversion_requires_known_positive_efficiency():
    assert fuel_litres(Decimal("120"), Decimal("15")) == Decimal("8")
    assert fuel_litres(Decimal("0"), Decimal("15")) == Decimal("0")
    with pytest.raises(ValueError):
        fuel_litres(Decimal("12"), Decimal("0"))


def test_unit_conversions_are_explicit():
    assert convert(Decimal("1500"), "Wh", "kWh") == Decimal("1.500")
    with pytest.raises(ValueError):
        convert(Decimal("1"), "km", "litre")


def test_monthly_electricity_annualizes_and_actual_replaces_estimates():
    assert annual_consumption(monthly_kwh=Decimal("120")) == Decimal("1440")
    result = prefer_actual_electricity(actual_annual_kwh=Decimal("1000"), estimated_appliance_kwh=[Decimal("400")])
    assert result.annual_kwh == Decimal("1000")
    assert result.source_kind == "ACTUAL"
    estimated = prefer_actual_electricity(actual_annual_kwh=None, estimated_appliance_kwh=[Decimal("200"), Decimal("300")])
    assert estimated.annual_kwh == Decimal("500")
    assert estimated.source_kind == "ESTIMATED"
