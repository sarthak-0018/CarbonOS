# Calculation methodology

## Arithmetic and factor selection

For each activity, the deterministic service computes normalized quantity multiplied by a versioned factor using Python `Decimal`; it rejects negative values and mismatched units and rounds emissions to six decimal places. The persistence layer requires one and only one APPROVED factor whose key, geography, status, and effective dates match the activity. REVIEW and DEPRECATED factors are not used. Missing or ambiguous factors remain unavailable.

Factors are not inferred from category names. Legacy TODO rows are marked DEPRECATED by the gas-provenance migration. The approved Indian grid electricity factor is 0.675 kgCO₂/kWh from the CEA CO₂ Baseline Database Version 22.0, for FY 2025-26. The CEA user guide reports weighted average 0.675 tCO₂/MWh; conversion is 1 t/MWh = 1 kg/kWh. CEA publishes CO₂, so this result is not CO₂e. See [factor source data](../data/raw/emission_factors/electricity_india_cea_v22.json).

## Reproducibility and scope

Every calculation record stores its activity quantity/unit, factor id and numeric value snapshot, emissions, methodology version, and timestamp. A footprint session stores date range, selected factor-version set, calculation version, total, and category rows. Category details include each contributing activity and factor provenance. Later catalog changes do not mutate these snapshots.

Current aggregate calculations use stored activities. Profile-level estimated appliance consumption and diet labels do not independently generate emissions; they need explicit, documented activity conversion methods and verified factors first. Do not combine appliance estimates with overlapping actual electricity activities. Food, grocery, air travel, LPG, CNG, and public transport remain unavailable until verified factors are loaded.
# Calculation version 2: frequency and factor provenance

Every approved factor is selected from PostgreSQL by activity key, geography,
approval status, and its effective dates. Review, deprecated, and legacy TODO
records are never used. Activity emissions are calculated with decimal
arithmetic as normalized activity quantity × factor.

Recurring activity is normalized to an annual quantity using fixed calendar
conventions: daily × 365, weekly × 52, monthly × 12, quarterly × 4, yearly × 1.
ONE_TIME values are multiplied by 1. Recurring results are labeled
`ANNUALIZED_ESTIMATE`; event-only results are labeled `YTD_ACTUAL` for the
requested date window.

The CEA Version 22.0 weighted-average Indian grid factor is 0.675 tCO2/MWh,
equivalent to 0.675 kgCO2/kWh. Its reference data is FY 2025-26. For activity
dates outside that reference period, the latest approved CEA grid factor is
used with an explicit latest-published-factor note in calculation details.
The factor is CO2 and must not be described as CO2e.

For road travel with user-entered distance, fuel type, and vehicle efficiency,
the pipeline converts annualized distance to litres (`km ÷ km/litre`) and
multiplies by the APPROVED India petrol or diesel fuel factor. These source
values (2.27 kgCO2/litre petrol and 2.64 kgCO2/litre diesel) are reported in
Government of India DPIIT-hosted City Logistics Plan guidance, citing the 2015
India Specific Road Transport Emission Factors for Stakeholder Consultation.
They are CO2-only source factors. LPG and CNG remain unavailable because no
factor with reliable source applicability/units is seeded.

Data quality is a deterministic input-source score, not a scientifically
validated uncertainty estimate: bill/integration data = 100, user-entered =
80, estimated = 40. The session score is the arithmetic mean across saved
activity records in the requested window, including records lacking an
approved factor.

Sessions with multiple gas measurement types do not combine their values into
one total. The response stores totals by gas and labels the measurement as
mixed. A CO2-only result is PARTIAL because it is not a complete CO2e footprint.
