# ADR-0025: Durable dispatch for course generation

## Status

Accepted.

## Context

`HierarchicalCourseGenerationService` currently creates an `asyncio` task in
the FastAPI process after persisting a generation plan. Process restart drops
that task; multiple API processes have separate in-memory job maps. This breaks
the durable job rule in ADR-0016 and risks duplicate model calls.

## Decision

- PostgreSQL remains the authoritative lifecycle store for generation plans,
  lesson tasks, runs and results. Redis/ARQ carries only opaque plan IDs.
- A generation plan gets a durable dispatch record containing plan ID, original
  actor ID, state, attempt/lease data and timestamps. Its claim is atomic in
  PostgreSQL; only the process holding the lease may generate lessons.
- API operations persist the plan/tasks and dispatch record before enqueueing an
  ARQ job. Broker failure leaves the record queued for reconciliation; the API
  never runs model inference inline.
- An ARQ worker loads the existing plan, resolves the stored actor from trusted
  persistence, claims the record, runs the existing lesson generator and marks
  the dispatch terminal or eligible for retry.
- Reconciliation re-enqueues queued or expired leased records. ARQ duplicate
  messages are harmless because a non-owner cannot claim the durable record.
- Queue payloads contain only the plan ID. No prompt, learner reference,
  document content, actor role or credential is serialized into Redis.

## Alternatives considered

- Leave `asyncio.create_task`: rejected because restart and multi-instance
  behavior are not durable.
- Redis-only job state: rejected by ADR-0016 because audit/lifecycle state
  would be non-authoritative.
- Database polling without ARQ: rejected because ADR-0016 selects Redis/ARQ as
  the dispatch provider.

## Migration

Add a dispatch table keyed by plan ID and an index for records eligible for
claim/reconciliation. Existing RUNNING plans are backfilled as queued so the
worker reconciliation path can resume them after deployment.
