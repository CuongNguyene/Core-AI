# PAI-CANDIDATE-INPUT-01C — Structured Evidence & Candidate Source Ingestion

Status: **COMPLETE**
Repository: Core-AI, `feat/deterministic-ai-course-planning-workspace`
Scope: HRM full-snapshot ingestion foundation; no capability-analysis behavior changes.

## Confirmed upstream semantics

- HRM Employee `name` is the unique employee identifier used as `employee_ref`.
- ATS → HRM delivery uses **FULL SNAPSHOT** semantics. A later accepted snapshot is a complete source state; absent records are not current in that state, while prior snapshots remain retained.
- HRM `company` is currently a string; HRM `department` is currently a string.
- `company` resolves a Core-AI organization only through an explicit server-side exact mapping `(source_system, external_company_ref) → organization_id`.
- `department` is contextual source data only and never participates in organization/tenant resolution.
- Core-AI continues to own the Candidate UUID; email, display name, phone and department are not identity keys.

## Known V1 organization limitation

HRM exposes `company` as a string rather than an immutable upstream company ID. A rename therefore requires explicit mapping administration. No implicit aliasing, fuzzy match or historical rename inference is implemented.

## Implemented foundations

- Strict `pai.candidate-source` v1 input models with source-only interview, assessment, language, tools and optional ATS scanning fields.
- Deterministic exact organization mapping and an admin-scoped integration API to add mappings.
- Signed-actor + integration-key protected snapshot endpoint. It enforces actor organization scope before creating/resolving a Candidate.
- External employee identity uniqueness by `(organization_id, source_system, employee_ref)`; HRM employee replay resolves to the same Candidate.
- Immutable snapshot payload/fingerprint storage and document-free structured evidence with source record/field path, snapshot, source version and source timestamp lineage.
- At the original 01C implementation, the first snapshot became the baseline current snapshot and identical full-payload fingerprints replayed; changed snapshots were retained as `ORDER_UNRESOLVED` pending a trustworthy upstream ordering field. This behavior was superseded by 01C.2 below.
- Deterministic projection into existing `CandidateProfile` employment, education, credential and project entity shapes. Tools/languages/interview/assessment/ATS scanning remain source-layer-only; no claims, capability levels, gaps or readiness are created.
- Alembic revision `20261006_52` adds organization mapping, external employee identity, immutable snapshots and structured evidence; legacy document evidence tables are untouched.

## Historical source ordering gate (01C)

The 01B contract and repository evidence identify `source_updated_at` as optional/proposed and state that a timestamp alone does not define ordering/replay semantics. No HRM payload contract in this repository confirms a monotonic version or authoritative modified timestamp. Therefore this implementation does **not** classify changed snapshots as newer, older, or equal-time conflicts, and never uses ingestion time or fingerprint as ordering. Changed snapshots receive HTTP 202 and `ORDER_UNRESOLVED`; they are retained but not promoted.

At the time 01C was implemented, upstream had not confirmed a source ordering field, so changed payloads could not truthfully be ordered. 01C.2 now implements the explicitly approved HRM projection assumption below. HRM producer implementation remains a separate dependency and is not claimed as complete.

## 01C.2 — Source Revision Ordering & Runtime Completion (2026-10-06)

### Upstream contract assumption and internal mapping

- The external contract remains **HRM → PAI Learning Projection v1**, a reduced PAI-specific **FULL SNAPSHOT** payload.
- The upstream ordering field is `snapshot.source_revision`, required as a positive integer and monotonically increasing per external employee. This is an approved integration assumption pending HRM producer implementation; the HRM producer is not part of this milestone.
- The API/OpenAPI transport preserves that nested field. `CandidateSourceProjectionV1.to_candidate_source_envelope()` explicitly maps `snapshot.source_revision` → internal `CandidateSourceEnvelope.source_revision`; `snapshot.source_updated_at`, `source_version`, and `source_snapshot_ref` map to internal `source_snapshot` audit metadata. The external projection schema is not silently redefined as a top-level revision.
- `source_updated_at`, ingestion time, and either fingerprint are never ordering authorities.

### Revision ordering matrix

| Current state | Incoming state | Result |
|---|---|---|
| No current pointer | Any valid positive revision | Accept as baseline; persist snapshot/evidence and promote |
| Current revision C | R > C | Accept and atomically promote; retain history |
| Current revision C | R < C | `candidate_source_snapshot_stale` / HTTP 409; no persistence or pointer mutation |
| Current revision C | R = C, same content fingerprint | Replay existing snapshot / HTTP 200; no duplicate evidence or pointer mutation |
| Current revision C | R = C, different content fingerprint | `candidate_source_snapshot_revision_conflict` / HTTP 409; no persistence or pointer mutation |
| Current revision C | R > C, same content fingerprint | Accept a distinct revisioned snapshot and promote |
| Current pointer has no trustworthy revision | Any incoming revision | `candidate_source_current_revision_unavailable` / HTTP 409; fail closed, no backfill/inference |

The legacy `fingerprint` remains the deterministic full-envelope/audit hash. A separate non-unique `content_fingerprint` excludes `source_revision` and `source_snapshot` audit metadata and is only compared when revisions are equal. Historical fingerprints and revision values are not rewritten or fabricated.

### Persistence, full-snapshot, and concurrency behavior

- Alembic revision `20261006_53` follows `20261006_52` without editing it. It adds nullable historical `source_revision` and `content_fingerprint`, plus the snapshot→external identity FK and unique `(external_identity_id, source_revision)` invariant. Revision values are constrained positive when present; legacy revisions remain NULL.
- Before backfilling the FK, migration 53 counts identity matches using the exact existing tuple `(candidate_id, organization_id, source_system, employee_ref)`. Any snapshot with zero or multiple matches aborts migration. It does not guess or derive a revision.
- `current_snapshot_id` is the canonical current pointer. Every accepted revision stores its complete source payload and revision-specific structured evidence; omitted/empty collections in a newer full snapshot do not inherit prior evidence. Prior snapshots/evidence remain historical.
- Existing identity rows are selected `FOR UPDATE`; a concurrent first identity insert is retried only after the named external-identity uniqueness race, with the entire failed transaction rolled back. Snapshot insertion is flushed before changing the identity pointer to satisfy the existing circular FK boundary on PostgreSQL.
- PostgreSQL race tests use separate sessions for same-revision/same-content, same-revision/different-content, and rev2/rev3. On 2026-10-06, all three scenarios passed against an isolated temporary PostgreSQL cluster; this is not the canonical runtime DB.

### API behavior and regression boundary

- Existing `/api/v1/candidate-sources/snapshots` route, `IntegrationEnvelopeV1`, integration API-key dependency, signed actor context, writer roles, and exact organization scope remain in place.
- New acceptance returns 201; replay returns 200; stale, equal-revision conflict, and legacy current-without-revision return 409. Valid revisioned HRM input no longer returns 202/`ORDER_UNRESOLVED`.
- Organization mapping, employee identity, CandidateProfile-compatible projection, structured evidence, document/CV evidence, ATS scoring, capability semantics, and recommendation logic are unchanged.

### Verification and runtime status

- Focused candidate-source suite: **21 passed**, including three PostgreSQL concurrency races.
- Full backend suite: **1,593 passed**.
- Ruff on touched Python files: **pass**.
- Migration upgrade/backfill/fail-closed/downgrade tests: **4 passed**; Alembic has one head, `20261006_53`.
- OpenAPI tests confirm the external request requires `snapshot.source_revision` and does not expose an internal top-level field.
- Canonical runtime: host Alembic had been loading `backend/.env` against host PostgreSQL at `localhost:5432`, whose credentials differ from the PAI Compose DB. The actual PAI PostgreSQL is the healthy Compose `postgres` service (host-published port `15433`; backend container uses `postgres:5432` and Compose-managed credentials). Using the Compose backend environment, read-only inspection observed `20260929_50`; normal `alembic upgrade head` applied `20261005_51`, `20261006_52`, and `20261006_53`. Post-upgrade smoke confirmed head `20261006_53`, all four candidate-source tables, required FK/check/unique constraints, and zero identity-link violations. The current-source backend image was rebuilt and its service recreated; `/health/ready` returned HTTP 200 and its OpenAPI exposes both candidate-source routes. No secret values were printed or modified.

### Remaining limitation

The Core-AI contract, ordering, migration, and local runtime verification are complete. The upstream HRM producer must implement the agreed `snapshot.source_revision` contract before integration traffic can use this path.

## Verification

Focused tests cover exact mapping/fail-closed resolution, canonical fingerprint behavior, replay and ordering refusal, deterministic profile projection, source-only fields, SQL persistence/idempotency/history, and migration upgrade/downgrade. Broader existing CV/document/evidence/capability tests are reported separately in the implementation handoff. Runtime Alembic upgrade and schema/API readiness smoke are recorded in the 01C.2 evidence bundle.

## 01C.3 — Learning Projection Transport Alignment (2026-10-06)

Status: **COMPLETE_WITH_PRE_EXISTING_WORKTREE_BLOCKER**. New ingress code,
contract, full regression and runtime flow are verified. The unrelated
repository-wide lint and pre-existing mapping administration API limitations
below remain, without opportunistic repairs.

### Why a dedicated ingress

LMS bridge PAI-LMS-CANDIDATE-BRIDGE-01 stopped with
`BLOCKED_BY_CORE_TRANSPORT_CONTRACT`: the old strict candidate-source DTO could
not retain frozen employment, target-job and auxiliary projection fields.
01C.2 solved revision ordering, not this complete external schema mismatch.

New endpoint: **POST `/api/v1/candidate-sources/learning-projections`**.
Request: `{"schema_version":"v1","data": <EmployeeLearningProjectionV1>}`.
The outer IntegrationEnvelopeV1 version is distinct from the inner
`schema_id="pai.employee-learning-projection"`, `schema_version="1.0"`.
Existing `/api/v1/candidate-sources/snapshots` remains compatible with its
`pai.candidate-source` / `v1` contract. Core, not LMS, owns the adapter.

### Frozen validation and exact mapping

| External field | Internal ingestion / source storage |
|---|---|
| `identity.employee_ref`, `identity.source_system` | Internal employee identity; source system exactly HRM; employee ref nonblank |
| `snapshot.source_revision` | Explicitly maps to `CandidateSourceEnvelope.source_revision`; strict positive integer |
| `snapshot.source_updated_at` | Optional `source_snapshot.source_updated_at`, audit-only |
| `employment_context.company` | `envelope.company`; exact `(HRM, company)` organization mapping, never signed actor override |
| `employment_context.department` | Existing internal department plus preserved external context |
| `candidate_source` | Existing career/education/language/tool/certification/project records; all six full collections required |
| `recruitment_evidence.interviewer_feedback` | Existing internal interviews; required collection |
| `recruitment_evidence.assessments` | Existing internal assessments; required collection |
| Full `employment_context` | Complete immutable external source JSON and structured source paths |
| Full `target_job_source` | Complete immutable source JSON; no semantic adapter destination |
| Full `auxiliary_signals` | Complete immutable source JSON; scanning also maps to existing internal source-only signal |

Employment requires nonblank company; department, job_title, designation_label,
grade_label and date_of_joining are optional/nullable source strings. Target-job
object is optional/nullable; source_application_ref is an optional string, and
HTML description/requirements and posting URL are transported unchanged.
Auxiliary object/fields are optional/nullable. Current application AI score
supports source numeric/string values without interpretation; scanning reuses
the existing typed ATSScanningSignal. Recruitment timestamps accept ISO strings
over HTTP without weakening the strict record models.

The integration owner explicitly froze **`AtsAiProfileV1`** during 01C.3:
`cv_match_score: float|null`, `verified_by_recruiter: bool|null`,
`verified_by: str|null`, `verified_at: datetime|null`, `summary: str|null`.
All five fields are optional/nullable; the object is optional/nullable and
strict. No string/object union or arbitrary JSON bag is accepted. Unknown
fields, including full-HR bank/payroll/salary/identity/family structures and
payload actor/org overrides, are rejected at every typed nesting level.

### Persistence, equality and semantic boundary

**NO_MIGRATION_REQUIRED**: existing `candidate_source_snapshots.payload` JSON
durably retains the complete accepted external projection, with external
schema markers; no new table/column or CandidateProfile field. Serialization
preserves supplied-versus-omitted/null fields, UTF-8, HTML, child order and
source values; datetimes receive canonical ISO serialization. Full fixture
round-trips exactly after canonical serialization, both SQLite and PostgreSQL.
Existing generic structured-source evidence retains paths into that same full
projection. Nothing is converted into Document/CV offsets or fabricated IDs.

Responsibilities is retained in career source records. Technologies and
project_achievements are absent/rejected by the new external DTO; the legacy
route's existing fields are untouched for compatibility. Employment title,
designation and grade do not become Roles/levels. Target-job source does not
create Role/JD/profile objects or trigger extraction. AI score, profile summary,
recruiter verification and scanning remain source-only; no capability claim,
verification, gap, readiness, learning-need or ranking inference.

Both routes share `_ingest_source` API behavior and the same repository
transaction/unique-identity retry machinery. 01C.2 revision ordering is unchanged:
baseline/newer 201, equal content replay 200, stale/conflict 409. Higher revision
with identical content creates a distinct immutable snapshot. Audit fingerprint
includes the complete projection; logical fingerprint excludes only nested
snapshot revision/audit timestamp. All five source sections participate in
same-revision equality. Changing only source_updated_at replays the original
snapshot; audit-only retry metadata does not rewrite immutable history.
Do not switch between old/new schema shapes as same-revision retries: changing
the contract shape changes logical content and requires a new upstream revision.

### Security and errors

Reuses integration bearer API key, signed Ed25519 actor, durable nonce protection,
trusted persisted ADMIN/REVIEWER roles, exact company mapping and organization
equality. Projection cannot supply actor/organization/credentials/headers.
Errors retain Integration API correlation conventions: validation 422,
missing mapping 404, org/writer mismatch 403, signing/auth 401 or existing 403,
stale/revision/current-unavailable conflicts 409, repository unavailable 503.
No new raw-body or secret logging is added. No LMS/HRM/ATS/frontend changes.

### Verification and runtime

- TDD RED observed for missing external DTO, JSON recruitment timestamps, and
  object ATS profile; then GREEN after the respective implementations.
- New transport tests: **55 passed**. New PostgreSQL transport concurrency test:
  **1 passed**, exercising duplicate identity retry/replay/context conflict and
  concurrent higher revisions.
- Existing candidate-source regressions: **21 passed**. Combined focused suite:
  **77 passed**, including PostgreSQL; existing migration tests included.
- Full backend: **1,649 passed**, zero skipped, with isolated PostgreSQL enabled.
  Includes candidate, CV/document evidence, extraction, signed actor, capability
  and JD regression suites. Initial sandbox-only ClamAV socket bind failure was
  resolved by running the same suite with loopback permission, not by code edits.
- Ruff on all 01C.3 Python files: **PASS**. Repository-wide Ruff: **15 pre-existing
  errors in unrelated files**, left unchanged (including prior migration 52).
- Mypy on ingress schemas/API: **PASS**. Repository check retains **4 pre-existing
  errors** in the old replay Optional narrowing and untyped source-value walker;
  no new adapter type errors remain. Those foundation statements were not repaired.
- Alembic: **one head `20261006_53`**, no new migration. Actual Compose runtime
  inspection independently confirmed the same revision; no upgrade was needed.
- OpenAPI: new ingress, strict ATS object and required nested source_revision
  exposed; old snapshot route retained. API tests also use a real Ed25519 signer.
- Independent read-only review: no Critical/Important findings; 28 additional
  in-memory schema checks passed. Its single minor concurrency test-hardening
  finding was addressed: concurrent revision results now permit only success or
  the explicit stale error, never arbitrary discarded exceptions.
- Rebuilt/recreated only the local backend service. Readiness HTTP 200. Real
  signed HTTP ingestion through port 18000 returned **201,200,201,409,409** for
  baseline/replay/newer/stale/conflict. SQL inspection proved exactly two full
  projections, identical content fingerprints across revisions 1/2 and current
  pointer at revision 2. Runtime source JSON exactly equals submitted fixtures.
- After the final typing refinement, rebuilt/recreated the backend again and
  reverified signed revision-2 replay plus both stored payloads using the retained
  smoke marker; **PASS**, no additional candidate/source rows created.

### Pre-existing blockers and remaining limitations

`PRE_EXISTING_WORKTREE_BLOCKER` (outside 01C.3): full-backend Ruff has 15 unrelated
lint errors; global `git diff --check` flags existing CRLF whitespace in
`app/documents/repository.py`. Neither was normalized or repaired.
The existing organization-mapping POST DTO rejects JSON UUID strings with 422
under strict validation. Smoke recorded this failure and seeded only its unique
synthetic mapping through the existing server repository; the **new ingress
itself was fully authenticated and live-verified**, not dependency-overridden.
Mapping administration API repair is separate work, not a security bypass in
production ingestion.

Runtime smoke retained synthetic candidate
`0a6b9131-3444-4124-9902-926ead67df46`, mapping
`c9be1cb8-a65e-445a-b2cd-65e70e792b55`, employee
`01C3-SMOKE-8f5bb1db122247ffb0496ad5d00c1a25`, two snapshots and associated
source evidence for audit. No real employee data or credentials were changed.
Test-only PostgreSQL schemas were cleaned up and temporary cluster stopped.

LMS bridge may resume against `/learning-projections` using the frozen external
DTO and outer envelope. It still must enforce trusted integration actor scope
and use governed exact organization mapping. HRM producer and real LMS→Core E2E
are not delivered here. **LMS transports; Core owns candidate source state and
semantics. Transport now, semantic activation later.** No commit or push.
