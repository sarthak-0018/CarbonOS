# Database setup

CarbonOS uses PostgreSQL 16, SQLAlchemy 2, and Alembic. Copy `.env.example` to `.env`, set a strong `POSTGRES_PASSWORD`, and use the same credential in `DATABASE_URL`. `POSTGRES_DB` and `POSTGRES_USER` default to `carbonos`; Docker persists data in the `postgres_data` volume.

Start services with `docker compose up --build`. Run schema migrations with `docker compose exec api alembic upgrade head`. Inspect migration state with `docker compose exec api alembic current`. To stop services while preserving data use `docker compose down`; deleting the volume permanently removes local database data.

Tables currently include profiles, profile facts, assets, asset events, vehicles, appliances, activities, emission factors, per-activity calculation records, footprint sessions, and footprint results. The initial migration adds only NULL-valued TODO factor placeholders. No credentials or production factor values are checked into the repository.

Environment variables: `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` configure the container; `DATABASE_URL` configures SQLAlchemy and Alembic; `VITE_API_BASE_URL` configures the frontend API base URL.
