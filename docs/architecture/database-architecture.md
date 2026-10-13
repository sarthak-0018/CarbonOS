# Database architecture

PostgreSQL is the only application database. Alembic owns schema changes; apply them with `docker compose exec api alembic upgrade head`. The Compose `postgres_data` named volume persists PostgreSQL files through container recreation. Never use `docker compose down -v` for routine restarts.

Profiles own facts, assets, activities, and immutable footprint sessions. Assets can have typed vehicle/appliance rows; asset event snapshots retain edits and retirement. Versioned emission factors have non-overlapping effective dates enforced by the factor service. Calculation records point to a factor version and snapshot the numeric value; footprint results snapshot category-level explanations and percentages.

The current database calls the profile owner `profile_id` (there is not yet an authenticated users table). No second ORM or database system is introduced.
