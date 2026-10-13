# Database architecture

PostgreSQL is the source of truth. SQLAlchemy models live in `backend/app/models`; Alembic migrations in `backend/migrations` define schema history. Route handlers validate/map HTTP and delegate persistence to `DomainService`.

`profiles` have source-aware `profile_facts`, one-to-many assets and activities, and one-to-many immutable footprint sessions. Assets preserve retired records and append lifecycle snapshots in `asset_events`; vehicle and appliance specifics are stored in dedicated one-to-one subtype tables and mirrored from asset attributes. Activities are soft-deleted, profile-scoped, and may point to an asset. Factors are immutable by key/geography/version and include provenance and valid dates. Calculation records and footprint result JSON keep factor values and input details for reproducibility.

Foreign keys enforce ownership associations; profile/time, factor lookup, and history fields are indexed. Future electricity bills, receipts/products, recommendations, challenges, notifications, and audit logs are intentionally not created in this migration stage.

Profile UUIDs currently act as the API's scoping identifier. Authentication and authorization are not yet implemented, so this API is a local development foundation and must not be exposed to untrusted clients.
