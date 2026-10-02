# CURR-02C — Confirmed CurriculumPlan to LMS Draft Materialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Materialize a confirmed Core-AI CurriculumPlan into one unpublished Frappe LMS Course tree with deterministic Chapters/Lessons, safe linkage, authorization, idempotency, and rollback.

**Architecture:** Keep CurriculumPlan ownership and confirmation in Core-AI. Add a dedicated pure adapter in `pai_frappe` that maps the authenticated canonical plan response to a small LMS draft spec, then let a Frappe-side service create LMS DocTypes inside a savepoint. Reuse only low-level LMS document creation conventions from the existing generated-course flow; keep its readiness and DTO contract untouched.

**Tech Stack:** Frappe/Python, Frappe DocTypes, Core-AI authenticated server-side bridge, unittest, local Docker Bench.

**Spec:** `/Users/mac/.codex/attachments/ebf8dd9f-137b-41e2-95c4-0bd64f641b03/Pasted text.txt`

## Global Constraints

- Only `CurriculumPlan.status == CONFIRMED` may materialize.
- LMS publication remains Frappe-owned and the created Course must always have `published = 0`.
- Do not route CurriculumPlan through `generated_course` or `READY_FOR_MATERIALIZATION`.
- Do not call a model, generate lesson content, modify the LMS UI, publish, commit, or push.
- Fetch the canonical plan through the authenticated server-side `pai_frappe` bridge; never trust a browser-supplied plan body.
- Repeated materialization of the same plan reference must return the existing draft rather than create duplicates.

## Review Focus

- A confirmed plan with multiple modules/lessons preserves source order and creates exactly one LMS tree.
- A non-confirmed, stale, cross-request, or malformed plan is rejected before LMS records are created.
- A second request for the same `plan_ref` returns the stored LMS course linkage.
- A mid-tree insert failure rolls back the Course/Chapter/Lesson records and leaves a retryable failed import record.
- Existing generated-course materialization keeps its readiness guard and behavior.

### Task 1: Freeze LMS and CurriculumPlan contracts with failing tests

**Files:**
- Create: `apps/pai_frappe/pai_frappe/tests/test_curriculum_materialization.py`
- Modify: `apps/pai_frappe/pai_frappe/tests/test_materialization.py`

**Interfaces:**
- Tests consume the current `CurriculumPlan` response shape, current Frappe DocType field names, and the new adapter/service names defined in later tasks.

- [ ] **Step 1: Write failing adapter tests** for title/description mapping, ordered module/chapter and lesson mapping, empty lesson content, optional metadata omission, and no model dependency.
- [ ] **Step 2: Run the new test module** with the Bench Python interpreter and confirm it fails because the adapter does not exist.
- [ ] **Step 3: Add failing service/API tests** for confirmed-only eligibility, request binding, authorization, source linkage, duplicate reuse, rollback, `published = 0`, and no publish call.
- [ ] **Step 4: Run the service tests** and confirm failures are caused by the missing CurriculumPlan materialization path rather than test setup.
- [ ] **Step 5: Add a generated-course regression assertion** that the existing `READY_FOR_MATERIALIZATION` path remains unchanged.

### Task 2: Implement the dedicated CurriculumPlan adapter

**Files:**
- Create: `apps/pai_frappe/pai_frappe/curriculum_materialization.py`
- Modify: `apps/pai_frappe/pai_frappe/tests/test_curriculum_materialization.py`

**Interfaces:**
- Produces `CurriculumCourseDraftSpec`, `CurriculumChapterDraftSpec`, and `CurriculumLessonDraftSpec` dataclasses plus `adapt_curriculum_plan(plan)`.
- `adapt_curriculum_plan(plan)` accepts the canonical JSON dict returned by Core-AI and returns an immutable/deterministic spec; it does not call Frappe or a model.

- [ ] **Step 1: Define the spec dataclasses** with only title, description, order, and safe optional source metadata; do not include generated-course sections or body content.
- [ ] **Step 2: Implement validation** for plan identity, `CONFIRMED` status, non-empty course title/description, unique positive module/lesson order, and non-empty module/lesson collections.
- [ ] **Step 3: Implement deterministic mapping** from `course_title`, `course_description`, modules, and lessons; retain source plan ref/version and omit objective refs, duration, lesson type, and estimated minutes unless a canonical LMS field exists.
- [ ] **Step 4: Keep lesson body empty** because the milestone does not generate instructional content; document this in code and tests.
- [ ] **Step 5: Run adapter tests** and confirm green.

### Task 3: Add source-plan linkage and Frappe materialization service

**Files:**
- Modify: `apps/pai_frappe/pai_frappe/pai_backend/doctype/pai_course_import/pai_course_import.json`
- Modify: `apps/pai_frappe/pai_frappe/pai_backend/doctype/pai_course_import/pai_course_import.py`
- Modify: `apps/pai_frappe/pai_frappe/api.py`
- Modify: `apps/pai_frappe/pai_frappe/tests/test_curriculum_materialization.py`

**Interfaces:**
- Add unique `source_plan_ref` and read-only `source_plan_version` to `PAI Course Import`.
- Add `materialize_curriculum_plan(name, plan_id)` as the whitelisted server-side entry point.
- Fetch `GET /api/v1/course-authoring/curriculum-plans/{plan_id}` through `_call_pai`, bind its `authoring_request_ref` to the local `PAI Request`, and require `CONFIRMED`.

- [ ] **Step 1: Add failing linkage assertions** proving the source plan reference is stored and unique.
- [ ] **Step 2: Add the DocType fields** without changing generated-course fields or LMS DocTypes.
- [ ] **Step 3: Implement canonical plan fetch and ownership binding** using `_get_request` and `_call_pai`; reject missing, wrong-request, non-confirmed, and invalid responses before creation.
- [ ] **Step 4: Implement idempotency** using unique `source_plan_ref`; return the linked Course for an existing Imported record and reject an in-progress duplicate safely.
- [ ] **Step 5: Create Course/Chapter/Lesson documents** with actual fields from the LMS JSON: Course title, description, short introduction, instructors, `published = 0`; Chapter course/title and child Lesson Reference; Lesson chapter/title/course with empty body and child Lesson Reference.
- [ ] **Step 6: Use a Frappe savepoint** around the tree creation. On failure roll back the savepoint, mark the import Failed with a safe error, and do not leave partial LMS records.
- [ ] **Step 7: Return stable references** including import name, plan ref/version, Course name, chapter names, lesson names, status, and `already_materialized`.
- [ ] **Step 8: Run service tests** and confirm green.

### Task 4: Runtime migration, authenticated live smoke, and evidence

**Files:**
- Create: `docs/research/CURR-02C-CURRICULUM-LMS-DRAFT-MATERIALIZATION.md`
- Create: `test/results/curr-02c/*.json`
- Modify: `apps/pai_frappe/pai_frappe/tests/test_materialization.py` only if regression coverage needs a precise assertion.

**Interfaces:**
- Runtime consumes the existing confirmed plan from CURR-02A and returns an unpublished LMS draft through Frappe only.

- [ ] **Step 1: Run the focused Core-AI bridge and Frappe test suites** plus existing generated-course materialization tests.
- [ ] **Step 2: Apply the DocType sync/migration in the local Bench** and verify the new linkage fields exist.
- [ ] **Step 3: Run live smoke**: get confirmed plan, materialize, inspect Course/Chapter/Lesson titles and order, verify `published = 0`, repeat materialization, and verify no duplicate Course.
- [ ] **Step 4: Capture before/after plan version/status and TrainingBrief revision count**; verify no curriculum or brief mutation and no model call.
- [ ] **Step 5: Search the diff for publish calls or `published = 1`, run `git diff --check`, scan evidence for secrets, and write the report with explicit remaining CURR-02B/02D gaps.
- [ ] **Step 6: Do not commit or push.**
