# COURSE-REC-01A Catalog + Course Capability Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a deterministic Core-AI course-supply contract, normalized internal/external catalog fixtures, validation tests, and evidence without changing LMS schema or implementing recommendation logic.

**Architecture:** Create a focused `course_catalog` domain module in Core-AI. It owns source identity, `ExternalCourse`, `CourseCapabilityProfile`, capability coverage, course-local prerequisites, provenance, lifecycle, and a normalized candidate projection. Internal LMS and external provider facts enter through explicit constructors/fixtures; recommendation logic is deferred to COURSE-REC-01B.

**Tech Stack:** Python 3.13, Pydantic v2, pytest, existing Core-AI domain schemas and deterministic fixture conventions.

**Spec:** User-provided COURSE-REC-01A request in `/Users/mac/.codex/attachments/61fb850c-96e0-4ff8-8522-82a49af1494e/Pasted text.txt`.

## Global Constraints

- Do not modify LMS production code or LMS Course schema.
- Do not add recommendation ranking, scoring, top-k selection, embeddings, vector search, or model calls.
- Do not add migrations, persistence, live provider clients, OAuth, or network calls.
- Preserve nullable unknown `target_level`; never infer semantic levels from title, duration, or descriptions.
- Keep LMS course facts separate from Core-AI semantic capability claims.
- Use synthetic, domain-neutral fixtures only and do not include secrets or production personal data.
- Do not commit or push.

## Review Focus

- Internal/external identity collisions must be rejected or deterministically namespaced; test both source types.
- External courses must require provider identity while internal courses must require the LMS reference; test both invalid cases.
- Nullable target levels and empty prerequisites must remain valid without implicit inference; test explicit null/empty values.
- Provenance must distinguish source facts from manual mappings and must not enable AI-derived runtime claims; test provenance validation and no model imports.
- Catalog fixture order and content must be deterministic and domain-neutral; test repeated loads and domain coverage.

---

### Task 1: Freeze the course catalog domain contract

**Files:**
- Create: `services/pai-backend/backend/app/course_catalog/__init__.py`
- Create: `services/pai-backend/backend/app/course_catalog/schemas.py`
- Create: `services/pai-backend/backend/tests/test_course_catalog_schemas.py`

**Interfaces:**
- Produces `CourseSourceType`, `CourseProfileStatus`, `CourseAvailability`, `CoverageType`, `CourseProvenance`, `CourseCapability`, `CoursePrerequisite`, `ExternalCourse`, `CourseCapabilityProfile`, and `NormalizedCourseCandidate`.
- Produces `CourseCapabilityProfile.to_normalized_candidate()` as the exact COURSE-REC-01B input projection.

- [ ] **Step 1: Write failing tests** for valid internal/external profiles, identity requirements, nullable levels, duration validation, duplicate capability rejection, provenance validation, normalized parity, and prerequisite shape.
- [ ] **Step 2: Run the focused test file** and verify it fails because the course catalog module does not exist.
- [ ] **Step 3: Implement minimal Pydantic schemas** using namespaced identity fields: `source_system`, `course_ref`, optional `provider_ref`, optional `provider_course_id`, version/status, semantic fields, metadata, and provenance.
- [ ] **Step 4: Run the focused tests** and verify they pass.
- [ ] **Step 5: Run the existing Core-AI schema/domain test subset** that covers semantic policy and learning prerequisites to detect namespace or enum conflicts.

### Task 2: Add deterministic internal and external catalog fixtures

**Files:**
- Create: `services/pai-backend/backend/app/course_catalog/fixtures.py`
- Create: `services/pai-backend/backend/app/course_catalog/providers.py`
- Create: `services/pai-backend/backend/tests/test_course_catalog_fixtures.py`

**Interfaces:**
- Produces `internal_course_catalog() -> tuple[CourseCapabilityProfile, ...]`.
- Produces `MockExternalProvider.list_courses() -> tuple[ExternalCourse, ...]` and `get_course(provider_course_id: str) -> ExternalCourse`.
- Produces deterministic catalog profiles without network, model, or recommendation calls.

- [ ] **Step 1: Write failing tests** for deterministic repeated loads, 20–30 internal and external fixtures, multiple domains, unavailable/unpublished variants, provider lookup, and no network/model imports.
- [ ] **Step 2: Run the focused fixture tests** and verify they fail because fixtures/provider are missing.
- [ ] **Step 3: Implement compact synthetic fixtures** spanning software/AI, sales, finance/accounting, HR/communication, with explicit manual/source-fact provenance and stable synthetic LMS/provider refs.
- [ ] **Step 4: Implement the pure mock provider** with stable lookup and no HTTP dependencies.
- [ ] **Step 5: Run fixture tests** and verify they pass.

### Task 3: Document LMS projection and normalized parity

**Files:**
- Create: `docs/research/COURSE-REC-01A-CATALOG-CAPABILITY-CONTRACT.md`
- Create: `test/results/course-rec-01a/domain-inventory.json`
- Create: `test/results/course-rec-01a/lms-course-contract.json`
- Create: `test/results/course-rec-01a/course-capability-profile-contract.json`
- Create: `test/results/course-rec-01a/external-course-contract.json`
- Create: `test/results/course-rec-01a/provider-contract.json`
- Create: `test/results/course-rec-01a/internal-external-parity.json`
- Create: `test/results/course-rec-01a/fixture-catalog-summary.json`

**Interfaces:**
- Documents the actual Frappe LMS Course fields inspected from the canonical repository and marks each as `DIRECT`, `TRANSFORM`, or `NOT_USED`.
- Documents the Core-AI contract and COURSE-REC-01B normalized input without adding LMS fields.

- [ ] **Step 1: Record the inspected LMS Course DocType/controller fields** and the existing Core domain inventory in JSON evidence.
- [ ] **Step 2: Write the human-readable contract** covering identity, ownership, capability coverage, nullable levels, prerequisites, metadata, availability, provenance, provider abstraction, lifecycle, parity, and deliberate deferrals.
- [ ] **Step 3: Add a compact example normalized candidate** and explicitly state that recommendation logic is not present.
- [ ] **Step 4: Validate all evidence JSON** with the repository’s JSON tooling.

### Task 4: Run scoped quality gates and produce final evidence

**Files:**
- Create: `test/results/course-rec-01a/validation-results.json`
- Create: `test/results/course-rec-01a/test-results.json`
- Create: `test/results/course-rec-01a/summary.json`

**Interfaces:**
- Evidence records exact commands and exit statuses for focused tests, Ruff, mypy, JSON validation, diff checks, and LMS no-change verification.

- [ ] **Step 1: Run focused pytest for the new course catalog tests.**
- [ ] **Step 2: Run scoped Ruff and mypy for the new module.**
- [ ] **Step 3: Run existing relevant Core-AI primitive tests if shared schemas were imported.**
- [ ] **Step 4: Scan the final diff for recommendation/model/provider-network implementation and verify none exists.**
- [ ] **Step 5: Verify the LMS repository has no modifications and run `git diff --check` in both repositories.**
- [ ] **Step 6: Write final evidence JSON without secrets or production data.**
- [ ] **Step 7: Leave all changes uncommitted and report exact status.**
