# Mini-app Template Alignment Design

## Goal

Adopt the CTPAI template capability set for PAI as an integrated mini-app,
without replacing its evidence-first modular monolith. Migrate infrastructure,
queue dispatch, authentication and frontend in reversible, independently
verifiable PRs.

## Scope and Non-goals

This design covers the delivery architecture and its staged rollout. The
template is applied as the target state, not copied as a greenfield repository:
PAI's existing migrations, document-storage boundary, ModelGateway/
PrivacyGateway, UUID actor identity, RBAC and scoped delegation are retained.

The following remain out of scope: SSO/OIDC, self-registration, password reset,
MFA, refresh tokens, multi-organization selection, public sign-up/password
reset, production storage/retention decisions and SSO/OIDC remain out of scope.

## Target Delivery Shape

```text
Larger system reverse proxy
  └─ /pai (configurable)
       ├─ frontend static/app shell       [PR-010C]
       └─ backend API and worker          [existing monolith]
            ├─ PostgreSQL
            ├─ MinIO (document boundary)
            └─ Redis cache + ARQ dispatch

devops/
  compose/       local/integration service definitions
  proxy/         reverse-proxy configuration/templates
  backend/       container/runtime helpers
  frontend/      frontend delivery helpers after PR-010C
  gitlab/        GitLab CI implementation
  github/        GitHub CI helpers
```

The root CI discovery files are deliberately retained. The template's split
Compose units are adopted under `devops/`; MinIO remains an extra PAI service
because it is required for raw-document storage. PostgreSQL is upgraded from
17 to 18 only through a new volume and verified logical dump/restore.

## Authentication Boundary

PR-010B will add a local login adapter. The user presents username/email and a
password only to the login endpoint. A verified account receives a signed,
short-lived access token whose subject is the existing internal UUID. On each
protected request the identity adapter resolves that UUID through subject
persistence and then builds the existing `ActorContext`.

```text
login credentials → local verifier → signed JWT(actor UUID)
JWT → identity adapter → User + one active membership + roles → ActorContext
ActorContext → existing policy/delegation service
```

Authorization is never derived from client-provided roles, organization, or
JWT claims beyond actor identity. The header adapter is development/test-only;
non-development deployments must reject it.

There is no registration endpoint. An active administrator provisions users.
The first controlled deployment can create the initial administrator from a
required secret `PAI_BOOTSTRAP_ADMIN_PASSWORD`; normal operations use the
administrator provisioning API.

## Configuration and Failure Behavior

`PAI_BASE_PATH` defaults to `/pai` in integration deployment and is empty/root
locally. The proxy and frontend consume the same setting. Invalid base paths,
missing JWT signing key or bootstrap secret where bootstrap is enabled, invalid
or expired tokens, disabled users, invalid organization/membership state, and
identity persistence errors return the safe error contract and fail closed.

Configuration secrets are injected outside source control. They are redacted
from logs and excluded from audit metadata. AI/document privacy behavior does
not change.

## PR Breakdown

1. **PR-010A — Split Delivery & PostgreSQL 18**: template-aligned Compose,
   backend container, Redis/MinIO preservation, Nginx skeleton, migration
   runbook and compatibility checks.
2. **PR-010B — Redis/ARQ Dispatch & Cache**: ARQ worker dispatch retaining
   PostgreSQL domain-job ownership, safe cache/invalidation and reconciliation.
3. **PR-010C — Local Authentication**: bcrypt password verifier, PyJWT adapter,
   admin-only provisioning, controlled bootstrap and persistence/tests.
4. **PR-010D — Frontend & Mini-app Proxy**: Next.js/React/next-intl/Tailwind/
   Zod foundation, login shell and Nginx routing under the configured base path.

## Verification

Every PR runs backend formatting/lint/type/test, Alembic head/one-head checks,
Compose validation and secret scans. PR-010A proves backup, restore and schema
equivalence on a disposable PostgreSQL 18 volume. PR-010B proves idempotent
dispatch, reconciliation and Redis outage behavior. PR-010C adds negative
authentication and authorization tests. PR-010D builds the frontend and proves
Nginx base-path routing, API proxying and Swagger/OpenAPI behavior.
