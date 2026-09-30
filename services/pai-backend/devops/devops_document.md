# DevOps module document

`devops/` owns local/integration Compose configuration, container definitions,
proxy configuration, hosted-CI implementation and operational runbooks.

- Initialize the shared network with `bash devops/scripts/init-network.sh`.
- The template-aligned split services are database, Redis, MinIO, backend and
  Nginx. The previous combined Compose file remains for compatibility until the
  split stack passes migration and integration checks.
- PostgreSQL 18 uses a new `/var/lib/postgresql` volume. Follow
  `database/POSTGRES_17_TO_18.md`; never reuse a PostgreSQL 17 data directory.
- Redis uses password protection and AOF. It is cache/broker infrastructure,
  not a PAI source of truth.
- Copy each service's `.env.example` to its sibling `.env` before running its
  Compose file. The backend Compose file also receives PAI runtime settings
  through the deployment secret-injection mechanism; no `.env` file is tracked
  or assumed by Compose validation.
- Do not rebuild Docker images automatically. Build only when a user explicitly
  requests it or when the approved verification command requires it.
- Update this document for every DevOps service, network, secret-injection,
  Compose, CI or migration-runbook change.
