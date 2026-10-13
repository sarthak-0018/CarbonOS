# Calculation engine

The engine in `backend/app/calculations/engine.py` is deterministic and uses `Decimal`. It computes normalized `activity × approved factor`, requires exact unit agreement, and rounds emissions to six decimal places. The result keeps the factor gas (`CO2`, `CH4`, `N2O`, or `CO2E`) and does not label CO2 as CO2e. Factor selection is separate from arithmetic: the persistence service selects one APPROVED factor matching activity key, geography, and effective date. REVIEW and DEPRECATED factors are ignored; missing, overlapping, or incompatible factors fail closed.

`POST /api/profiles/{profile_id}/footprint/calculate` accepts an inclusive date range, calculates stored activities, and saves an immutable session with category results. `GET /api/profiles/{profile_id}/footprint/history` returns those snapshots. Each result stores the activity quantity/unit/source, factor id/value/unit/version and provenance, and emissions, along with the methodology version. A later factor import therefore does not rewrite prior results.

The footprint session retains the factor-version list when it fits the schema field; unusually large lists are represented by a SHA-256 digest. The full factor identities and provenance remain in the per-activity category details.

Activity recurrence is stored in `details.frequency`: ONE_TIME ×1, DAILY ×365, WEEKLY ×52, MONTHLY ×12, QUARTERLY ×4, YEARLY ×1. Recurring results are labeled `ANNUALIZED_ESTIMATE`; one-time events use the requested date-window label. Data quality is the arithmetic mean of input-source scores: BILL_UPLOAD/INTEGRATION 100, USER_ENTERED 80, ESTIMATED 40. It is a deterministic indicator, not a statistically validated confidence score.

Legacy TODO rows are retired from use by migration `20261006_0005`. The approved CEA India grid factor is `0.675 kgCO2/kWh`, sourced from the Version 22.0 user guide for FY 2025-26. For dates outside that reference period, the latest approved CEA factor is explicitly identified in calculation details as the latest published factor. Diet labels alone do not produce emissions.

Petrol and diesel distance activities use APPROVED India fuel factors of 2.27
and 2.64 kgCO2/litre, reported by DPIIT-hosted City Logistics Plan guidance
(citing the 2015 India Specific Road Transport Emission Factors report). The
calculation converts entered distance to fuel volume using the user-entered
vehicle efficiency. LPG, CNG, flights, food, and public transport remain
unavailable until usable factors are reviewed and loaded.
