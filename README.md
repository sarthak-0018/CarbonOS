<<<<<<< HEAD
# CarbonOS

**Your personal carbon footprint, without the spreadsheets.**

CarbonOS is an India-first personal carbon intelligence product foundation. It includes a responsive frontend, a FastAPI domain API, PostgreSQL persistence, versioned emission-factor architecture, and a deterministic calculation service. OCR and AI workflows remain out of scope.

## Stack

- React, Vite, JavaScript, Tailwind CSS, React Router, Recharts, Framer Motion, Lucide
- Python, FastAPI, Pydantic, SQLAlchemy and Alembic
- PostgreSQL via Docker Compose

## Run locally

1. Install Node.js 20+ and Python 3.12+.
2. Run `npm install` and `npm run dev` for the frontend.
3. Copy `.env.example` to `.env`, then run `docker compose up --build` for PostgreSQL and the API.
4. Apply the database schema with `docker compose exec api alembic upgrade head`.

The frontend can run without the API. The health endpoint is `GET /api/health`.

## Domain model and API

- Profiles persist location, household context, preferences, and source-aware confirmed facts.
- Assets persist vehicles, appliances, and other user-owned items, with active/inactive state and an append-only event snapshot for creation, edits, and retirement.
- Activities persist normalized activity keys, decimal quantities, exact units, occurrence timestamps, source, confidence, optional asset association, and soft deletion.
- Emission factors have a stable key, geography, immutable version identity, category, activity/output units, value, status, effective-date range, methodology note, and source/data version, license, checksum, and access metadata.
- Calculation records snapshot the exact input quantity, factor value, factor reference, methodology version, result, and calculation timestamp.

Routes include:

- `POST /api/profiles`, `GET/PATCH /api/profiles/{profile_id}`
- `POST /api/profiles/onboarding` atomically creates a profile, confirmed onboarding facts, selected assets, and asset-created history events
- `GET/POST /api/profiles/{profile_id}/facts` with fact `PATCH/DELETE`
- `GET/POST /api/profiles/{profile_id}/assets`, asset `PATCH`, `/retire`, and `/events`
- `GET/POST /api/profiles/{profile_id}/activities` with activity `PATCH/DELETE`
- `GET /api/emission-factors?status=TODO&geography_code=IN`
- `POST /api/profiles/{profile_id}/activities/{activity_id}/calculate`
- `GET /api/profiles/{profile_id}/activities/{activity_id}/calculations`

The initial migration inserts only TODO factor placeholders with NULL values and no source attribution. They cannot be used to calculate emissions. `FactorCatalogService.add_version` appends factor versions and rejects incomplete verified provenance or overlapping valid dates; factor writes are not exposed as public API without authenticated admin permissions. Add evidence-backed, reviewed factors as new versions before enabling a calculation. Calculation uses Decimal arithmetic, requires an exact unit match and exactly one verified factor effective on the activity date and geography, and rounds results to six decimal places in kgCO₂e. Missing, TODO, overlapping, or unit-mismatched factors return an error; the engine never substitutes or guesses a value.

## Frontend scope

Landing, onboarding, dashboard, profile, activity timeline, receipt and bill upload previews, simulator, insights, settings, and a Carbon Guide placeholder are available. Receipt and bill files are not transmitted or processed. Dashboard content currently uses labeled sample data.

## Boundaries and limitations

- Domain services hold ORM access; API routes handle HTTP mapping and schemas validate input/output.
- OCR and AI provider logic is deferred.
- API endpoints do not yet include authentication or user authorization. Keep the API on a trusted local network until those controls are implemented.
- PostgreSQL migrations are managed by Alembic; the API does not auto-create or mutate the schema at startup.

## Next steps

Source and review geographically and temporally appropriate emission factors, add calculation/domain tests, implement authentication and user isolation, then add OCR/AI behind optional, separately reviewed interfaces.
=======
# CarbonOS
>>>>>>> 67899951d106be4a9416addb5079597157e8f0e8
