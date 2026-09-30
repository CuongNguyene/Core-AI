# ID-03A Cross-Domain Validation Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a clean five-domain, brief-only fixture registry and validation contracts for cross-domain instructional-design analysis.

**Architecture:** Keep generated `ResearchFixtureBundle` unchanged for existing deterministic tests. Add a separate strict `CrossDomainFixture` input model containing only controlled metadata and `ResearchLearningBrief`; the registry creates five fresh fixtures and performs no model calls.

**Tech Stack:** Python 3.13, Pydantic strict models, pytest, Ruff, mypy.

**Spec:** `docs/domain/instructional-design-cross-domain-validation.md`

## Global Constraints

- Do not execute model calls, Smoke-5, human review, TEXT generation, RAG, or lesson factual-content generation.
- Do not create prompt v0.4 or change ID-02D prompt/schema/quality-gate semantics.
- Cross-domain labels are controlled experiment metadata, not an ontology.
- Fixtures contain only metadata and `ResearchLearningBrief`; generated artifacts are rejected.

### Task 1: Define strict metadata and fixture purity contracts

**Files:**
- Modify: `backend/app/instructional_design/fixtures.py`
- Test: `backend/tests/test_instructional_design_cross_domain_fixtures.py`

**Interfaces:**
- `CrossDomainFixtureMetadata` exposes `fixture_id`, `domain`, `industry_family`, `learning_type`, `difficulty`, and `description`.
- `CrossDomainFixture` exposes only `metadata` and `brief`.
- `cross_domain_validation_fixtures() -> dict[str, CrossDomainFixture]` returns five clean fixtures.

- [x] Write RED tests for missing domain, unsupported learning type, valid metadata, generated-content rejection, registry cardinality, and metadata/key consistency.
- [x] Run the focused test and observe collection failure before implementation.
- [x] Implement strict enums/models and the brief-only registry.
- [x] Run focused tests, Ruff, mypy, and diff check.

### Task 2: Document the domain matrix and evaluation dimensions

**Files:**
- Create: `docs/domain/instructional-design-cross-domain-validation.md`
- Create: `docs/superpowers/plans/2026-08-13-id-03a-cross-domain-validation.md`

- [x] Document motivation, research question, fixture purity, five-domain matrix, and domain-neutral invariants.
- [x] Define objective quality, assessment alignment, prerequisite quality, sequencing, and traceability without scoring.
- [x] Review docs for scope leakage into model execution or TEXT-01.

### Task 3: Verify ID-03A without execution

**Files:**
- No runtime/provider changes.

- [x] Run focused cross-domain fixture tests.
- [x] Run instructional-design regression tests and full backend suite.
- [x] Run Ruff, scoped/full mypy, and `git diff --check`.
- [x] Confirm no model-output or Smoke artifact files were modified.

No ID-03B model execution starts automatically after this plan.
