# Emission factor provenance

## Electricity, India

The approved `electricity_grid_kwh` factor is `0.675 kgCO2/kWh`, gas `CO2`, from the CEA CO2 Baseline Database Version 22.0. The User Guide reports 0.675 tCO2/MWh as the weighted average Indian Grid factor for FY 2025-26; the explicit conversion is 0.675 kgCO2/kWh. See the [official CEA Version 22.0 User Guide](https://cea.nic.in/wp-content/uploads/baseline/2026/09/User_Guide__Version_22.0.pdf) and the local [factor record](../../data/raw/emission_factors/electricity_india_cea_v22.json).

For activity dates outside FY 2025-26, the latest approved CEA factor can be used under the latest-published-factor policy. Calculation details include the policy statement and the factor's reference period. A CEA result is CO2 and must not be labeled CO2e.

## Road fuel

The approved India petrol and diesel factors are respectively 2.27 and 2.64 kgCO2/litre. The Government of India DPIIT-hosted [City Logistics Plan guidance](https://www.dpiit.gov.in/static/uploads/2025/07/4e218c186c4bdbc202d9f1f62bb9b372.pdf) reports these values and cites *India Specific Road Transport Emission Factors for Stakeholder Consultation* (2015). The user provides distance, recurrence, fuel type, and km/litre efficiency; the calculation annualizes distance, converts it to litres, and applies the saved factor. See the local [petrol and diesel factor records](../../data/raw/emission_factors/transport_india_petrol_diesel_dpiit.json).

No LPG factor is loaded. CNG remains unavailable because the cited per-litre reporting is not a reliable activity unit for compressed gas.

## Lifecycle and importer

Factors are append-only versions keyed by factor key and geography. Statuses are `REVIEW`, `APPROVED`, and `DEPRECATED`; legacy TODO rows are migrated to DEPRECATED, while referenced historical rows remain stored. Approved records require a non-null, nonnegative value and source provenance. Only APPROVED factors are selected for new calculations.

The JSON/CSV importer validates complete records, preserves source metadata and gas, skips an unchanged source/version record, and reports Imported, Updated, Skipped, and Rejected. `Updated` remains zero because approved factor history is append-only. Run `python scripts/data/import_emission_factors.py` with `DATABASE_URL` configured from the host.
