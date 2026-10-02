from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.schemas.domain import (
    ActivityCreate, ActivityRead, ActivityUpdate, AssetCreate, AssetEventRead, AssetRead, AssetUpdate,
    CalculationRead, FactCreate, FactRead, FactUpdate, FactorRead, OnboardingProfileCreate, ProfileCreate, ProfileRead, ProfileUpdate,
)
from app.services.domain import DomainService, FactorUnavailableError, NotFoundError

router = APIRouter(prefix="/api", tags=["carbon data"])
Db = Annotated[Session, Depends(get_session)]


def service(session: Session) -> DomainService:
    return DomainService(session)


def _not_found(call):
    try:
        return call()
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": str(exc)}) from exc


@router.post("/profiles", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
def create_profile(payload: ProfileCreate, db: Db):
    return service(db).create_profile(payload)


# Onboarding writes the profile, confirmed facts, assets, and asset events in one transaction.
@router.post("/profiles/onboarding", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
def create_profile_from_onboarding(payload: OnboardingProfileCreate, db: Db):
    return service(db).create_profile_from_onboarding(payload)


@router.get("/profiles/{profile_id}", response_model=ProfileRead)
def get_profile(profile_id: UUID, db: Db):
    return _not_found(lambda: service(db).get_profile(profile_id))


@router.patch("/profiles/{profile_id}", response_model=ProfileRead)
def update_profile(profile_id: UUID, payload: ProfileUpdate, db: Db):
    return _not_found(lambda: service(db).update_profile(profile_id, payload))


@router.get("/profiles/{profile_id}/facts", response_model=list[FactRead])
def list_profile_facts(profile_id: UUID, db: Db):
    return _not_found(lambda: service(db).list_facts(profile_id))


@router.post("/profiles/{profile_id}/facts", response_model=FactRead, status_code=201)
def create_profile_fact(profile_id: UUID, payload: FactCreate, db: Db):
    return _not_found(lambda: service(db).create_fact(profile_id, payload))


@router.patch("/profiles/{profile_id}/facts/{fact_id}", response_model=FactRead)
def update_profile_fact(profile_id: UUID, fact_id: UUID, payload: FactUpdate, db: Db):
    return _not_found(lambda: service(db).update_fact(profile_id, fact_id, payload))


@router.delete("/profiles/{profile_id}/facts/{fact_id}", status_code=204)
def delete_profile_fact(profile_id: UUID, fact_id: UUID, db: Db):
    _not_found(lambda: service(db).delete_fact(profile_id, fact_id))
    return Response(status_code=204)


@router.get("/profiles/{profile_id}/assets", response_model=list[AssetRead])
def list_assets(profile_id: UUID, db: Db, include_inactive: bool = False):
    return _not_found(lambda: service(db).list_assets(profile_id, include_inactive))


@router.post("/profiles/{profile_id}/assets", response_model=AssetRead, status_code=201)
def create_asset(profile_id: UUID, payload: AssetCreate, db: Db):
    return _not_found(lambda: service(db).create_asset(profile_id, payload))


@router.patch("/profiles/{profile_id}/assets/{asset_id}", response_model=AssetRead)
def update_asset(profile_id: UUID, asset_id: UUID, payload: AssetUpdate, db: Db):
    return _not_found(lambda: service(db).update_asset(profile_id, asset_id, payload))


@router.post("/profiles/{profile_id}/assets/{asset_id}/retire", response_model=AssetRead)
def retire_asset(profile_id: UUID, asset_id: UUID, db: Db):
    return _not_found(lambda: service(db).retire_asset(profile_id, asset_id))


@router.get("/profiles/{profile_id}/assets/{asset_id}/events", response_model=list[AssetEventRead])
def asset_events(profile_id: UUID, asset_id: UUID, db: Db):
    return _not_found(lambda: service(db).list_asset_events(profile_id, asset_id))


@router.get("/profiles/{profile_id}/activities", response_model=list[ActivityRead])
def list_activities(profile_id: UUID, db: Db, limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)):
    return _not_found(lambda: service(db).list_activities(profile_id, limit, offset))


@router.post("/profiles/{profile_id}/activities", response_model=ActivityRead, status_code=201)
def create_activity(profile_id: UUID, payload: ActivityCreate, db: Db):
    return _not_found(lambda: service(db).create_activity(profile_id, payload))


@router.patch("/profiles/{profile_id}/activities/{activity_id}", response_model=ActivityRead)
def update_activity(profile_id: UUID, activity_id: UUID, payload: ActivityUpdate, db: Db):
    return _not_found(lambda: service(db).update_activity(profile_id, activity_id, payload))


@router.delete("/profiles/{profile_id}/activities/{activity_id}", status_code=204)
def delete_activity(profile_id: UUID, activity_id: UUID, db: Db):
    _not_found(lambda: service(db).delete_activity(profile_id, activity_id))
    return Response(status_code=204)


@router.get("/emission-factors", response_model=list[FactorRead])
def list_emission_factors(db: Db, factor_key: str | None = None, factor_status: str | None = Query(default=None, alias="status"), geography_code: str | None = None):
    return service(db).list_factors(factor_key, factor_status, geography_code)


@router.post("/profiles/{profile_id}/activities/{activity_id}/calculate", response_model=CalculationRead, status_code=201)
def calculate_activity(profile_id: UUID, activity_id: UUID, db: Db):
    try:
        record, factor = service(db).calculate_activity(profile_id, activity_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": str(exc)}) from exc
    except FactorUnavailableError as exc:
        raise HTTPException(status_code=409, detail={"code": "EMISSION_FACTOR_UNAVAILABLE", "message": str(exc), "factor_key": exc.factor_key, "factor_status": exc.factor_status}) from exc
    return CalculationRead.model_validate({
        **record.__dict__, "factor_key": factor.factor_key, "factor_version": factor.version,
    })


@router.get("/profiles/{profile_id}/activities/{activity_id}/calculations", response_model=list[CalculationRead])
def calculation_history(profile_id: UUID, activity_id: UUID, db: Db):
    try:
        rows = service(db).list_calculations(profile_id, activity_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": str(exc)}) from exc
    output = []
    for record, factor in rows:
        output.append(CalculationRead.model_validate({
            **record.__dict__, "factor_key": factor.factor_key, "factor_version": factor.version,
        }))
    return output
