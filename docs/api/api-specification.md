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
# Grocery receipt endpoints

The local-development scanner adds `GET /api/receipts/categories`, `POST /api/receipts/scan` (multipart `profile_id` and `image`), `GET /api/receipts?profile_id=...`, `GET /api/receipts/{id}?profile_id=...`, `GET /api/receipts/{id}/image?profile_id=...`, `POST /api/receipts/{id}/process?profile_id=...` for failed/interrupted retries, `PATCH /api/receipts/{id}/items/{item_id}?profile_id=...`, `POST /api/receipts/{id}/items?profile_id=...`, `DELETE /api/receipts/{id}/items/{item_id}?profile_id=...`, `PATCH /api/receipts/{id}?profile_id=...`, `POST /api/receipts/{id}/confirm?profile_id=...`, and `POST /api/receipts/{id}/recalculate?profile_id=...`. These follow the existing profile-ID ownership pattern; account authentication is not part of the current project foundation. Uploads accept JPG/JPEG, PNG, and WebP up to 10 MB. Receipt and item corrections are decimal validated; OCR and parsing failures do not invent quantities. Unsupported rows remain stored with a null carbon result and an explicit status.
