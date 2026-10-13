from decimal import Decimal
from app.calculations.engine import DeterministicCalculationEngine
from app.calculations.contracts import CalculationInput

def calculate_flight(passenger_km: Decimal, factor: Decimal, factor_id: str, version: int):
    return DeterministicCalculationEngine().calculate(CalculationInput(passenger_km, "passenger_km", factor, "passenger_km", factor_id, version, "carbonos-deterministic-v1"))
