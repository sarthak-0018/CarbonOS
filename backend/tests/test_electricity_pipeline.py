import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_session
from app.main import app
from app.models import Activity, Asset, EmissionFactor, FootprintResult, FootprintSession, Profile, Vehicle
from app.services.emission_factor_service import EmissionFactorService


def test_cea_electricity_factor_activity_calculation_and_api_round_trip():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    with TestingSession() as db:
        seed_path = Path(__file__).resolve().parents[2] / "data/raw/emission_factors/electricity_india_cea_v22.json"
        factor_payload = json.loads(seed_path.read_text(encoding="utf-8"))
        assert EmissionFactorService(db).import_record(factor_payload) == "Imported"
        assert EmissionFactorService(db).import_record(factor_payload) == "Skipped"
        fuel_path = seed_path.with_name("transport_india_petrol_diesel_dpiit.json")
        for fuel_factor in json.loads(fuel_path.read_text(encoding="utf-8")):
            assert EmissionFactorService(db).import_record(fuel_factor) == "Imported"
        factor = db.scalar(select(EmissionFactor).where(EmissionFactor.factor_key == "electricity_grid_kwh"))
        assert factor is not None and factor.status == "APPROVED"
        assert factor.gas == "CO2" and factor.value_kg_co2e_per_unit == Decimal("0.675")

        profile = Profile(display_name="Pipeline test", country_code="IN", preferences={})
        db.add(profile)
        db.flush()
        activity = Activity(
            profile_id=profile.id, activity_type="electricity_grid_kwh", quantity=Decimal("180"), unit="kWh",
            occurred_at=datetime(2026, 10, 6, tzinfo=timezone.utc), source="USER_ENTERED",
            details={"frequency": "MONTHLY"},
        )
        db.add(activity)
        db.commit()
        profile_id = str(profile.id)
        activity_id = str(activity.id)

    def override_session():
        with TestingSession() as db:
            yield db

    app.dependency_overrides[get_session] = override_session
    try:
        client = TestClient(app)
        response = client.post(f"/api/profiles/{profile_id}/footprint/calculate", json={
            "period_start": "2026-01-01", "period_end": "2026-10-06",
        })
        assert response.status_code == 201, response.text
        payload = response.json()
        assert payload["status"] == "PARTIAL"
        assert payload["total_co2e"] == "1458.000000"
        assert payload["unit"] == "kgCO2"
        assert payload["measurement_type"] == "CO2"
        assert payload["period_kind"] == "ANNUALIZED_ESTIMATE"
        assert payload["total"]["value"] == "1458.000000"
        assert payload["total"]["unit"] == "kgCO2"
        result = payload["results"][0]
        assert result["category"] == "electricity"
        assert result["co2e"] == "1458.000000"
        activity_detail = result["calculation_details"]["activities"][0]
        assert activity_detail["normalized_quantity"] == "2160.000000"
        assert activity_detail["factor_value"] == "0.675000000000"
        assert activity_detail["gas"] == "CO2"
        one_activity = client.post(f"/api/profiles/{profile_id}/activities/{activity_id}/calculate")
        assert one_activity.status_code == 201
        assert one_activity.json()["gas"] == "CO2"
        assert one_activity.json()["activity_quantity"] == "2160.000000"

        with TestingSession() as db:
            vehicle_asset = Asset(profile_id=UUID(profile_id), asset_type="VEHICLE", name="Profile vehicle", attributes={})
            db.add(vehicle_asset)
            db.flush()
            db.add(Vehicle(asset_id=vehicle_asset.id, fuel_type="petrol", fuel_efficiency=Decimal("17")))
            db.add(Activity(
                profile_id=UUID(profile_id), asset_id=vehicle_asset.id,
                activity_type="road_travel_car_km", quantity=Decimal("170"), unit="km",
                occurred_at=datetime(2026, 10, 6, tzinfo=timezone.utc), source="USER_ENTERED",
                details={"frequency": "MONTHLY"},
            ))
            db.commit()
        with_transport = client.post(f"/api/profiles/{profile_id}/footprint/calculate", json={
            "period_start": "2026-01-01", "period_end": "2026-10-06",
        }).json()
        transport = next(x for x in with_transport["results"] if x["category"] == "transport")
        assert transport["co2e"] == "272.400000"
        assert transport["value"] == "272.400000"
        assert transport["unit"] == "kgCO2"
        transport_activity = transport["calculation_details"]["activities"][0]
        assert Decimal(transport_activity["normalized_quantity"]) == Decimal("120")
        assert transport_activity["factor_unit"] == "kgCO2/litre"
        assert transport_activity["formula"].endswith("kgCO2/litre = 272.400000 kgCO2")
        assert "Central Electricity Authority" not in transport_activity["source_name"]

        latest = client.get(f"/api/profiles/{profile_id}/footprint/latest")
        assert latest.status_code == 200
        assert latest.json()["results"][0]["co2e"] == "1458.000000"
        with TestingSession() as db:
            assert db.get(Activity, UUID(activity_id)) is not None
            assert db.scalar(select(FootprintSession).where(FootprintSession.profile_id == UUID(profile_id))) is not None
            assert db.scalar(select(FootprintResult)) is not None

        with TestingSession() as db:
            factors = list(db.scalars(select(EmissionFactor).where(EmissionFactor.factor_key.in_(("electricity_grid_kwh", "fuel_petrol_litre")))))
            for factor in factors:
                factor.status = "DEPRECATED"
            db.commit()
        unavailable = client.post(f"/api/profiles/{profile_id}/footprint/calculate", json={
            "period_start": "2026-01-01", "period_end": "2026-10-06",
        }).json()
        assert unavailable["status"] == "UNAVAILABLE"
        assert unavailable["results"] == []
        assert {x["factor_key"] for x in unavailable["missing_factors"]} == {"electricity_grid_kwh", "fuel_petrol_litre"}
        with TestingSession() as db:
            factors = list(db.scalars(select(EmissionFactor).where(EmissionFactor.factor_key.in_(("electricity_grid_kwh", "fuel_petrol_litre")))))
            for factor in factors:
                factor.status = "APPROVED"
            db.commit()
        restored = client.post(f"/api/profiles/{profile_id}/footprint/calculate", json={
            "period_start": "2026-01-01", "period_end": "2026-10-06",
        }).json()
        assert restored["status"] == "PARTIAL"
        assert restored["total_co2e"] == "1730.400000"
    finally:
        app.dependency_overrides.pop(get_session, None)
        Base.metadata.drop_all(engine)
        engine.dispose()
