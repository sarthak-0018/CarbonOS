# API notes

- `GET /api/health`: API liveness.
- `POST /api/profiles/onboarding`: creates profile, facts, and multiple assets in one transaction.
- `POST /api/profiles/{profile_id}/activities`: stores a source-aware activity.
- `POST /api/profiles/{profile_id}/footprint/calculate`: creates an immutable calculation session and category results; request includes inclusive `period_start` and `period_end` dates. Response includes session status and missing factor reasons.
- `GET /api/profiles/{profile_id}/footprint/latest`: most recent saved calculation (404 if none).
- `GET /api/profiles/{profile_id}/footprint/history`: historical session snapshots.
- `GET /api/emission-factors`: versioned factor catalog with status and gas metadata. Legacy TODO factors have been marked DEPRECATED and are excluded from calculation.

Footprint responses retain legacy `total_co2e`/`co2e` fields for compatibility and also expose gas-aware `total`/`value` and `unit` fields. `measurement_type` identifies CO2, CO2E, or MIXED; mixed gas totals are returned separately by gas.

Factor catalog mutation has no public endpoint. Admin authentication is not implemented; use the controlled importer only from a trusted environment.
