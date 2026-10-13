# CarbonOS

India-first personal carbon intelligence foundation with a React/Vite client, FastAPI API, PostgreSQL persistence, Alembic migrations, and deterministic Decimal-based calculations.

## Run locally

Copy `.env.example` to `.env` and replace `POSTGRES_PASSWORD` and the matching password in `DATABASE_URL`. Start the API and database with `docker compose up --build`, then apply migrations with `docker compose exec api alembic upgrade head`. Start the frontend separately with `npm install` and `npm run dev`.

The API health check is `GET /api/health`. The database schema is managed only through Alembic; application startup does not create tables.

## Persistent domain

Profiles store location, household, diet, preferences, and source-aware facts. Assets support multiple active or retired vehicles and appliances, with event snapshots for historical changes. Activities retain normalized keys, decimal quantities, units, timestamps, source, confidence, recurrence, and optional asset association. Emission factors preserve geography, category, unit, gas, immutable version, reference period, and provenance. Legacy TODO factors are deprecated and cannot be used to calculate.

The current API supports profile onboarding and updates, profile facts, multiple assets, activity history, emission factor listing, per-activity calculations, and footprint calculation/history/latest. Sessions are immutable and explicitly marked COMPLETE, PARTIAL, or UNAVAILABLE. See [DATABASE_SETUP.md](DATABASE_SETUP.md), [CALCULATION_ENGINE.md](CALCULATION_ENGINE.md), and the [API specification](docs/api/api-specification.md).

Calculation uses deterministic decimal arithmetic and APPROVED factors selected from PostgreSQL. Recurring quantities are normalized to annual activity; one-time quantities remain one-time. The CEA electricity factor is 0.675 kgCO2/kWh and petrol/diesel factors are sourced; unsupported categories remain unavailable. Gas type is preserved, so CO2 is never represented as CO2e. Historical sessions retain factor values, source references, activity inputs, factor versions, gas totals, and calculation version.

## Current boundaries

The dashboard fetches the saved latest snapshot and recalculates to include recent edits. Food, flights, public transport, LPG, and CNG remain unavailable pending suitable factors. Authentication/user isolation and admin factor-management endpoints are not implemented. Keep the API on a trusted local network until authentication is added. Factor import and provenance are described in [emission factors](docs/methodology/emission-factors.md); methodology and assumptions are in [calculation methodology](docs/methodology/calculation-methodology.md) and [assumptions](docs/methodology/assumptions.md).
