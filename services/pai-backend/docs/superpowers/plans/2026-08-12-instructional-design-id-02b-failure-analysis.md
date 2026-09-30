# ID-02B Failure Analysis and Blinded Review Preparation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Classify the nine structured Smoke-2 findings without weakening the quality gate, then prepare condition-blind packets for six human calibration reviews.

**Architecture:** Store researcher-authored root-cause annotations as a separate immutable research artifact that references the existing result/finding identity. Strengthen the existing blinded payload contract so reviewers receive an opaque review ID and snapshot only; its condition mapping remains in a private researcher artifact.

**Tech Stack:** Python 3.13, Pydantic v2, pytest, JSON research artifacts, Markdown documentation.

## Global Constraints

- Do not change any quality-gate severity, exception, or validator rule.
- Do not tune prompts, introduce v0.3, rerun the model, or proceed to text generation.
- Root-cause labels are researcher-authored hypotheses, not model inference or validated pedagogical conclusions.
- Review packets must not contain condition, a condition-bearing run ID, or a prompt identifier.
- Preserve all raw Smoke-2 artifacts; analysis references their exact run/finding fields.

### Task 1: Failure-analysis contract and annotated Smoke-2 report

**Files:**
- Create: `backend/app/instructional_design/failure_analysis.py`
- Create: `backend/tests/test_instructional_design_failure_analysis.py`
- Create: `backend/test/results/instructional-design-smoke-2-live-3/failure-analysis.json`

- [x] Write RED tests proving an annotation must reference an exact run/finding, has one allowed root-cause category, records producer stage and validator correctness, and cannot alter the source result.
- [x] Run the focused test and observe missing contract failure.
- [x] Implement immutable research contracts and write the nine researcher-authored annotations from Smoke-2.
- [x] Run focused test GREEN.

### Task 2: Opaque blinded review packets

**Files:**
- Modify: `backend/app/instructional_design/experiment.py`
- Modify: `backend/tests/test_instructional_design_experiment_contracts.py`
- Create: `backend/app/instructional_design/blinded_review_cli.py`
- Create: `backend/tests/test_instructional_design_blinded_review_cli.py`
- Create: `backend/test/results/instructional-design-smoke-2-live-3/blinded-review/`

- [x] Write RED tests proving a blinded payload has an opaque review ID and no condition/run ID/prompt metadata, while private mapping retains the run ID only outside packets.
- [x] Run focused tests and observe the existing condition-bearing payload failure.
- [x] Implement the minimal contract and CLI to create six packets plus one private mapping from the raw Smoke-2 result.
- [x] Run focused tests GREEN.

### Task 3: Documentation and verification

**Files:**
- Modify: `docs/domain/instructional-design-experiment.md`
- Modify: `docs/domain/instructional-design-evaluation-rubric.md`

- [x] Record the structured-interface trade-off, failure-analysis distributions, milestone state, and review question that separates traceability from pedagogical judgment.
- [x] Run focused tests, full backend tests, Ruff, scoped mypy, and `git diff --check`.
