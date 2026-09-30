# INTEGRATION-04A Runtime Topology

Status: scan only (2026-08-18). No service, dependency, or deployment was changed.

## Current systems

| Area | LMS/TMS | PAI Learning |
|---|---|---|
| UI | React 19 + Vite 8, browser API client | No UI in this repository |
| API | NestJS 11, Node 20, global `/api` prefix, Swagger `/docs` | FastAPI/Uvicorn, routers currently mounted without a global prefix |
| Persistence | Prisma 5.22, PostgreSQL; Prisma schema/migrations are LMS-owned | Async SQLAlchemy + Alembic, PostgreSQL; Alembic migrations are PAI-owned |
| Async work | BullMQ + Redis and Socket.IO | Extraction worker, Redis queues/cache, model calls |
| Files | Local `UPLOAD_DIR` in the LMS configuration | MinIO/S3-compatible secured document storage |
| Model/privacy | None in the scanned LMS runtime | ModelGateway + PrivacyGateway; external provider routing is policy-controlled |

## Current process topology

```text
LMS browser (Vite)
  -> NestJS API :3000/api
      -> Prisma -> LMS PostgreSQL
      -> Redis/BullMQ
      -> local uploads

PAI client/integration adapter
  -> FastAPI/Uvicorn :8000
      -> SQLAlchemy/Alembic -> PAI PostgreSQL
      -> Redis (queue/cache)
      -> MinIO/S3 document store
      -> extraction worker -> ModelGateway/PrivacyGateway -> configured provider
```

## Target monorepo topology

The scan recommends a service-preserving monorepo, not an early language rewrite:

```text
apps/
  lms-web/       # React/Vite
  lms-api/       # NestJS/Prisma
  pai-api/       # FastAPI/SQLAlchemy/Alembic
  pai-worker/    # PAI extraction worker
packages/
  contracts/     # versioned HTTP/event DTOs only
infra/
  compose/       # local orchestration, no shared migration runner
docs/integration/
```

LMS calls PAI through the versioned PAI integration adapter. The adapter owns authentication, correlation IDs, retries, idempotency, and translation between LMS Course Blueprint/Learning Result contracts and PAI artifacts. PAI remains authoritative for evidence, competency, extraction, and capability-analysis semantics.

## Environment and network boundaries

The two services must retain separate environment namespaces. LMS variables include `PORT`, `DATABASE_URL`, `DIRECT_URL`, `JWT_SECRET`, `REDIS_HOST`, `REDIS_PORT`, and `UPLOAD_DIR`. PAI variables include `APP_*`, `DATABASE_URL`, `REDIS_*`, `OBJECT_STORAGE_*`, `MODEL_*`, and privacy-policy controls such as `EXTERNAL_AI_ENABLED` and `PII_EXTERNAL_DEFAULT_DENY`.

In the monorepo, service-to-service URLs should use compose service DNS (for example `PAI_API_BASE_URL=http://pai-api:8000`) and never share database credentials. External model endpoint and raw-document egress remain governed by PAI's privacy gateway; the LMS must not proxy raw CV/JD content directly to a model provider.

## Topology risks

1. Both applications currently assume convenient local ports and separate compose files.
2. Both use PostgreSQL but have incompatible migration/tooling ownership (Prisma versus Alembic).
3. LMS local uploads and PAI MinIO have different retention and access semantics.
4. A shared Redis cluster is possible later, but queue names and serialization must be namespaced (`lms.*`, `pai.*`).
5. A single reverse proxy may add `/api/lms` and `/api/pai`; changing PAI routes in place is not part of this scan.
