# ID-02 Smoke-2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute one auditable, real-model comparative Smoke-2 experiment across three public research fixtures without expanding to the 72-run experiment.

**Architecture:** Add a research-only `ModelGateway` adapter for the existing one-shot and five-stage contracts. Public fixture payloads may use the configured external provider only after the privacy gateway returns external-sanitized approval; all requests retain gateway audit metadata. The CLI constructs an immutable manifest and serializable comparisons, then writes artifacts only after all calls complete.

**Tech Stack:** Python 3.13, Pydantic v2, pytest, ModelGateway, existing prompt/schema registries, argparse.

## Global Constraints

- Run exactly Model Monitoring, Python Data Processing, and Technical Communication fixtures; one one-shot and one structured run per fixture.
- Use one configured provider/model/revision/generation configuration for both conditions.
- Use no raw CV/JD, production RoleProfile, capability analysis, API, database migration, content prose, or learner outcome evaluation.
- Keep all actual model calls through ModelGateway/privacy/routing/structured validation; do not bypass audit.
- Stop on a stage failure, preserve partial artifacts, report raw metrics and findings, and never declare a winner.
- Do not run the 72-run experiment.

### Task 1: Correct call accounting and public external routing

**Files:**
- Modify: `backend/app/instructional_design/experiment.py`
- Modify: `backend/app/privacy/service.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_instructional_design_experiment_contracts.py`
- Test: `backend/tests/test_privacy_routing.py`

- [x] Write failing tests proving a three-fixture one-shot/structured smoke estimates 18 calls and a PII-clean public research request can route to the configured external provider.
- [x] Run focused tests and record RED.
- [x] Implement the smallest exact call accounting and privacy-gateway configuration needed for external public research payloads; keep internal/restricted behavior unchanged.
- [x] Run focused tests GREEN.

### Task 2: ModelGateway-backed typed designers and comparative runner

**Files:**
- Create: `backend/app/instructional_design/model_gateway_designers.py`
- Modify: `backend/app/instructional_design/experiment_runners.py`
- Modify: `backend/app/instructional_design/contracts.py`
- Test: `backend/tests/test_instructional_design_model_gateway_designers.py`

- [x] Write failing adapter tests that assert prompt/schema/payload selection, shared brief, audit-derived provenance, candidate prerequisites, and no stage fallback.
- [x] Run focused adapter tests and record RED.
- [x] Implement the adapters with `ModelGateway.infer_structured`, immutable typed artifacts, public data classification, configured provider selection, and auditable metadata.
- [x] Run focused adapter and runner tests GREEN.

### Task 3: Smoke-2 command, manifest artifact, execution, and report

**Files:**
- Create: `backend/app/instructional_design/smoke_2_cli.py`
- Create: `backend/tests/test_instructional_design_smoke_2_cli.py`
- Create: `test/results/instructional-design-smoke-2/` at execution time only
- Modify: `docs/domain/instructional-design-experiment.md`

- [x] Write failing CLI tests for the exact three fixture IDs, both conditions, one run each, manifest-before-execution, two-condition comparisons, and no winner.
- [x] Run focused CLI tests and record RED.
- [x] Implement a serializable CLI that persists manifest and raw result artifact only when explicitly invoked.
- [x] Run focused tests GREEN, then execute exactly Smoke-2 with the configured real model.
- [x] Run full backend regression and static checks; document actual metrics/findings without inferring a winner.
