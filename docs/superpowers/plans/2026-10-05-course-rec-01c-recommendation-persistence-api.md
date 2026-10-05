# COURSE-REC-01C Recommendation Persistence & API Implementation Plan

> **For agentic workers:** Execute inline in the canonical Core-AI checkout. Follow TDD for each behavior. This milestone explicitly forbids commit and push.

**Goal:** Persist immutable, idempotent recommendation executions and expose authenticated create/read APIs that return exact historical snapshots without recomputation.

**Architecture:** Reuse the existing COURSE-REC-01B request/result schemas and engine, with structurally validated 3D-4/3D-5 projections as already-resolved inputs. Persist one SQLAlchemy execution row containing deterministic request, result and minimized governance JSON snapshots; read paths use only that row. Add a small FastAPI integration router using the existing bearer-key, signed actor, envelope and APIError conventions.

**Tech Stack:** Python 3.13, Pydantic, FastAPI, SQLAlchemy async, Alembic, PostgreSQL/SQLite test fixtures, pytest, Ruff, mypy.

**Spec:** /Users/mac/.codex/attachments/e1db7989-7d06-43f3-ae9e-d18dd26cf33a/Pasted text.txt

## Global Constraints

- Do NOT redesign recommendation semantics, capability governance, or ranking logic.
- Do NOT modify LMS, 3D domain semantics, or COURSE-REC-01B ranking files.
- Do NOT implement taxonomy migration or governance-authority persistence.
- Persist an immutable snapshot of the resolved execution; historical GET must not rerun 01B or resolve latest state.
- Use existing SQLAlchemy async, Alembic, integration auth, actor-context, envelope, and error conventions.
- Add no update, delete, list, search, rerun, refresh, or recompute API.
- Do NOT persist raw CV, raw JD, prompt text, or raw provider package content.
- Do NOT commit or push.
- Preserve all four pre-existing untracked artifacts in the Core-AI checkout.

## Review Focus

- Cross-organization or non-owner reads must be denied; test a different actor in the same and another organization, and the existing organization-admin convention.
- A target projection with mismatched target refs, need/requirement lineage, bindings, pins, or mappings must fail before persistence; mutate one field at a time in tests.
- A course projection with a DRAFT profile, absent normalized candidate, mismatched coverage, non-current mapping trace, or inconsistent definition pin must fail before persistence.
- Reusing an idempotency key concurrently or with changed semantics must not create a second row or disclose another actor's record; test same-key replay and a conflicting payload.
- Historical GET after current authority changes must return byte-equivalent semantic JSON and must not call the engine, current resolver, provider, or catalog.

---

### Task 1: Snapshot contracts and projection consistency

**Files:**
- Create: services/pai-backend/backend/app/course_recommendation/execution_schemas.py
- Create: services/pai-backend/backend/app/course_recommendation/execution_snapshots.py
- Test: services/pai-backend/backend/tests/test_course_recommendation_execution_snapshots.py

**Interfaces:**
- Consumes GovernedRecommendationTargetProjection, GovernedCourseProjectionResult, CourseRecommendationRequest, CourseRecommendationCandidate, and existing 01B result schemas.
- Produces typed immutable execution request/result/governance snapshot models, build_execution_snapshots(...), and deterministic request_fingerprint(...).
- Snapshot schema version is 1.0; algorithm ID/version come from CourseRecommendationEngine.

- [ ] Step 1: Write failing tests for target/provenance equality, exact definition-pin join, ACTIVE-only candidate inclusion, candidate coverage equality, privacy-minimized governance fields, JSON round-trip, stable fingerprint, and candidate-order canonicalization.
- [ ] Step 2: Run focused tests with uv run pytest tests/test_course_recommendation_execution_snapshots.py -q; confirm failures are missing contracts/validation.
- [ ] Step 3: Implement immutable snapshot schemas/builders. Derive the 01B request only from projection outputs; preserve exact request/result inputs; store target and course IDs/pins/fingerprints/proposal-review-activation refs/source pins, but exclude raw role requirement and gap entries. Reject any target/course capability join with unequal CapabilityDefinitionPin. Bound canonical serialized snapshots to 1 MiB.
- [ ] Step 4: Verify focused tests pass and malformed/ineligible projections fail with stable RecommendationSnapshotInconsistent errors.

### Task 2: SQLAlchemy execution model and idempotent repository

**Files:**
- Create: services/pai-backend/backend/app/course_recommendation/models.py
- Create: services/pai-backend/backend/app/course_recommendation/repository.py
- Create: services/pai-backend/backend/alembic/versions/20261005_51_course_recommendation_executions.py
- Test: services/pai-backend/backend/tests/test_course_recommendation_execution_repository.py
- Modify: services/pai-backend/backend/tests/test_migration_config.py

**Interfaces:**
- Produces CourseRecommendationExecutionRecord, immutable read model, SqlAlchemyCourseRecommendationExecutionRepository.create_or_get(...), and get(...).
- Idempotency scope is (organization_ref, actor_ref, request_key); a matching fingerprint returns the existing record, a different fingerprint raises a typed conflict.

- [ ] Step 1: Write failing repository tests for create/read JSON round-trip, unique scoped key, same-key/same-fingerprint replay, same-key/different-fingerprint conflict, and integrity-error race recovery.
- [ ] Step 2: Run focused repository tests and verify they fail because the table/repository do not exist.
- [ ] Step 3: Implement one append-only execution table with UUID organization/actor refs; string ID, request key/fingerprint, snapshot version, algorithm identity, result kind, target and need refs, three JSON snapshots, and created timestamp. Add only PK and the scoped idempotency unique constraint plus indexes needed for organization/actor lookup.
- [ ] Step 4: Add one additive Alembic migration after 20260929_50; no backfill or governance table changes. Preserve the existing async session/transaction pattern and handle unique races by re-reading the scoped key after rollback.
- [ ] Step 5: Verify repository tests and migration graph (uv run alembic heads, migration-configuration test).

### Task 3: Execution service and immutable historical read

**Files:**
- Create: services/pai-backend/backend/app/course_recommendation/execution_service.py
- Test: services/pai-backend/backend/tests/test_course_recommendation_execution_service.py

**Interfaces:**
- Produces CourseRecommendationExecutionService.execute(...) and .get(...).
- The service builds snapshots, invokes CourseRecommendationEngine.recommend(...) exactly once, persists atomically, and returns the immutable execution/read result. GET only reads the repository.

- [ ] Step 1: Write failing tests for happy path, NO_SUITABLE_COURSE success, multi-capability preservation, actor/organization provenance, engine failure leaves no row, persistence failure is not reported as success, and GET after changed authority returns the original snapshot without engine/resolver calls.
- [ ] Step 2: Run focused tests and verify the missing service behavior is the failure.
- [ ] Step 3: Implement service composition with server-owned engine identity; never accept algorithm identity from the caller. Do not call current mapping/pack resolvers, providers, or catalog on GET.
- [ ] Step 4: Verify focused tests and existing 01B tests pass.

### Task 4: Authenticated POST/GET integration API

**Files:**
- Create: services/pai-backend/backend/app/integration/course_recommendation_schemas.py
- Create: services/pai-backend/backend/app/integration/course_recommendation_api.py
- Modify: services/pai-backend/backend/app/main.py
- Test: services/pai-backend/backend/tests/test_course_recommendation_api.py

**Interfaces:**
- POST /api/v1/course-recommendations accepts IntegrationEnvelopeV1[CourseRecommendationExecutionCreateV1], requires bearer integration auth and signed actor context, and returns the existing envelope with the immutable read model.
- GET /api/v1/course-recommendations/{recommendation_id} uses the same auth, returns the stored read model, and never computes or resolves governance.
- GET ownership is creator-only within the same organization, except the existing Role.ADMIN convention; organization is always checked.

- [ ] Step 1: Write failing API tests for auth, signed actor, envelope, create/replay status, GET round-trip, 404, validation, conflict, inconsistent projection, owner/admin/other-org access, and no engine logic in transport.
- [ ] Step 2: Run focused API tests and confirm route/service registration is absent.
- [ ] Step 3: Implement strict transport schemas, route error mapping, service wiring, and router inclusion. Body cannot supply actor/organization or algorithm identity. Use request key from the bounded DTO; return 201 on creation and 200 on idempotent replay.
- [ ] Step 4: Verify API tests plus existing integration API/auth tests.

### Task 5: Migration verification, docs, evidence, final regression

**Files:**
- Create: docs/research/COURSE-REC-01C-RECOMMENDATION-PERSISTENCE-API.md
- Create: test/results/course-rec-01c/*.json
- Tests: focused persistence/API/migration tests and full backend regression.

- [ ] Step 1: Add migration tests that verify table, columns, JSON type, indexes and unique idempotency constraint; run upgrade/downgrade using the repository-supported disposable test database. Do not migrate a production database.
- [ ] Step 2: Add evidence artifacts for preflight, schema, snapshot, fingerprint, idempotency, provenance, API/auth, historical read, migration, regression, static checks and summary; no secrets or runtime data.
- [ ] Step 3: Document exact POST/GET, trust boundary, idempotency, ownership, schema versioning, historical behavior, migration, privacy, constraints, and deferred LMS bridge.
- [ ] Step 4: Run full backend pytest, Ruff format/check, mypy on changed scope, Alembic heads/current as environment permits, JSON/whitespace/secret scans, git diff --check, and verify Core-AI has no staged changes/commit/push while LMS remains unchanged.

## Execution Notes

- The canonical checkout is a normal Git checkout, not a linked worktree; direct modification was selected to keep uncommitted results visible in the canonical repository. Four pre-existing untracked items remain outside this plan.
- The configured DB is PostgreSQL on localhost. Sandbox denied the read-only alembic current socket connection during preflight; record this as an environment limitation unless an approved read-only elevated check or disposable migration test is available.
- Do not commit or push at any task boundary or at completion.

## Self-Review

- Spec coverage: the five tasks cover persistence, snapshots, fingerprint/idempotency, engine execution, auth/API, ownership, migration, historical immutability, privacy, docs/evidence, and final checks.
- Domain/ranking files remain untouched; algorithm identity is server-owned; reads do not re-resolve current governance.
- Review-focus failure inputs each have focused tests in Tasks 1–4.
- Migration/runtime distinction: prefer disposable/test DB migration verification; do not mutate the local configured runtime DB merely to satisfy a test.
