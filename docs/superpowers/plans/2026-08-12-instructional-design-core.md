# Instructional Design Core v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, research-only Instructional Design Core that validates typed instructional-design artifacts created from an explicitly authored `ResearchLearningBrief`.

**Architecture:** Create an isolated `app.instructional_design` domain package. Typed research artifacts and proposal contracts remain separate from a deterministic quality gate; an orchestrator assembles immutable research snapshots without generating factual lesson content or making provider calls. Prompt and output-schema registration is versioned but is not wired to an HTTP endpoint, worker, persistence layer, or production learning path.

**Tech Stack:** Python 3.13, Pydantic v2, pytest, ModelGateway prompt/schema registries, Markdown ADR and domain documentation.

## Global Constraints

- Research-only: use `ResearchLearningBrief` with `research_fixture` provenance; never accept or create a production `RoleCompetencyProfile` or learning path.
- Do not implement RAG, content rendering, lesson factual content, question banks, competency verification, provider calls, API endpoints, database persistence, or migrations.
- Deterministic validation owns all pass/fail findings. LLM proposal contracts must never self-approve a design.
- `model_proposed` prerequisites must be explicitly `candidate`; no promotion to `confirmed` is allowed.
- Prompt and schema IDs/versions are exact `0.1`; snapshot provenance records policy, prompt/schema, and model metadata.
- `quality_report.passed` means only deterministic policy checks passed, not SME approval, competency verification, or production-course approval.

### Task 1: Research models and provenance contracts

**Files:**
- Create: `backend/app/instructional_design/__init__.py`
- Create: `backend/app/instructional_design/schemas.py`
- Create: `backend/tests/test_instructional_design_schemas.py`

**Consumes:** Existing Pydantic v2 conventions in `app.learning.schemas`.

**Produces:** Frozen models `ResearchLearningBrief`, `LearningObjectiveSpec`, `AssessmentSpec`, `PrerequisiteSpec`, `CourseOutline`, `LessonSpec`, `InstructionalDesignQualityReport`, and `InstructionalDesignResearchSnapshot`.

- [x] **Step 1: Write failing schema tests** for research-only provenance, a valid observable objective, model-proposed prerequisite candidate enforcement, snapshot generation provenance, and fixture serialization.
- [x] **Step 2: Run RED**

Run: `UV_CACHE_DIR=/private/tmp/pai-uv-cache uv run pytest -q tests/test_instructional_design_schemas.py`

Expected: import failure for `app.instructional_design`.

- [x] **Step 3: Implement minimal frozen Pydantic schemas** with explicit enums, IDs, status/basis validation, and provenance objects; do not add persistence or API models.
- [x] **Step 4: Run GREEN** using the same focused command.

### Task 2: Policy and deterministic quality gate

**Files:**
- Create: `backend/app/instructional_design/policy.py`
- Create: `backend/app/instructional_design/quality_gate.py`
- Create: `backend/tests/test_instructional_design_quality_gate.py`

**Consumes:** Task 1 artifact schemas.

**Produces:** `InstructionalDesignPolicy.v0_1` and `evaluate_instructional_design(...) -> InstructionalDesignQualityReport`.

- [x] **Step 1: Write failing tests** for all deterministic acceptance cases: vague objective, missing/orphan assessment, cognitive under-demand, orphan lesson/module, objective not taught, prerequisite order/cycle, uncovered assessment dependency, candidate prerequisites, and deterministic report identity.
- [x] **Step 2: Run RED**

Run: `UV_CACHE_DIR=/private/tmp/pai-uv-cache uv run pytest -q tests/test_instructional_design_quality_gate.py`

Expected: missing quality-gate import/function.

- [x] **Step 3: Implement only deterministic checks.** Use ordered Bloom demand (assessment must be at least objective demand for summative checks); use explicit references only for dependency coverage; detect confirmed-prerequisite cycles without breaking them.
- [x] **Step 4: Run GREEN** using the same focused command.

### Task 3: Versioned LLM proposal contracts and snapshot assembly

**Files:**
- Create: `backend/app/instructional_design/contracts.py`
- Create: `backend/app/instructional_design/prompts.py`
- Create: `backend/app/instructional_design/orchestrator.py`
- Create: `backend/tests/test_instructional_design_contracts.py`

**Consumes:** Task 1 schemas, Task 2 policy/gate, `PromptTemplateRegistry`, and `OutputSchemaRegistry`.

**Produces:** Exact versioned registrations for objective, assessment, prerequisite, course, and lesson proposals plus `build_research_snapshot(...)`.

- [x] **Step 1: Write failing tests** that resolve every prompt/schema pair, inspect research-only instructions, preserve upstream IDs, retain model/prompt/schema provenance, and prove the orchestrator delegates pass/fail to the deterministic gate.
- [x] **Step 2: Run RED**

Run: `UV_CACHE_DIR=/private/tmp/pai-uv-cache uv run pytest -q tests/test_instructional_design_contracts.py`

Expected: missing contracts registration/orchestrator.

- [x] **Step 3: Register typed JSON-only proposal contracts and implement snapshot assembly.** The orchestrator must accept typed stage outputs; it must not perform a provider call, mutate a brief, or generate teaching content.
- [x] **Step 4: Run GREEN** using the same focused command.

### Task 4: Three domain-diverse research fixtures and documentation

**Files:**
- Create: `backend/app/instructional_design/fixtures.py`
- Create: `backend/tests/test_instructional_design_fixtures.py`
- Create: `docs/domain/instructional-design-core.md`
- Create: `docs/domain/instructional-design-research-plan.md`
- Create: `docs/domain/instructional-design-policy-v0.1.md`
- Create: `docs/domain/instructional-design-data-contracts.md`
- Create: `docs/adr/0021-instructional-design-before-content-generation.md`

**Consumes:** Task 1–3 contracts.

**Produces:** Serializable Model Monitoring, Python Data Processing, and Technical Communication research fixtures plus implementation-accurate documentation.

- [x] **Step 1: Write failing tests** that load all three fixtures, verify they have `research_fixture` provenance, are domain-diverse, remain research-only, and yield deterministic reports.
- [x] **Step 2: Run RED**

Run: `UV_CACHE_DIR=/private/tmp/pai-uv-cache uv run pytest -q tests/test_instructional_design_fixtures.py`

Expected: missing fixture module.

- [x] **Step 3: Implement fixtures and documents.** Documents distinguish external instructional-design frameworks from PAI architecture and state no evaluation result has been measured.
- [x] **Step 4: Run GREEN** using the same focused command.

### Task 5: Full verification and checkpoint

**Files:**
- Verify only the Task 1–4 files.

- [x] Run all Instructional Design focused tests.
- [x] Run full backend suite, Ruff, scoped mypy, and `git diff --check`.
- [x] Inspect diff and verify no API, Alembic, production-learning, capability, extraction, or provider-routing files changed.
- [ ] Commit the isolated worktree checkpoint after user review/authorization.
