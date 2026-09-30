# ID-03B.1 Cross-Domain Root Cause Trace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute this forensic plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trace the persisted ID-03B failure artifacts to the stage that owns each invalid reference or uncovered dependency, without changing generation or validation semantics.

**Architecture:** Read the immutable `results.json` from the five-run live smoke and derive deterministic traces from typed partial artifacts and snapshots. Persist only forensic JSON and documentation; keep model output, prompts, schemas, the normalizer, and the quality gate unchanged.

**Tech Stack:** Python 3.13, persisted JSON artifacts, Pydantic experiment contracts, pytest, Ruff, mypy.

**Spec:** `/Users/mac/.codex/attachments/da3ee009-b97d-49cf-a739-c698ae1aa158/pasted-text.txt`

## Global Constraints

- Do not change prompt version, schemas, quality-gate severity, validators, normalizer behavior, or model execution.
- Do not add fuzzy reference repair or auto-create objectives from unknown references.
- Do not rerun the five-fixture cross-domain smoke, create human-review packets, or start TEXT-01.
- Treat model-proposed prerequisites as candidates; do not promote them during analysis.

### Task 1: Trace reference ownership from persisted partial artifacts

**Files:**
- Read: `backend/test/results/instructional-design-id-03b-cross-domain-smoke/results.json`
- Create: `backend/test/results/instructional-design-id-03b-root-cause/reference-trace.json`
- Test: `backend/tests/test_instructional_design_id02d_contracts.py`

**Interfaces:**
- Each trace records `fixture`, `finding`, `producer_stage`, `reference_value`, `expected_owner`, `actual_owner`, `root_cause`, `validator_correct`, and `recommended_fix_layer`.
- `_validate_v03_references()` remains the fail-closed authority for nested capability-requirement objective ownership.

- [x] Add a regression test where a required capability refers to an objective that exists globally but is outside its parent `AssessmentSpec.objective_ids`; assert `_validate_v03_references()` raises the existing fail-closed error.
- [x] Run `uv run pytest tests/test_instructional_design_id02d_contracts.py -q` and confirm the invariant is already enforced without production changes.
- [x] For Accounting, HR, and Construction, derive every nested requirement objective ID outside the parent assessment's ownership set.
- [x] Classify the source as `assessment_generation` when the objective exists globally but was assigned outside the parent assessment; preserve the original value and parent ownership set.

### Task 2: Trace required dependency coverage without changing the gate

**Files:**
- Read: `backend/test/results/instructional-design-id-03b-cross-domain-smoke/results.json`
- Create: `backend/test/results/instructional-design-id-03b-root-cause/dependency-trace.json`
- Test: `backend/tests/test_instructional_design_quality_gate.py`

**Interfaces:**
- A dependency trace records its assessment reference, normalized dependency text, exact stage presence, missing stage, root-cause classification, validator status, and recommended fix layer.
- `evaluate_instructional_design()` counts only known learner evidence, objective `capability_refs` taught by lessons, and confirmed prerequisites as coverage.

- [x] Add a regression test where a model-proposed candidate prerequisite has the same capability text as an assessment requirement; assert `assessment_dependency_not_covered` remains present and the prerequisite stays `candidate`.
- [x] Run `uv run pytest tests/test_instructional_design_quality_gate.py -q` and confirm no promotion or validator relaxation occurs.
- [x] For Python and Legal, trace each canonical required dependency through assessment requirements, dependency candidates, prerequisite references, course references, and lesson references.
- [x] Record `assessment_scope_creep` when the AssessmentDesigner both treats an unresolved external capability as required and emits it as a candidate/precondition; record `missing_dependency_propagation` when objective semantic `capability_refs` are absent despite objective/course/lesson ID coverage.

### Task 3: Audit DependencyNormalizer and persist root-cause report

**Files:**
- Read: `backend/app/instructional_design/dependency_normalizer.py`
- Create: `backend/test/results/instructional-design-id-03b-root-cause/manifest.json`
- Create: `backend/test/results/instructional-design-id-03b-root-cause/root-cause-report.json`
- Create: `backend/test/results/instructional-design-id-03b-root-cause/validation-report.json`

**Interfaces:**
- The report references source experiment `instructional-design-id-03b-cross-domain-smoke`, `structured_v0.3.1`, and normalizer `id02d.2@0.1`.
- Normalization proof records legacy/typed duplicate merging, provenance source types, and the fact that supporting candidates retain `status=candidate`.

- [x] Compare each completed snapshot's legacy and typed requirements to canonical dependencies by exact normalized text.
- [x] Assert every identical legacy/typed pair produces one canonical required dependency with both provenance sources.
- [x] Assert supporting dependencies sourced from `dependency_candidates` retain `dependency_role=supporting_dependency` and `status=candidate`.
- [x] Summarize only observed prompt, schema, orchestration, and validator ownership; do not propose or implement repairs.

### Task 4: Update cross-domain documentation and verify forensic deliverables

**Files:**
- Modify: `docs/domain/instructional-design-cross-domain-validation.md`
- Verify: `backend/test/results/instructional-design-id-03b-root-cause/*.json`

- [x] Add an ID-03B findings section with per-domain failure, observed producer stage, root cause, correct fix layer, and explicit non-success statement.
- [x] Validate every root-cause JSON artifact with `python -m json.tool`.
- [x] Run `uv run pytest tests/test_instructional_design_id02d_contracts.py tests/test_instructional_design_quality_gate.py tests/test_instructional_design_dependency_normalization.py tests/test_instructional_design_cross_domain_fixtures.py -q`.
- [x] Run `uv run ruff check app tests`, `uv run mypy app`, and `git diff --check`.
