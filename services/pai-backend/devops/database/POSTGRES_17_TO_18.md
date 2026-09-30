# PostgreSQL 17 → 18 local/integration migration

Do not mount an existing PostgreSQL 17 data volume into PostgreSQL 18.

1. Stop API and worker writers.
2. Record `uv run alembic current`, row counts for each PAI table, and the
   source container/volume name.
3. Create a logical backup with `pg_dump --format=custom`; calculate and record
   its SHA-256 outside Git.
4. Keep the PostgreSQL 17 volume untouched. Create the `pai_postgres18_data`
   volume by starting the PostgreSQL 18 Compose service.
5. Restore into PostgreSQL 18 with `pg_restore --clean --if-exists`.
6. Run `cd backend && uv run alembic upgrade head`; compare the Alembic revision
   and row counts with the source; then run the full backend test suite against
   the restored database.
7. If restore or verification fails, stop PostgreSQL 18 and reconnect clients
   to PostgreSQL 17. Do not edit either data directory. Retain the old volume
   until the verified smoke test is accepted.
