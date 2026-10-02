"""SQLAlchemy domain models. Importing this module registers all tables on Base."""

from app.models.domain import Activity, Asset, AssetEvent, CalculationRecord, EmissionFactor, Profile, ProfileFact

__all__ = ["Activity", "Asset", "AssetEvent", "CalculationRecord", "EmissionFactor", "Profile", "ProfileFact"]
