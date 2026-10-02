"""Pure deterministic emissions arithmetic; factor selection and persistence are separate."""

from decimal import Decimal, ROUND_HALF_UP

from app.calculations.contracts import CalculationInput, CalculationResult

METHODOLOGY_VERSION = "carbonos-deterministic-v1"
RESULT_QUANTUM = Decimal("0.000001")


class UnitMismatchError(ValueError):
    pass


class DeterministicCalculationEngine:
    """Calculate activity × verified factor with Decimal-only arithmetic."""

    def calculate(self, item: CalculationInput) -> CalculationResult:
        if item.activity_value < 0:
            raise ValueError("Activity quantity cannot be negative")
        if item.factor_value_kg_co2e_per_unit < 0:
            raise ValueError("Emission factor cannot be negative")
        if item.activity_unit != item.factor_activity_unit:
            raise UnitMismatchError(
                f"Activity unit {item.activity_unit!r} does not match factor unit {item.factor_activity_unit!r}"
            )
        result = (item.activity_value * item.factor_value_kg_co2e_per_unit).quantize(
            RESULT_QUANTUM, rounding=ROUND_HALF_UP
        )
        return CalculationResult(
            emissions_kg_co2e=result,
            activity_value=item.activity_value,
            activity_unit=item.activity_unit,
            factor_value_kg_co2e_per_unit=item.factor_value_kg_co2e_per_unit,
            factor_id=item.factor_id,
            factor_version=item.factor_version,
            methodology_version=item.methodology_version,
        )
