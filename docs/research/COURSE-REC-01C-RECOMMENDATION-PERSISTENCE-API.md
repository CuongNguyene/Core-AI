# COURSE-REC-01C — Recommendation Persistence & API

Status: COMPLETE; production runtime migration/application remains a deployment gate, and LMS integration remains deferred.

## Boundary

This application milestone stores an already-resolved COURSE-REC-01B execution. It reuses the existing `RecommendationTarget`, `NormalizedCourseCandidate`, `CourseRecommendationRequest`, `CourseRecommendationResult`, and `CourseRecommendationEngine` contracts without changing 01B ranking or 3D governance semantics. The API structurally checks the supplied 3D-4/3D-5 projection pair and exact definition-pin joins. It does not establish governance authority; callers must supply projections resolved through the existing governed adapters.

Persistence is an immutable historical snapshot, not a governance registry. GET reads only the row. It never resolves current/latest packs, mappings, role profiles, course profiles, providers, or a model. There are no update, delete, list, search, rerun, refresh, or recompute routes.

## Routes and trust

- `POST /api/v1/course-recommendations` accepts an `IntegrationEnvelopeV1` containing `request_key`, a `GovernedRecommendationTargetProjection`, zero or more `GovernedCourseProjectionResult` values, and `max_results`.
- `GET /api/v1/course-recommendations/{recommendation_id}` returns the stored envelope.
- Both require the existing integration bearer key and signed actor context. Organization and actor are taken only from the verified server-side `ActorContext`; algorithm identity is server-owned.
- The creator may read within the same organization. A different actor is denied unless the verified actor has the existing `Role.ADMIN`; cross-organization lookups return not found.
- Initial POST returns 201; a same-key/same-fingerprint replay returns 200 and the original execution ID. A semantic mismatch returns `recommendation_idempotency_conflict`.

The idempotency scope is `(organization_ref, actor_ref, request_key)`. The SHA-256 fingerprint covers canonical JSON for the server-owned algorithm ID/version, exact effective 01B request, and minimized governance snapshot. It excludes timestamp, execution ID, request actor, and request key. Candidate records are ordered deterministically by `course_ref` before both fingerprinting and engine execution.

## Stored snapshot

The `course_recommendation_executions` table has a string `crx_…` primary key, scoped unique idempotency key, actor/organization UUIDs, algorithm identity, result kind, target/learning-need refs, immutable JSON request/result/governance snapshots, and UTC creation time. The complete serialized request + result + governance payload is limited to 1 MiB before insert.

The request snapshot is the exact effective 01B request: target, candidate facts actually passed to the engine, and prerequisite context. The result snapshot is the exact existing 01B result, including rank, decision details, warnings, result trace and the successful `NO_SUITABLE_COURSE` outcome when applicable.

The governance snapshot is explicitly versioned `1.0`. It stores role/gap/need identity and version refs, canonical refs and exact definition pins, target mapping/proposal/review/activation references and fingerprints, plus each course profile identity when the existing projection exposes one, canonical coverage, mapping fingerprints, source refs/source pins, resolution mode and warnings. Raw role requirements and gap entries are intentionally excluded. For ACTIVE 3D-5 projections the current adapter exposes `normalized_candidate` but not a profile ID/version; those fields remain null rather than being invented. The target-side adapter exposes source semantic refs and exact mapping fingerprints, but not a separate source pin value; no synthetic pin is added.

Provider/course candidate fields and provenance are persisted only as the bounded effective 01B input/output snapshot. Raw CVs, raw JDs, prompts, and provider package contents are not accepted as snapshot fields. No semantic registry tables or taxonomy data are added.

## Atomicity and history

Projection validation and the pure deterministic engine call happen before repository insert. Engine or validation failure leaves no row. SQL writes use one transaction. A unique-key race is recovered by reading the same organization/actor/key after rollback: equal fingerprints return the winner; changed fingerprints conflict; unrelated DB failures do not return success.

Records are immutable through this API and the read model is frozen. `NO_SUITABLE_COURSE` is persisted as a successful result. GET does not invoke the engine, model, provider, catalog, or governance resolver.

## Migration and verification

Migration `20261005_51` follows `20260929_50`, creates only the execution table/constraints/indexes, and has no backfill. SQLite migration tests exercise upgrade, schema inspection, scoped uniqueness and downgrade. `alembic heads` reports `20261005_51`.

The configured local PostgreSQL database was not migrated: its configured role is unavailable in this environment, and preflight could not read the current DB revision. Disposable SQLite migration verification passed. The full backend suite produced 1571 passes and one sandbox loopback-bind failure; rerunning that existing test with local socket permission passed. Scoped mypy reports only five existing `app/documents/safety.py` optional-writer errors; no changed source file reported a mypy finding. This is reported as verification evidence, not suppressed.

## Deferred

The later LMS bridge may consume this stable create/read contract. Persisting governance authority, bootstrap of production capability packs, catalog/provider integration, and any 3D/01B semantic changes are out of scope.
