from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class CalculationInput:
    activity_value: Decimal
    activity_unit: str
    factor_value_kg_co2e_per_unit: Decimal
    factor_activity_unit: str
    factor_id: str
    factor_version: int
    methodology_version: str


@dataclass(frozen=True)
class CalculationResult:
    emissions_kg_co2e: Decimal
    activity_value: Decimal
    activity_unit: str
    factor_value_kg_co2e_per_unit: Decimal
    factor_id: str
    factor_version: int
    methodology_version: str


class CalculationEngine(Protocol):
    def calculate(self, item: CalculationInput) -> CalculationResult: ...
