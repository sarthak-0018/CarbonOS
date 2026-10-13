from decimal import Decimal
from app.calculations.engine import DeterministicCalculationEngine
from app.calculations.contracts import CalculationInput

def calculate_waste(quantity: Decimal, unit: str, factor: Decimal, factor_id: str, version: int):
    return DeterministicCalculationEngine().calculate(CalculationInput(quantity, unit, factor, unit, factor_id, version, "carbonos-deterministic-v1"))
