# PR-007 Learning Path & Content Blueprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** Build a versioned learning-path and course-blueprint slice from eligible verified competencies, active target profiles, approved preliminary gaps, and a dated development goal.

**Architecture:** Keep the modular monolith. The learning application service owns eligibility, deterministic graph validation, generator orchestration and audit; SQLAlchemy and in-memory repositories are adapters. The content generator is an internal protocol whose only implementation in this PR is a deterministic fake provider.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy async, Alembic, pytest/pytest-asyncio, Ruff and mypy strict.

## Global Constraints

- Only `VERIFIED` competency records, an exact `ACTIVE` target role profile version, and `REVIEWED` preliminary matches with explicit approved gaps are eligible.
- Actor and organization come from the ADR-0010 development identity adapter; the request cannot grant role or organization authority.
- CV/JD raw content, extraction payload, prompt, generated content body and evidence payload never enter the learning generator or audit metadata.
- Learning path, blueprint and learning object changes create immutable versions; no in-place mutation.
- Prerequisite edges form a DAG and every learning object links to competency, target level, assessment reference and approved provenance reference.
- Learning completion never calls competency transition and no credential is issued.
- No external AI provider, new microservice or queue provider is introduced.

### Task 1: Preliminary-gap approval and learning contracts

**Files:**
- Create: `backend/app/learning/schemas.py`, `backend/app/learning/errors.py`, `backend/app/learning/graph.py`
- Modify: `backend/app/matching/schemas.py`, `backend/app/matching/models.py`, `backend/app/matching/repository.py`, `backend/app/matching/api.py`, `backend/app/matching/service.py`
- Test: `backend/tests/test_learning_schemas.py`, `backend/tests/test_matching_review.py`

**Interfaces:**
- `LearningPathRequest`, `LearningObjective`, `PrerequisiteNode`, `PrerequisiteEdge`, `LearningObjectMetadata`, `Lesson`, `LearningModule`, `CourseBlueprint`, `LearningPath`, `LearningPathStatus`, `LearningObjectType`, `ProvenanceStatus`.
- `validate_prerequisite_graph(nodes: list[PrerequisiteNode], edges: list[PrerequisiteEdge]) -> None`.
- `PreliminaryMatchReviewRequest(approved_gap_ids: list[str], expected_version: int)` and review transition on `PreliminaryMatchService.review(...)`.

- [ ] **Step 1: Write failing schema and review tests.** Assert raw/inline competency input is rejected, graph cycles are rejected, and only a reviewer can transition a completed match to reviewed with approved gaps.
- [ ] **Step 2: Run the focused tests and verify expected failures.** Run `cd backend && uv run --extra dev pytest tests/test_learning_schemas.py tests/test_matching_review.py -q`; expect missing learning contracts/review transition failures.
- [ ] **Step 3: Implement minimal Pydantic contracts, DAG validator and matching review state transition.** Persist only approved gap IDs, reviewer UUID, review timestamp and optimistic version metadata; do not add content body.
- [ ] **Step 4: Run focused tests to green and run Ruff on changed files.**
- [ ] **Step 5: Commit `feat: define learning contracts and gap approval`**.

### Task 2: Migration, ORM records and repositories

**Files:**
- Create: `backend/alembic/versions/20260803_12_learning_path_blueprints.py`, `backend/app/learning/models.py`, `backend/app/learning/repository.py`
- Modify: `backend/app/shared/database.py`, `backend/tests/test_migration_config.py`
- Test: `backend/tests/test_learning_repository.py`, `backend/tests/test_learning_sql_repository.py`

**Interfaces:**
- `LearningPathRepository` protocol with `create`, `get`, `supersede` and `record_audit`.
- `InMemoryLearningPathRepository` for unit tests and `SqlAlchemyLearningPathRepository` for runtime.
- `LearningPathRecord` stores aggregate/version snapshots and safe source metadata; `LearningAuditEventRecord` is append-only.

- [ ] **Step 1: Write failing repository tests.** Cover immutable duplicate version rejection, supersession, audit metadata redaction and rollback when audit insertion fails.
- [ ] **Step 2: Run repository tests to verify they fail for missing models/repository.**
- [ ] **Step 3: Add migration and ORM aggregate tables.** Add unique `(path_id, version)`, one current active version constraint/index, source input indexes and foreign-key-safe audit linkage. Store nested blueprint metadata as JSON, never raw documents.
- [ ] **Step 4: Implement both repositories with one transaction for snapshot plus audit.** Use SQLAlchemy async session factory and return Pydantic snapshots, not ORM objects.
- [ ] **Step 5: Run repository tests and `alembic upgrade head` against the development database.**
- [ ] **Step 6: Commit `feat: persist learning path blueprint snapshots`**.

### Task 3: Eligibility service and deterministic fake generator

**Files:**
- Create: `backend/app/learning/generator.py`, `backend/app/learning/service.py`
- Modify: `backend/app/competency/repository.py`, `backend/app/matching/repository.py`
- Test: `backend/tests/test_learning_eligibility.py`, `backend/tests/test_learning_generator.py`, `backend/tests/test_learning_service.py`

**Interfaces:**
- `ContentGenerationRequest` contains normalized objective/gap summaries, competency IDs/levels, deadline and policy versions only.
- `GeneratedBlueprint` contains metadata-only blueprints/modules/lessons/objects.
- `ContentBlueprintGenerator.generate(request: ContentGenerationRequest) -> GeneratedBlueprint`.
- `FakeContentBlueprintGenerator` is deterministic and records only safe call metadata in tests.
- `LearningPathService.create(...)` and `LearningPathService.supersede(...)` perform all guards before generation and persistence.

- [ ] **Step 1: Write failing eligibility/service tests.** Cover unverified/expired/superseded competency, inactive target, wrong subject/org, unreviewed/low-confidence gap, stale versions, deterministic rerun, and completion not changing competency.
- [ ] **Step 2: Run focused tests and verify failures are caused by missing service/provider.**
- [ ] **Step 3: Implement repository reader protocols and eligibility guards.** Require actor subject equality, exact target version, `VERIFIED` validity through target date, `REVIEWED` match approval and requirement confidence threshold.
- [ ] **Step 4: Implement fake generator and graph/provenance/assessment-link validation.** Generator must never receive raw document IDs/content or arbitrary client prompts.
- [ ] **Step 5: Persist immutable path snapshot and safe audit through the repository.**
- [ ] **Step 6: Run focused tests to green and commit `feat: generate eligible learning blueprints`**.

### Task 4: API wiring and application integration

**Files:**
- Create: `backend/app/learning/api.py`
- Modify: `backend/app/main.py`, `backend/app/shared/errors.py`
- Test: `backend/tests/test_learning_api.py`, `backend/tests/test_learning_openapi.py`

**Interfaces:**
- `POST /learning-paths` creates a path from references and goal/date.
- `GET /learning-paths/{path_id}` returns the immutable snapshot to its subject.
- `POST /learning-paths/{path_id}/supersede` creates a new version from a new eligible request.

- [ ] **Step 1: Write failing ASGI API tests.** Cover success, learner access, wrong actor, unsafe body fields, each safe error code and OpenAPI route presence.
- [ ] **Step 2: Run API tests to verify missing router/integration failures.**
- [ ] **Step 3: Implement request/response schemas, dependency wiring and safe error mapping.** Do not expose ORM objects or raw input in errors.
- [ ] **Step 4: Register the router and fake generator in `create_app`; keep SQLAlchemy repositories as runtime adapters.**
- [ ] **Step 5: Run API tests, OpenAPI inspection and full backend suite.**
- [ ] **Step 6: Commit `feat: expose learning path blueprint API`**.

### Task 5: Golden harness, documentation and final verification

**Files:**
- Create: `backend/tests/golden/learning_path_blueprint.json`, `backend/tests/test_golden_learning.py`
- Modify: `docs/domain/three-layer-assessment.md`, `README.md`

- [ ] **Step 1: Add golden fixture containing verified input references, approved gaps, goal/deadline and metadata-only expected blueprint.**
- [ ] **Step 2: Add deterministic rerun test and assertions that no raw document/prompt/body/credential appears in output or audit.**
- [ ] **Step 3: Update domain/API documentation with lifecycle and non-goals.**
- [ ] **Step 4: Run `uv run --extra dev pytest -q`, Ruff format/check, mypy and pre-commit from `backend/`; run `alembic upgrade head` and `alembic current`.**
- [ ] **Step 5: Review `git diff`, confirm only PR-007 files changed, and commit `test: add learning blueprint golden harness`**.
