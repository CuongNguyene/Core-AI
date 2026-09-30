# ADR-0016: Redis/ARQ Dispatch with Durable Domain Jobs

## Status

Accepted.

## Context

The adopted delivery template requires Redis and an ARQ worker. ADR-0005 chose
PostgreSQL polling because a queue provider had not been selected. PAI now has
extraction jobs whose state, retry metadata and audit trail are persisted in
PostgreSQL. Replacing them with ephemeral Redis payloads would lose the
evidence and audit guarantees required by the extraction boundary.

## Decision

- Redis 8 with authentication and AOF persistence provides the ARQ broker and
  cache infrastructure. It is not a primary datastore for PAI domain state.
- An API/service transaction first creates or changes a durable domain job in
  PostgreSQL. After commit it enqueues only the job UUID to ARQ. The ARQ task
  loads, claims and transitions the job using the existing repository.
- A missing, duplicate or delayed broker message is safe: an idempotent
  reconciliation command finds database jobs eligible for dispatch and
  re-enqueues their UUIDs. A task that cannot claim a job exits without calling
  a model.
- The worker continues to call ModelGateway and PrivacyGateway; ARQ does not
  give domain modules direct provider access.
- Cache entries are non-authoritative, have bounded TTLs, contain no raw
  CV/JD/prompt/answer/credential evidence, and are invalidated on the related
  mutation. Authorization and competency decisions never rely on cache-only
  state.
- Redis outage fails asynchronous enqueue safely and is recorded as a safe
  operational failure. It must not run extraction inline in an HTTP request or
  cause external-AI fallback.

## Alternatives considered

- Keep database polling forever: rejected because the delivery template and
  operational requirements now select Redis/ARQ.
- Make Redis the only job store: rejected because broker retention and retry do
  not satisfy PAI's durable lifecycle/audit requirement.
- Add Celery: rejected because the adopted template specifies async ARQ and the
  FastAPI stack is asynchronous.

## Consequences

- ADR-0005 is superseded only for worker dispatch. Its durable lifecycle,
  worker isolation, safe error and audit rules remain in force.
- PR-010B requires Redis integration tests, ARQ idempotency tests, broker-outage
  tests and a reconciliation test.
- Production Redis HA, backup and retention still require a later infrastructure
  decision; this ADR establishes the application boundary and local/integration
  stack.

## Migration

Existing queued jobs remain in PostgreSQL. The deployment runs reconciliation
after worker rollout so they are dispatched to ARQ. No raw document, prompt,
model output or actor mapping is migrated to Redis.
