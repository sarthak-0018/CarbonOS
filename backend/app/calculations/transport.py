from decimal import Decimal
from app.calculations.engine import DeterministicCalculationEngine
from app.calculations.contracts import CalculationInput

def fuel_litres(distance_km: Decimal, efficiency_km_per_litre: Decimal) -> Decimal:
    if distance_km < 0 or efficiency_km_per_litre <= 0:
        raise ValueError("Distance must be nonnegative and efficiency must be positive")
    return distance_km / efficiency_km_per_litre

def calculate_transport(quantity: Decimal, unit: str, factor: Decimal, factor_id: str, version: int):
    return DeterministicCalculationEngine().calculate(CalculationInput(quantity, unit, factor, unit, factor_id, version, "carbonos-deterministic-v1"))
