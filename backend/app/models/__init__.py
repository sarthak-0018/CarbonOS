"""SQLAlchemy domain models. Importing this module registers all tables on Base."""

from app.models.domain import Activity, Appliance, Asset, AssetEvent, CalculationRecord, EmissionFactor, FootprintResult, FootprintSession, Profile, ProfileFact, Receipt, ReceiptItem, Vehicle

__all__ = ["Activity", "Appliance", "Asset", "AssetEvent", "CalculationRecord", "EmissionFactor", "FootprintResult", "FootprintSession", "Profile", "ProfileFact", "Receipt", "ReceiptItem", "Vehicle"]
