# ADR-0015: Mini-app Integration, Local Authentication and Template-aligned Delivery

## Status

Accepted.

## Context

PAI Platform will be integrated as a mini-app in a larger system. The project
already has a safe hybrid repository layout (`backend/`, `frontend/`, and
`devops/`), a modular-monolith domain core, a PostgreSQL-backed worker, and a
development-only UUID header identity adapter. The organization has selected
local password authentication with JWT for this integration phase; it does not
need SSO. Accounts must be created and provisioned by an administrator, not by
self-registration.

The CTPAI template is now the target delivery scaffold: split DevOps Compose,
Redis, ARQ worker, local JWT/password authentication, a Next.js frontend and
Nginx routing. PAI must adopt those capabilities without replacing existing
domain migrations, privacy controls, evidence/assessment boundaries or trusted
authorization semantics.

## Decision

- PAI remains a FastAPI modular monolith. Redis and ARQ are adopted as the
  template's asynchronous dispatch stack under ADR-0016; this is not a move to
  microservices. PostgreSQL remains the durable owner of domain job lifecycle,
  idempotency, audit and retry state.
- PAI is deployable behind a reverse proxy as a mini-app at a configurable base
  path. The deployment default is `/pai`; the application must also support a
  root deployment for local development. Proxy routing and the frontend base
  path use the same configured value.
- The repository keeps its hybrid layout. `backend/` owns the monolith and
  migrations; `frontend/` will own the selected UI only after its own approved
  spec; `devops/` owns compose, proxy, container and CI implementation. Root
  `.gitlab-ci.yml` and `.github/workflows/ci.yml` remain host-discovery
  entrypoints.
- Delivery configuration will adopt the template's split Compose structure for
  database, Redis, backend/worker, frontend and Nginx. The existing single
  local Compose definition remains supported until an equivalent split stack is
  verified. MinIO remains part of the split stack because ADR-0014 requires it
  for restricted document storage. PostgreSQL 18 is introduced only through a
  logical dump/restore migration; no existing PostgreSQL 17 volume is reused.
- Local authentication uses a password verifier and signed, short-lived JWT
  access token. Password hashes, signing keys and bootstrap passwords are
  configuration secrets and must never be committed, logged or returned by an
  API. Password hashing and JWT details are implemented in PR-010B, not this
  delivery-layout PR.
- There is no public registration, password reset, OAuth/OIDC, refresh-token,
  SSO, MFA or multi-organization context selection in this scope. An active
  administrator provisions a user, their one active organization membership,
  role assignments and initial password. `PAI_BOOTSTRAP_ADMIN_PASSWORD` may
  bootstrap only the first administrator in a controlled deployment; it must
  be required from secret configuration, consumed safely and rotated/removed
  operationally after bootstrap.
- JWT establishes only the internal actor UUID. Every request still resolves
  the user, one active membership, organization status, role assignments and
  scoped delegation from trusted persistence. A token, request body, or header
  never supplies role or organization authority. Disabled users, inactive
  organizations, missing/multiple memberships, invalid/expired tokens and
  unavailable identity persistence fail closed.
- The development `X-PAI-Actor-ID` adapter remains limited to development/test
  compatibility until PR-010B explicitly gates it. It must not be available in
  an integration or production deployment profile.

## Alternatives considered

- Copy template source files without mapping them to PAI: rejected because that
  would discard accepted PAI domain/migration/security decisions. The template
  capability set is adopted through the migration plan instead.
- Keep the current scaffold indefinitely: rejected because it lacks a defined
  mini-app delivery and local authentication path.
- Introduce SSO/OIDC now: rejected by product decision; it can replace the
  local login adapter later while retaining UUID, persistence and authorization
  semantics.
- Let JWT carry roles or organization claims as authority: rejected because
  revocation, membership and scoped-delegation changes would not fail closed.

## Consequences

- PR-010A adds split delivery configuration, container boundaries and a
  PostgreSQL 17-to-18 logical migration runbook/test. It does not alter domain
  tables or API behavior.
- PR-010B adds Redis/ARQ dispatch while retaining durable database job state,
  plus a safe cache use with invalidation.
- PR-010C adds local JWT/password authentication and administrator provisioning
  with migration, authorization tests and a controlled development bootstrap.
- PR-010D adds the frontend foundation and Nginx mini-app routing after the
  previous slices pass their integration checks.
- Existing evidence, matching, assessment, learning and credential boundaries
  remain unchanged. In particular, all model calls continue to use
  ModelGateway and PrivacyGateway.

## Migration

PR-010A migrates only local/integration PostgreSQL infrastructure through a
tested logical dump/restore to a new PostgreSQL 18 volume; it does not mutate
domain schema. PR-010C requires an explicit migration for password-verifier
and credential/session fields, if any, and must not infer passwords or map
legacy string actors. Existing development fixture identities remain UUID-based.
