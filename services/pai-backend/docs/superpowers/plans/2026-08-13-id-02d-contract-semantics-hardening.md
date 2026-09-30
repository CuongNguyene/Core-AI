# ID-02D Contract Semantics Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add typed semantic IR and deterministic validations that prevent assessment/reference misuse, assessment taxonomy drift, graph inconsistency, undeclared time conflicts, and structurally unsupported prerequisite candidates.

**Architecture:** Register structured patch version `0.3.1` alongside historical versions. Stage validation fails closed for new outputs; the quality gate reports the same semantic failures for aggregate/one-shot output. Orchestration derives module lesson edges but never deletes or rewrites model-authored semantic references.

**Tech Stack:** Python 3.13, Pydantic v2, pytest, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-08-13-id-02d-contract-semantics-hardening-design.md`

## Global Constraints

- Preserve historical structured `0.2`/`0.3` and one-shot `@0.1` artifacts.
- Register additive structured `0.3.1`; do not create prompt `0.4`.
- Do not weaken quality-gate severity or repair model semantics silently.
- Do not run a full Smoke experiment in this milestone.
- Candidate prerequisites remain candidate/model-proposed.

### Task 1: Typed assessment role and capability requirements

**Files:**
- Modify: `backend/app/instructional_design/schemas.py`
- Modify: `backend/app/instructional_design/contracts.py`
- Test: `backend/tests/test_instructional_design_id02d_contracts.py`

**Produces:** `AssessmentRole`, `AssessmentCapabilityRequirement`, legacy-compatible `AssessmentSpec.role` and `required_capabilities`.

- [x] Write failing tests that reject conflicting legacy/typed assessment roles and retain typed capability semantic strings.
- [x] Run the focused test and observe failure.
- [x] Implement only the additive schema models and role-consistency validator.
- [x] Run the focused test and observe pass.

### Task 2: Stage semantic validation and prompt patch contract

**Files:**
- Modify: `backend/app/instructional_design/contracts.py`
- Modify: `backend/app/instructional_design/prompts.py`
- Modify: `backend/app/instructional_design/model_gateway_designers.py`
- Modify: `backend/app/instructional_design/experiment_runners.py`
- Test: `backend/tests/test_instructional_design_id02d_contracts.py`

**Consumes:** Task 1 semantic models.
**Produces:** `0.3.1` registration and fail-closed validation of artifact IDs in capability fields, non-formative lesson refs, and lesson/module objective ownership.

- [x] Write failing tests using Smoke-3-shaped assessment IDs and summative IDs in formative lists.
- [x] Run tests and observe the missing validator failure.
- [x] Register `0.3.1`, add allow-list validation and concise stage prompt rules.
- [x] Run focused contract/runner tests and observe pass.

### Task 3: Aggregate graph and taxonomy quality-gate checks

**Files:**
- Modify: `backend/app/instructional_design/quality_gate.py`
- Test: `backend/tests/test_instructional_design_quality_gate.py`

**Consumes:** Assessment effective role and graph semantics.
**Produces:** deterministic findings for artifact-ID capability reference, summative-as-formative, lesson objective outside module/course.

- [x] Write failing quality-gate tests for Python/Technical-Communication finding shapes.
- [x] Run tests and observe failures.
- [x] Implement findings without deleting lessons or changing severity policy.
- [x] Run focused gate tests and observe pass.

### Task 4: Planning warnings and prerequisite structural review

**Files:**
- Modify: `backend/app/instructional_design/schemas.py`
- Modify: `backend/app/instructional_design/contracts.py`
- Modify: `backend/app/instructional_design/quality_gate.py`
- Test: `backend/tests/test_instructional_design_id02d_contracts.py`
- Test: `backend/tests/test_instructional_design_quality_gate.py`

**Produces:** typed scope/time warning and non-mutating prerequisite structural review.

- [x] Write failing tests for explicit duration overflow without warning, overflow with warning, and candidate minimality review result.
- [x] Run tests and observe failures.
- [x] Implement only declared-duration arithmetic and structural review classifications.
- [x] Run focused tests and observe pass.

### Task 5: Regression/docs/verification

**Files:**
- Modify: `docs/domain/instructional-design-experiment.md`
- Create: `docs/domain/instructional-design-contract-semantics.md`
- Test: existing instructional-design suites

- [x] Add regression inventory mapping Smoke-2/Smoke-3 observations to deterministic checks.
- [x] Run `pytest -q tests/test_instructional_design* tests/test_model_gateway.py`.
- [x] Run full `pytest -q`, `ruff check app tests`, scoped `mypy`, and `git diff --check`.
- [x] Record results; do not execute a new Smoke run.

## Verification record

- Focused instructional-design and gateway regression: `76 passed`.
- Focused ID-02D contracts and quality gate after final patch: `23 passed`.
- Full backend suite: `528 passed`.
- `ruff check app tests`, scoped `mypy`, and `git diff --check`: passed.
- No live provider call or Smoke run was executed.

### Smoke-4 validation follow-up

- Manifest persisted before execution in `backend/test/results/instructional-design-smoke-4/`.
- Condition: `structured_v0.3.1`; fixtures: 3; planned calls: 15.
- Completed: 2/3; Technical Communication stopped at AssessmentDesigner with `invalid_model_json`.
- Completed-run contract checks: pass for capability refs, formative/summative separation, lesson graph, prerequisite governance, and scope warnings.
- Exact milestone decision: `ID-02D BLOCKED` due model reliability preventing the required 3/3 validation.

### ID-02D.1 recovery record

- Recovered only `technical_communication:structured_v0.3.1` with the existing gateway repair/retry path.
- Parent manifest/config/prompt-schema provenance was preserved; parent Smoke-4 artifacts were not overwritten.
- Merged result: 3/3 completed; all five contract checks pass.
- Python dependency trace: 2 unique requirements, 4 duplicated gate projections; root cause classified as `assessment_scope_creep` with secondary `missing_dependency_propagation`; validator correct.
- Final recovery status: `ID-02D NEEDS ITERATION` because the unchanged quality gate still reports four `ERROR` findings.
