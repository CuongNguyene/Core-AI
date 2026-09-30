# Preview Capability Snapshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist a deterministic, explicitly provisional capability-gap portfolio with context-safe evidence assessment, a verification queue, and preview-readiness metadata.

**Architecture:** Extend the immutable capability-gap snapshot with derived `preview_readiness` and `verification_queue` data. Evidence matching remains deterministic and source-backed: work is stronger than mention, project usage can support generic requirements, and production eligibility requires explicit production-context evidence. A migration persists both snapshot fields as JSON on the portfolio record; no new competency decisions or learning records are created.

For legacy accepted CV profiles, capability analysis builds an in-memory
`EvidenceIndex` from `CVExtractionOutput` whenever raw accepted claims are
present. This is the source of truth for `evidence_type`, source locator and
context; the persisted `CandidateProfile` is only a fallback for graph-only
profiles. The index is not persisted back to, or used to mutate, the accepted
extraction profile.

**Tech Stack:** Python 3.13, Pydantic, SQLAlchemy async, Alembic, pytest.

## Global Constraints

- PREVIEW only; do not implement or invoke OFFICIAL analysis.
- Do not create VERIFIED capability status, final competency decisions, combined/final readiness scores, future-track combination, learning objectives, or learning paths.
- Do not infer or write missing JD modality, target level, observable behavior, or evidence constraints.
- A requirement is production-bound only when its supplied evidence terms explicitly contain a production signal.
- Retrieval and eligibility are separate. Each assessment records
  `retrieved_candidate_count` and `eligible_candidate_count`; a production
  context mismatch may therefore have retrieved evidence but zero eligible
  evidence.
- Missing evidence is `not_found_in_evidence` or `insufficient`; it never proves employee capability absence.
- A PREVIEW gap with `evidence_status=not_found_in_evidence`, `insufficient`, or `context_mismatch` is an **evidence gap**, not a capability gap. Downstream systems must retain that distinction and must not count it as a confirmed capability deficit.
- Missing target level does not create a level gap.
- All snapshots are deterministic for identical accepted CV, role profile, and policy version inputs.

---

### Task 1: Evidence-strength and production eligibility rules

**Files:**
- Modify: `backend/app/capability_analysis/schemas.py`
- Modify: `backend/app/capability_analysis/rules.py`
- Modify: `backend/tests/test_capability_analysis_rules.py`

**Interfaces:**
- Produces `EvidenceStrength`, `AssessmentEvidenceStatus`, and deterministic requirement assessment metadata.
- Consumes `EvidenceContext` and supplied `RoleRequirement.evidence_terms` only.

- [ ] Write failing tests for: work over mention; mention requiring verification; project usage supporting generic requirements; project and non-production work rejected for explicit production requirements; explicit production work accepted; and no inferred production constraint for generic requirements.
- [ ] Run `UV_CACHE_DIR=/private/tmp/pai-uv-cache uv run pytest tests/test_capability_analysis_rules.py -q` and confirm RED.
- [ ] Implement source-context ranking and explicit lexical production eligibility without populating any RoleRequirement field.
- [ ] Add tests that missing target level creates no level gap, and missing evidence returns `not_found_in_evidence`/`insufficient` without absence language.
- [ ] Run the focused rules suite and confirm GREEN.

### Task 2: Versioned PREVIEW readiness and verification queue snapshot

**Files:**
- Modify: `backend/app/capability_analysis/schemas.py`
- Modify: `backend/app/capability_analysis/rules.py`
- Modify: `backend/app/capability_analysis/service.py`
- Modify: `backend/tests/test_capability_analysis_rules.py`
- Modify: `backend/tests/test_capability_analysis_api.py`

**Interfaces:**
- Produces `PreviewReadiness` with `analysis_mode=preview`, `final_decision_prohibited=true`, and provisional verification only.
- Produces `VerificationQueueItem` whose status is only `pending` or `recommended`.

- [ ] Write failing tests asserting every preview snapshot contains explicit readiness, has no combined score, and queue items never use `verified`.
- [ ] Run the focused API/rules tests and confirm RED.
- [ ] Implement deterministic queue derivation from incomplete/conflicting assessments and a PREVIEW-only readiness snapshot.
- [ ] Run focused API/rules tests and confirm GREEN.

### Task 3: Persist and restore versioned snapshot fields

**Files:**
- Create: `backend/alembic/versions/20260810_21_preview_capability_snapshot.py`
- Modify: `backend/app/capability_analysis/models.py`
- Modify: `backend/app/capability_analysis/repository.py`
- Modify: `backend/tests/test_capability_analysis_sql_repository.py`

**Interfaces:**
- Persists `snapshot_schema_version`, `preview_readiness`, and `verification_queue` with each `capability_gap_portfolios` row.
- Restores the exact snapshot fields on GET without deriving VERIFIED or OFFICIAL state.

- [ ] Write failing SQL repository tests for round-trip of readiness/queue and deterministic equal snapshots.
- [ ] Run `UV_CACHE_DIR=/private/tmp/pai-uv-cache uv run pytest tests/test_capability_analysis_sql_repository.py -q` and confirm RED.
- [ ] Add nullable-safe migration defaults for existing portfolios, then persist and restore the new JSON fields.
- [ ] Run SQL repository tests and confirm GREEN.

### Task 4: End-to-end PREVIEW regression

**Files:**
- Modify: `backend/tests/test_real_cv_capability_integration_harness.py`
- Modify: `backend/tests/test_capability_analysis_golden.py`

- [ ] Write failing integration assertions for the PREVIEW-only snapshot contract, deterministic rerun structure, source-backed missing-evidence wording, and no learning/official/verified outputs.
- [ ] Run focused capability suites and confirm RED.
- [ ] Implement only changes necessary for the asserted contract.
- [ ] Run all focused suites: `test_capability_analysis_rules.py`, `test_capability_analysis_api.py`, `test_capability_analysis_sql_repository.py`, `test_capability_analysis_golden.py`, and `test_real_cv_capability_integration_harness.py`.

## Self-review

- The plan covers all twelve supplied cases: evidence strength/context, missing target/evidence semantics, queue/readiness restrictions, and deterministic snapshots.
- The plan explicitly excludes all prohibited outputs and does not mutate accepted CV/JD extraction profiles.
- The persistence change is backwards-compatible: existing portfolio rows receive safe defaults and no existing identity/foreign-key contract changes.

## Milestone status and next boundary

- PREVIEW orchestration/persistence, governance boundaries, and focused evidence-eligibility rules are complete.
- P0 evidence projection is complete. Raw accepted claims override stale legacy
  CandidateProfile projections; `work_experience`, `project_usage`, education
  and credential contexts retain their original evidence type through
  EvidenceIndex, capability observations and retrieval candidates.
- Targeted semantic fixtures are complete for Python, ML/DL evaluation,
  education, Kafka/Spark aliasing, Docker mention, production deployment and
  MLOps negative control. They remain deliberately conservative: no broad
  ontology or LLM matching is used.
- Live PREVIEW validation against the accepted CV/JD profiles created portfolio
  `live-evidence-index-preview-20260810-05`: 45 requirements, 7 with retrieved
  evidence, 6 with eligible evidence, and one production `context_mismatch`
  with retrieved=1 / eligible=0. This is a diagnostic snapshot, not a final
  capability-gap count.
- The next milestone is precision-first expansion of expected-positive fixtures
  only; measure aggregate recall across all 45 requirements only after each
  new mapping preserves the retrieval-versus-eligibility boundary.
