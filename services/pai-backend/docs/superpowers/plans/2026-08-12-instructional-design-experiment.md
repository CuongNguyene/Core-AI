# Instructional Design Experiment ID-02 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ID-01 experimentally testable through fair one-shot and structured instructional-design conditions, deterministic comparison, human-review contracts, controlled fixtures, and a no-cost smoke runner.

**Architecture:** Add an isolated research experiment layer over ID-01's immutable artifacts and deterministic gate. Typed runner protocols produce either a one-shot canonical design or five staged structured outputs; all runs serialize the same snapshot/result contract. A fixture runner validates orchestration without model/provider cost; a future live adapter must use ModelGateway and is intentionally not executed here.

**Tech Stack:** Python 3.13, Pydantic v2, pytest, argparse CLI, existing ModelGateway prompt/schema registries, Markdown documentation.

## Global Constraints

- Research-only: no factual lesson content, RAG, question bank, tutor, learner outcome, competency decision, production learning path, API endpoint, database persistence, or migration.
- Baseline and structured conditions receive the same authored brief, generation config, policy reference, and run metadata.
- Structured stage prompts/schema contracts are exact version `0.2`; the one-shot baseline is exact version `0.1` and must not disclose staged procedure.
- Both conditions serialize to `InstructionalDesignResearchSnapshot` and receive exactly the same deterministic quality gate.
- Failed structured stages stop downstream execution, preserve safe partial artifacts, and record stage/failure/validation/retry metadata; no invisible fallback is allowed.
- Human scores are human-owned, condition-independent for blinded payloads, and never become a composite score or automatic winner.
- Do not launch paid/external model runs. Smoke uses the fixture runner only and must print a manifest first.

### Task 1: Experiment and human-evaluation data contracts

**Files:**
- Create: `backend/app/instructional_design/experiment.py`
- Create: `backend/tests/test_instructional_design_experiment_contracts.py`

**Produces:** Immutable experiment configuration, run/result/comparison/manifest, generation config, failure record, human rubric, blinded payload, and descriptive aggregation.

- [x] Write RED tests for condition comparability, independent run IDs, recorded prompt/policy/model configuration, no composite/winner, blinded review, and edit-effort ownership.
- [x] Run `pytest -q tests/test_instructional_design_experiment_contracts.py` and observe missing module failure.
- [x] Implement minimal contracts and deterministic descriptive aggregation only.
- [x] Run the focused test GREEN.

### Task 2: Versioned stage and baseline prompt/schema contracts

**Files:**
- Modify: `backend/app/instructional_design/contracts.py`
- Modify: `backend/app/instructional_design/prompts.py`
- Create: `backend/tests/test_instructional_design_experiment_prompts.py`

**Produces:** v0.2 structured stage contract registration and v0.1 one-shot baseline registration with isolated prompt responsibilities.

- [x] Write RED tests for all five v0.2 prompts, baseline isolation, preserved upstream IDs, and model-proposed candidate prerequisites.
- [x] Run focused prompt tests and observe missing v0.2/baseline constants or registration.
- [x] Implement typed output contracts/prompt templates without provider execution.
- [x] Run focused prompt tests GREEN.

### Task 3: Fair structured and baseline orchestration with failure retention

**Files:**
- Create: `backend/app/instructional_design/experiment_runners.py`
- Create: `backend/tests/test_instructional_design_experiment_runners.py`

**Produces:** One-shot and structured runner protocols, same-gate execution, stage failure result, partial snapshot retention, and fixture runner for test/smoke.

- [x] Write RED tests for same brief/config/policy, canonical baseline output, same quality gate, stage isolation, explicit failed stage, and no downstream fallback.
- [x] Run focused runner tests and observe missing orchestration imports.
- [x] Implement injected runner orchestration; do not call a provider or generate factual content.
- [x] Run focused runner tests GREEN.

### Task 4: Twelve controlled fixtures and smoke CLI

**Files:**
- Modify: `backend/app/instructional_design/fixtures.py`
- Create: `backend/app/instructional_design/experiment_cli.py`
- Create: `backend/tests/test_instructional_design_experiment_cli.py`

**Produces:** 3 domains × 2 learner states × 2 performance variants, manifest-before-run CLI, single fixture/condition filters, configurable repetitions, and fixture-only smoke output.

- [x] Write RED tests for 12 distinct research fixtures and smoke manifest/run result.
- [x] Run focused fixture/CLI tests and observe missing experiment fixtures/CLI.
- [x] Implement deterministic fixture families and argparse CLI; full/default costful mode must not invoke a live provider.
- [x] Run focused fixture/CLI tests GREEN.

### Task 5: Documentation and verification

**Files:**
- Create: `docs/domain/instructional-design-experiment.md`
- Create: `docs/domain/instructional-design-prompts-v0.2.md`
- Create: `docs/domain/instructional-design-evaluation-rubric.md`
- Modify: `docs/domain/instructional-design-research-plan.md`

- [x] Document implemented research boundaries, prompts, evaluation, fixture smoke and full-run readiness; do not invent results.
- [x] Run all ID-01/ID-02 focused tests, full backend suite, Ruff, scoped mypy, and `git diff --check`.
- [x] Inspect changed files to verify no production API, migration, learning, capability, extraction, provider-routing, or actual external run changed.
