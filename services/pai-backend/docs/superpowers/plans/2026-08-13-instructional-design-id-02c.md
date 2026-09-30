# ID-02C Prompt v0.3 and Smoke-3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the structured instructional-design pipeline against reference drift, assessment scope creep, prerequisite inflation, and missing practice, then run a controlled Smoke-3 comparison.

**Architecture:** Keep the five-stage structured pipeline and unchanged one-shot baseline. Model outputs remain proposals; orchestration validates supplied references, derives module lesson ownership after lesson generation, deduplicates only exact prerequisite candidates, and the deterministic quality gate remains the final non-repairing authority.

**Tech Stack:** Python 3.13, Pydantic v2, pytest, ModelGateway/Vilao, JSON research artifacts, Markdown.

**Spec:** `/Users/mac/.codex/attachments/19d52349-8e90-4ee6-b096-743050b9b4f1/pasted-text.txt`

## Global Constraints

- Preserve `instructional_design_one_shot_baseline@0.1` unchanged.
- Structured prompts and prompt/schema provenance use `0.3` for Smoke-3; historical Smoke-2 artifacts remain immutable.
- Do not relax existing quality-gate findings or repair unknown IDs with fuzzy/string guessing.
- Do not generate factual lesson content or proceed to TEXT-01.
- Model-proposed prerequisites remain `status=candidate`, `basis=model_proposed`.
- Do not mutate CV/JD profiles, capability analysis, or learning-path behavior.

### Task 1: v0.3 typed contracts and prompt registry

**Files:** `backend/app/instructional_design/contracts.py`, `schemas.py`, `prompts.py`, tests.

- [x] Add typed dependency candidates and prerequisite classification/minimality fields with backward-compatible defaults.
- [x] Add strict output validators for supplied objective/module/assessment references where stage context is available.
- [ ] Register structured schema/prompt version `0.3` alongside historical `0.2`; keep baseline `0.1`.
- [x] Add RED/GREEN tests for scope containment, candidate prerequisite rationale, and prompt-version/prose requirements.

### Task 2: orchestration ownership and deterministic reference resolution

**Files:** `backend/app/instructional_design/orchestrator.py`, `experiment_runners.py`, tests.

- [x] Validate unknown stage references as explicit stage failures.
- [x] Deduplicate only exact normalized prerequisite candidates and preserve provenance/references.
- [x] Derive `module.lesson_ids` from final `LessonSpec.module_id` after lesson generation.
- [x] Add final module/lesson graph consistency checks without silently repairing invalid model references.

### Task 3: v0.3 structured designer behavior

**Files:** `model_gateway_designers.py`, tests.

- [x] Make structured designer version explicit/configurable, defaulting to historical `0.2` for compatibility and using `0.3` in Smoke-3.
- [x] Send stage-specific v0.3 constraints and typed upstream artifacts.
- [x] Preserve one-shot designer path and prompt version exactly.

### Task 4: deterministic practice and scope regressions

**Files:** `quality_gate.py`, tests, docs.

- [x] Add only low-false-positive practice-before-summative detection for apply/analyze/evaluate/create objectives.
- [x] Keep integrated-practice guidance prompt-level unless a safe deterministic rule is demonstrated.
- [x] Add regression fixtures for orphan references, scope creep, prerequisite minimality/governance, practice coverage, and module lesson ownership.

### Task 5: Smoke-3 runner and controlled artifacts

**Files:** new/modified Smoke-3 CLI, tests, docs.

- [x] Persist the full manifest before model calls with provider/model/config/policy/prompt/schema metadata and 18 planned calls.
- [x] Run 3 fixtures × 2 conditions × 1 run with Vilao/claude-sonnet-5 and unchanged baseline; the missing structured slot was recovered in an isolated run using the same controls.
- [x] Persist manifest, results, comparisons, audit metadata, and failure annotations in a new directory.
- [x] Compare Smoke-2 vs Smoke-3 descriptively after the isolated recovery; no winner is declared.

### Task 6: Smoke-3 blinded review readiness and verification

**Files:** review packet generator/artifacts, docs.

- [x] Prepare six condition-free packets with the same rubric v0.1 and private mapping after all six Smoke-3 snapshots exist.
- [x] Run focused tests, full backend suite, Ruff, scoped mypy, and `git diff --check`.
- [x] Report `READY_FOR_BLINDED_REVIEW`; do not fabricate review results or advance to TEXT-01.
- [x] Ingest the six returned blind submissions without unblinding their source files; record one-reviewer calibration summary and keep structured quality at `NEEDS_ITERATION`.
