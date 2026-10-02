# CURR-02A Curriculum Review and Revision Bridge Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the existing Core-AI CurriculumPlan feedback preview and immutable revision lifecycle through the server-side `pai_frappe` bridge without changing LMS UI, materialization, or publishing.

**Architecture:** Keep Core-AI authoritative for CurriculumPlan state and revision semantics. Add narrowly scoped IntegrationEnvelopeV1 routes for plan lookup, feedback preview, and feedback-to-revision; Frappe wrappers resolve the local PAI Request, then use the existing PAIClient for Bearer auth, signed actor context, ownership, request IDs, and safe errors.

**Tech Stack:** FastAPI, Pydantic v2, async service/repository layer, Frappe whitelisted Python APIs, pytest, unittest.

**Spec:** `/Users/mac/.codex/attachments/0a0594df-7672-4b86-9efe-6d74a26827c2/Pasted text.txt` (CURR-02A)

## Global Constraints

- Do not implement `AICoursePlanning.vue` curriculum UI.
- Do not materialize LMS Course/Chapter/Lesson.
- Do not publish courses.
- Do not change TrainingBrief revision APIs.
- Do not broaden supported curriculum feedback beyond the existing bounded `ADJUST_EFFORT` behavior.
- Every Core-AI call remains behind server-side `pai_frappe` with Bearer integration auth, Ed25519 actor context, ownership checks, X-Request-ID, and IntegrationEnvelopeV1.
- Do not touch Learning Path, Recommendation, ATS, or lesson-content generation.
- Do not commit or push.

## Review Focus

- Preview must not persist a CurriculumPlan: test repository plan count and latest version before/after preview.
- Feedback revision must preserve immutable lineage: test v2, `supersedes_plan_ref`, and unchanged v1.
- Unsupported actions must fail with the existing safe error contract: test `ADD_UNIT` and malformed effort payload.
- Stale or cross-owner plan access must remain denied: test Core-AI actor ownership and Frappe local request binding.
- TrainingBrief revisions must remain untouched: live evidence records brief revision count before/after curriculum revision.

### Task 1: Core-AI Curriculum Feedback Public Contract

**Files:**
- Modify: `services/pai-backend/backend/app/integration/course_authoring_schemas.py`
- Modify: `services/pai-backend/backend/app/integration/course_authoring_api.py`
- Test: `services/pai-backend/backend/tests/test_course_authoring_api.py`
- Test: `services/pai-backend/backend/tests/test_curriculum_conversation_adapter.py`

**Interfaces:**
- Consumes: `CurriculumRevisionService.get`, `adapt_curriculum_feedback`, and `apply_curriculum_feedback`.
- Produces: `GET /api/v1/course-authoring/curriculum-plans/{plan_id}`, `POST /api/v1/course-authoring/curriculum-plans/{plan_id}/feedback/preview`, and `POST /api/v1/course-authoring/curriculum-plans/{plan_id}/feedback`, all returning `IntegrationEnvelopeV1`.

- [ ] **Step 1: Write failing API tests** for plan-by-ref, non-persisting feedback preview, feedback revision lineage, unsupported feedback, and malformed feedback.
- [ ] **Step 2: Run the focused tests** and confirm they fail because the public DTO/routes do not exist.
- [ ] **Step 3: Add bounded DTOs**: feedback fields must match the existing internal contract (`kind`, `target_ref`, `estimated_minutes`); response must expose preview operations/before/after without raw internal exceptions.
- [ ] **Step 4: Add authenticated routes** using `verify_integration_api_key`, `get_signed_actor_context`, parent-request authorization, and existing `_error` mapping.
- [ ] **Step 5: Run the focused API tests** and confirm pass.

### Task 2: pai_frappe CurriculumPlan Wrappers

**Files:**
- Modify: `apps/pai_frappe/pai_frappe/api.py`
- Test: `apps/pai_frappe/pai_frappe/tests/test_client.py`

**Interfaces:**
- Consumes: Task 1 routes and existing `_call_pai`, `_get_request`, `_require_authoring_access`.
- Produces: `list_curriculum_plans`, `get_curriculum_plan`, `preview_curriculum_feedback`, and `revise_curriculum_plan` whitelisted server-side methods; existing `review_course_authoring_plan` and `confirm_course_authoring_plan` remain the only review/confirm methods.

- [ ] **Step 1: Write failing wrapper tests** asserting Core route, HTTP method, request body, envelope parsing, and safe upstream rejection mapping.
- [ ] **Step 2: Run the wrapper tests** and confirm failure from missing wrappers.
- [ ] **Step 3: Implement wrappers** with local request ownership binding and no browser-visible credentials; feedback revision must call the feedback route, not TrainingBrief APIs.
- [ ] **Step 4: Run the focused `pai_frappe` suite** and confirm pass.

### Task 3: Verification Evidence and Live Bridge Smoke

**Files:**
- Create: `docs/research/CURR-02A-CURRICULUM-REVIEW-REVISION-BRIDGE.md`
- Create: `test/results/curr-02a/current-lifecycle-inventory.json`
- Create: `test/results/curr-02a/core-api-gap-analysis.json`
- Create: `test/results/curr-02a/feedback-contract.json`
- Create: `test/results/curr-02a/revision-semantics.json`
- Create: `test/results/curr-02a/bridge-wrapper-inventory.json`
- Create: `test/results/curr-02a/core-api-test-results.json`
- Create: `test/results/curr-02a/pai-frappe-test-results.json`
- Create: `test/results/curr-02a/live-bridge-smoke.json`
- Create: `test/results/curr-02a/negative-cases.json`
- Create: `test/results/curr-02a/summary.json`

**Interfaces:**
- Consumes: passing Task 1/2 tests and an existing safe confirmed TrainingBrief/CurriculumPlan in the local runtime.
- Produces: redacted evidence proving bridge flow, version lineage, auth/ownership, TrainingBrief separation, and no materialization/publish.

- [ ] **Step 1: Run focused Core-AI and pai_frappe suites** covering curriculum planning/revision, course-authoring API, integration auth, ownership, request signing, and bridge wrappers.
- [ ] **Step 2: Run the live Frappe server-side flow**: get/list, preview, verify no persistence, feedback revision, review, confirm, reload.
- [ ] **Step 3: Verify no materialization/publish calls** and no TrainingBrief revision count change.
- [ ] **Step 4: Write redacted evidence and report** with no secrets, raw signatures, or sensitive payloads.
- [ ] **Step 5: Run final `git diff --check`, status, and secret scan**; leave changes uncommitted and unpushed.

No commit step is included because CURR-02A explicitly forbids commit and push.
