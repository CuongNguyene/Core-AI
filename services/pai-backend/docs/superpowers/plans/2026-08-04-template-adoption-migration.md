# Template Adoption and Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt the CTPAI delivery template for PAI without losing its durable
evidence, privacy, authorization and migration boundaries.

**Architecture:** PAI remains one FastAPI modular monolith. The template is
introduced in four mergeable PRs: split PostgreSQL 18/Redis/MinIO delivery,
Redis/ARQ dispatch with PostgreSQL jobs as source of truth, local JWT/password
authentication, then a Next.js mini-app behind Nginx. A public `/pai/api/*`
proxy path maps to the existing backend routes during migration, so no domain
router is rewritten merely to adopt a path convention.

**Tech Stack:** Python 3.13,
FastAPI, SQLAlchemy async, Alembic, PostgreSQL 18, Redis 8 with AOF, ARQ,
PyJWT HS256, bcrypt, Next.js 16, React 19, TypeScript strict, Tailwind 4,
next-intl, Zod, Node 24, Nginx stable, Docker Compose and uv.

## Global Constraints

- Keep PAI a modular monolith and preserve all Alembic revisions and SQL data.
- Keep PostgreSQL as the source of truth for extraction jobs, audit and domain
  lifecycle; Redis must not hold raw CV/JD, prompts, raw model responses or
  authorization authority.
- All worker model calls still go through ModelGateway then PrivacyGateway.
- No self-registration, password reset, SSO/OIDC, refresh token, MFA or
  multi-organization selector is introduced.
- Only an active ADMIN provisions users. JWT establishes actor UUID only;
  ActorContext roles and organization come from persistence on every request.
- Never commit passwords, JWT secrets, Redis passwords, object-store secrets,
  backups, `node_modules`, `.next`, certificate files or generated test files.
- PostgreSQL 17 data moves only through a logical dump/restore to a new
  PostgreSQL 18 volume. Do not mount a 17 data directory into PostgreSQL 18.
- Pin exact dependency versions in `backend/uv.lock` and
  `frontend/package-lock.json` only after each package's stable release and
  Python/Node compatibility is verified at implementation time.

---

### Task 1: PR-010A — Split DevOps delivery foundation and PostgreSQL 18 migration

**Files:**
- Create: `devops/database/docker-compose.yml`, `devops/database/.env.example`
- Create: `devops/redis/docker-compose.yml`, `devops/redis/.env.example`
- Create: `devops/backend/Dockerfile`, `devops/backend/docker-entrypoint.sh`,
  `devops/backend/docker-compose.yml`, `devops/backend/.env.example`
- Create: `devops/minio/docker-compose.yml`, `devops/nginx/docker-compose.yml`,
  `devops/nginx/nginx.conf`, `devops/scripts/init-network.sh`
- Create: `devops/database/POSTGRES_17_TO_18.md`
- Modify: `devops/compose/docker-compose.yml`, `backend/.env.example`,
  `backend/pyproject.toml`, `backend/uv.lock`, `devops/gitlab/pipeline.yml`,
  `.gitignore`, `README.md`, `devops/devops_document.md`
- Test: `backend/tests/test_settings.py`, `devops/scripts/test-compose-config.sh`

**Consumes:** existing async `DATABASE_URL`, MinIO document storage contract,
Alembic revisions and `devops/compose/docker-compose.yml` local stack.

**Produces:** independently runnable template-style service definitions using
an explicit `pai-proxy` network, PostgreSQL 18 with the correct
`/var/lib/postgresql` volume path, Redis password/AOF configuration, and a
backend image able to run either API or worker commands.

- [x] **Step 1: Write failing configuration and Compose contract tests**

Add tests that parse each Compose file with `docker compose config`; assert
PostgreSQL image begins with `postgres:18`, its volume target is
`/var/lib/postgresql`, Redis command includes `--appendonly yes` and
`--requirepass`, and no literal secret from `.env` occurs in tracked YAML.

- [x] **Step 2: Run contract tests before implementation**

Run: `bash devops/scripts/test-compose-config.sh`

Expected: FAIL because the split service definitions and test script do not yet
exist.

- [x] **Step 3: Create split service definitions and runtime image**

Create one Compose file per template service directory. Database, Redis, MinIO,
backend/worker and Nginx join the explicit `pai-proxy` network created by
`init-network.sh`. Keep `devops/compose/docker-compose.yml` as a documented
compatibility aggregator until all split commands pass. The backend entrypoint
runs `uv run alembic upgrade head` only for the API command, then `uv run
uvicorn app.main:app --host 0.0.0.0 --port 8000`; the worker command is supplied
by PR-010B and must not be faked in this PR.

- [x] **Step 4: Add the logical PostgreSQL 17-to-18 runbook**

Document these mandatory, operator-confirmed stages in
`POSTGRES_17_TO_18.md`: stop writers; obtain `pg_dump --format=custom`; record
`alembic current`, table row counts and dump SHA-256; start PostgreSQL 18 with
a **new** named volume; restore with `pg_restore --clean --if-exists`; run
`uv run alembic upgrade head`; compare revision and row counts; run backend
tests against the restored database; retain the old volume until acceptance.
The runbook must state that a failed restore is rolled back by stopping the new
container and reconnecting the old PostgreSQL 17 volume, not by editing either
volume.

- [x] **Step 5: Make configuration explicit and safe**

Add `REDIS_CACHE_URL`, `REDIS_QUEUE_URL`, `REDIS_PASSWORD`,
`PAI_BASE_PATH`, `JWT_SIGNING_KEY` and `PAI_BOOTSTRAP_ADMIN_PASSWORD` as
documented placeholders only. Settings must reject absent production secrets;
the development profile must not substitute a production-safe default.

- [x] **Step 6: Upgrade the backend runtime baseline to the template version**

First run the current backend suite with Python 3.13 in a clean uv environment.
If green, change `requires-python` to `>=3.13`, Ruff and mypy targets to 3.13,
update the FastAPI/Uvicorn/SQLAlchemy/Alembic/Pydantic floors required by the
template, regenerate `uv.lock`, and change the GitLab/backend image to Python
3.13. Do not retain a `requirements.txt`; `pyproject.toml` and `uv.lock` remain
the single dependency source of truth. A failed 3.13 compatibility run blocks
the upgrade and must be resolved before PR-010A merges.

- [x] **Step 7: Verify PR-010A**

Run:

```bash
bash devops/scripts/test-compose-config.sh
docker compose -f devops/database/docker-compose.yml config
docker compose -f devops/redis/docker-compose.yml config
docker compose -f devops/minio/docker-compose.yml config
docker compose -f devops/backend/docker-compose.yml config
docker compose -f devops/nginx/docker-compose.yml config
cd backend && uv run pytest tests/test_settings.py -q
cd backend && uv run ruff check . && uv run mypy app && uv run pytest -q
cd backend && uv run alembic heads
```

Expected: one Alembic head, all Compose definitions resolve and backend quality
remains green. Do not run the real database restore without an operator backup
confirmation.

- [x] **Step 8: Commit PR-010A**

```bash
git add devops backend/.env.example .gitignore README.md
git commit -m "build: adopt split template delivery foundation"
```

### Task 2: PR-010B — Redis cache and ARQ dispatch without replacing durable jobs

**Files:**
- Modify: `backend/pyproject.toml`, `backend/uv.lock`, `backend/app/shared/config.py`
- Create: `backend/app/cache/client.py`, `backend/app/cache/credential_verification.py`
- Create: `backend/app/worker/arq.py`, `backend/app/worker/dispatch.py`,
  `backend/app/worker/reconcile.py`
- Modify: `backend/app/extraction/service.py`, `backend/app/extraction/repository.py`,
  `backend/app/credential/service.py`, `backend/app/main.py`,
  `devops/backend/docker-compose.yml`
- Test: `backend/tests/test_arq_dispatch.py`, `backend/tests/test_job_reconciliation.py`,
  `backend/tests/test_credential_verification_cache.py`

**Consumes:** ADR-0016, `ExtractionJob` persistence, existing worker claim
method, ModelGateway/PrivacyGateway and Redis URLs from PR-010A.

**Produces:** `enqueue_extraction_job(job_id: UUID) -> None`, an ARQ task that
claims before processing, `reconcile_queued_extraction_jobs() -> int`, and an
invalidated bounded-TTL cache for public credential verification.

- [ ] **Step 1: Write the failing queue/cache tests**

Add tests asserting: enqueue receives only the job UUID; duplicate ARQ delivery
causes one claimed execution; broker failure leaves the job queued and never
runs a model inline; reconciliation re-enqueues the queued ID; cache hit serves
the same public verification response; revoke invalidates its cache key; cache
never stores subject/evidence fields.

- [ ] **Step 2: Run tests before implementation**

Run: `cd backend && uv run pytest tests/test_arq_dispatch.py tests/test_job_reconciliation.py tests/test_credential_verification_cache.py -q`

Expected: FAIL because the ARQ, reconciliation and cache modules do not exist.

- [ ] **Step 3: Add dependencies and minimal adapters**

Add `arq` and async Redis client dependencies with locked versions. Implement a
Redis adapter that serializes only safe JSON and uses namespaced keys. Implement
ARQ settings with `process_extraction_job(ctx, job_id: str)` that parses UUID,
loads and claims the PostgreSQL job, then delegates to the existing extraction
service. A failed claim returns normally without any provider call.

- [ ] **Step 4: Add durable dispatch and reconciliation**

After the transaction creating a queued extraction job commits, call the
dispatcher. If Redis is unavailable, return a safe enqueue failure category and
leave the durable job eligible for reconciliation. The reconciliation command
queries only queued/retryable jobs and calls the same dispatcher. It does not
read documents, call models or mutate profile evidence itself.

- [ ] **Step 5: Add cache invalidation**

Cache only the public-safe credential verification schema by credential UUID
with a short configured TTL. Invalidate it in the same service boundary after
issue, revoke or expire transitions commit. On Redis failure, resolve from
PostgreSQL and do not fail open on authorization or validity.

- [ ] **Step 6: Verify PR-010B**

Run:

```bash
cd backend && uv run pytest tests/test_arq_dispatch.py tests/test_job_reconciliation.py tests/test_credential_verification_cache.py -q
cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy app && uv run pytest -q
docker compose -f devops/redis/docker-compose.yml up -d
docker compose -f devops/redis/docker-compose.yml exec redis redis-cli -a "$REDIS_PASSWORD" ping
```

Expected: `PONG`, deterministic queue tests, one backend test suite pass and no
raw document/prompt data in Redis test assertions.

- [ ] **Step 7: Commit PR-010B**

```bash
git add backend devops/backend devops/redis docs
git commit -m "feat: dispatch durable jobs through arq"
```

### Task 3: PR-010C — Local password/JWT identity and administrator provisioning

**Files:**
- Create: `docs/adr/0017-local-password-jwt-authentication.md`
- Create: `backend/alembic/versions/20260804_15_local_authentication.py`
- Modify: `backend/app/authorization/models.py`, `repository.py`, `schemas.py`,
  `fixtures.py`, `policy.py`, `api.py`, `backend/app/main.py`,
  `backend/app/shared/config.py`
- Create: `backend/app/identity/passwords.py`, `backend/app/identity/jwt.py`,
  `backend/app/identity/service.py`, `backend/app/identity/api.py`
- Test: `backend/tests/test_local_auth_api.py`, `backend/tests/test_admin_provisioning.py`,
  `backend/tests/test_jwt_identity_adapter.py`, `backend/tests/test_auth_migration.py`

**Consumes:** UUID subject persistence from ADR-0010 and authorization policies
from ADR-0011/0013.

**Produces:** `POST /auth/login`, `GET /auth/me`, and admin-only
`POST /users`; a JWT adapter that returns the existing `ActorContext`; a bcrypt
password verifier; and explicit password-hash persistence.

- [ ] **Step 1: Write ADR-0017 and failing tests**

ADR-0017 fixes token issuer/audience, HS256 signing-key requirements, access
token TTL, bcrypt cost, ADMIN provisioning, bootstrap behavior, audit metadata,
and header-adapter environment gate. Tests must cover invalid credentials,
missing/expired/tampered token, disabled user, inactive organization,
missing/multiple membership, unknown actor UUID, role changes after a token is
issued, non-admin provisioning denial, duplicate username/email and no
password/hash in responses or audit.

- [ ] **Step 2: Run the targeted tests before implementation**

Run: `cd backend && uv run pytest tests/test_local_auth_api.py tests/test_admin_provisioning.py tests/test_jwt_identity_adapter.py -q`

Expected: FAIL because local identity routes and password/JWT modules do not
exist.

- [ ] **Step 3: Migrate subject persistence without legacy inference**

Add nullable-safe password hash and unique normalized username/email fields to
the existing User table. Use the next Alembic revision based on the actual
single current head. Do not derive a password, username or UUID from old actor
strings. Run an explicit fixture/bootstrap seeder only when the target table is
empty and bootstrap is enabled.

- [ ] **Step 4: Implement authentication and provisioning**

Use bcrypt to hash and verify passwords. `POST /auth/login` accepts only login
identifier/password and returns a short-lived access token. JWT payload has
only registered claims plus subject UUID; it has no role/organization claims.
Every protected request resolves subject persistence before policy evaluation.
`POST /users` requires an active ADMIN ActorContext and creates user,
membership, roles and password through one transaction plus a safe audit event.

- [ ] **Step 5: Gate development headers**

Permit `X-PAI-Actor-ID` only with `APP_ENV=development` or `test`. In
integration/production, ignore or reject it with the safe error contract even
if the header contains a valid fixture UUID. Ensure existing tests explicitly
set their environment.

- [ ] **Step 6: Verify PR-010C**

Run:

```bash
cd backend && uv run alembic upgrade head
cd backend && uv run alembic heads
cd backend && uv run pytest tests/test_local_auth_api.py tests/test_admin_provisioning.py tests/test_jwt_identity_adapter.py tests/test_auth_migration.py -q
cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy app && uv run pytest -q
```

Expected: one head, all old UUID/RBAC tests still pass, and every authentication
negative case fails closed.

- [ ] **Step 7: Commit PR-010C**

```bash
git add backend docs/adr/0017-local-password-jwt-authentication.md
git commit -m "feat: add administrator-provisioned local authentication"
```

### Task 4: PR-010D — Next.js mini-app and Nginx proxy

**Files:**
- Create: `frontend/package.json`, `frontend/package-lock.json`, `frontend/tsconfig.json`,
  `frontend/next.config.ts`, `frontend/Dockerfile`, `frontend/postcss.config.mjs`
- Create: `frontend/app/[locale]/layout.tsx`, `frontend/app/[locale]/page.tsx`,
  `frontend/app/[locale]/login/page.tsx`, `frontend/app/globals.css`
- Create: `frontend/components/layout/app-shell.tsx`, `frontend/lib/api/client.ts`,
  `frontend/lib/auth/session.ts`, `frontend/i18n/routing.ts`,
  `frontend/i18n/request.ts`, `frontend/middleware.ts`,
  `frontend/messages/vi.json`, `frontend/messages/en.json`
- Modify: `devops/frontend/docker-compose.yml`, `devops/nginx/nginx.conf`,
  `devops/nginx/docker-compose.yml`, `README.md`, `frontend/README.md`,
  `devops/devops_document.md`, `.gitlab-ci.yml`, `devops/gitlab/pipeline.yml`
- Test: `frontend/lib/api/client.test.ts`, `frontend/lib/auth/session.test.ts`,
  `devops/nginx/test-routing.sh`

**Consumes:** PR-010A container/network configuration and PR-010C login/me
contract.

**Produces:** a strict TypeScript localized shell at `/pai`, a login flow using
the local auth API, and Nginx routes `/pai/` to frontend and `/pai/api/` to the
backend while preserving the backend's internal route paths.

- [ ] **Step 1: Write failing frontend and proxy tests**

Add tests asserting the API client reads no hard-coded host, attaches the access
token only to API calls, and clears it on 401. Add a proxy shell test that
checks `/pai/` returns frontend HTML, `/pai/api/health/live` reaches FastAPI,
`/pai/api/docs` serves OpenAPI UI assets correctly, and direct backend routes
remain available only on the internal service port.

- [ ] **Step 2: Run tests before implementation**

Run: `cd frontend && npm test` and `bash devops/nginx/test-routing.sh`

Expected: FAIL because the frontend, Nginx routing and test commands do not
exist.

- [ ] **Step 3: Scaffold the template frontend with PAI-safe boundaries**

Use Next.js 16 App Router, React 19, TypeScript strict, Tailwind 4 CSS-first,
next-intl with Vietnamese default and English, and Zod for the login form.
Set `output: "standalone"` and a configurable `basePath` from the same
`PAI_BASE_PATH` used by Nginx. Do not add sign-up, password reset, role picker,
organization selector, domain CRUD demo, or direct Redis access.

- [ ] **Step 4: Implement proxy mapping and API documentation behavior**

Nginx strips `/pai/api` when proxying to the internal FastAPI service, forwards
request IDs safely, and does not log authorization headers or request bodies.
Set FastAPI's proxy/root-path configuration so generated OpenAPI server URLs
and Swagger asset links resolve under `/pai/api`. Maintain a local root-path
mode for direct developer `uvicorn` use.

- [ ] **Step 5: Extend CI and documentation**

Add a frontend install/build/test job using the committed lockfile, retain all
backend checks, and document boot order: network, database, Redis, MinIO,
backend/worker, frontend, Nginx. Document login only with provisioned accounts
and environment-secret injection, never actual credentials.

- [ ] **Step 6: Verify PR-010D end-to-end**

Run:

```bash
cd frontend && npm ci && npm run lint && npm test && npm run build
docker compose -f devops/database/docker-compose.yml up -d
docker compose -f devops/redis/docker-compose.yml up -d
docker compose -f devops/minio/docker-compose.yml up -d
docker compose -f devops/backend/docker-compose.yml up -d --build
docker compose -f devops/frontend/docker-compose.yml up -d --build
docker compose -f devops/nginx/docker-compose.yml up -d
bash devops/nginx/test-routing.sh
cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy app && uv run pytest -q && uv run alembic heads
git diff --check
```

Expected: one migration head, backend and frontend quality suites pass, Nginx
serves the mini-app at the configured base path, and no direct provider/raw
document route exists.

- [ ] **Step 7: Commit PR-010D**

```bash
git add frontend devops README.md .gitlab-ci.yml
git commit -m "feat: add mini-app frontend and proxy delivery"
```

## Final Migration Gate

Before merging PR-010D, run the PostgreSQL 17-to-18 restore rehearsal against a
copy of the current development database; record source/destination Alembic
revision, table count comparison and backend test result in the merge request.
Only then schedule the real local/integration migration with a confirmed backup
and retain the PostgreSQL 17 volume until the smoke test passes.
