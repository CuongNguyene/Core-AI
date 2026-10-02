# CURR-02C — CONFIRMED CURRICULUMPLAN → LMS DRAFT MATERIALIZATION

## Status

COMPLETE

## 1. Repository

Core-AI: `/Users/mac/Developers/work/LMS/Core-AI`

Branch: `feat/deterministic-ai-course-planning-workspace`

HEAD: `2bd68ac23f51630ce60d08ab9a0f7516daff5d3f`

LMS: `/Users/mac/Developers/work/LMS/lms`

Branch: `dev`

HEAD: `eb1116f166c5ed79990206d99bfdb7960570e43d`

pai_frappe source: `/workspace/core-ai/apps/pai_frappe`, mounted into the active Bench at `/home/frappe/frappe-bench/apps/pai_frappe`; site `lms.localhost`.

Pre-existing changes: Core-AI contains the prior CURR-02A bridge/evidence changes and graphify output; LMS contains prior learning-planning UI/Cypress/docs changes. No unrelated LMS files were modified.

## 2. Existing Materialization Inventory

| Function | Source Artifact | Responsibility | Reused? | Notes |
|---|---|---|---|---|
| `get_generated_course` | `generated_course` | Validates `READY_FOR_MATERIALIZATION`, structure, sections, and ordering | No | Remains generated-course-specific |
| `get_source_hash` | `generated_course` | Deterministic source hash | No | Not used for CurriculumPlan semantics |
| `materialize_course` | `generated_course` | Creates LMS Course/Chapter/Lesson tree and updates `PAI Course Import` | Creation conventions only | Its lifecycle gate was not reused |
| `_resolve_course_instructor` | Local Frappe request | Validates Instructor role and admin override | Yes | Same server-side authorization helper |
| `adapt_curriculum_plan` | Confirmed `CurriculumPlan` | Maps canonical plan into LMS draft spec | New | Dedicated adapter in `curriculum_materialization.py` |
| `create_lms_draft` | Curriculum draft spec | Creates Course, Chapters, Lessons and child-table references | New | No model call and no publish call |

## 3. LMS DocType Contract

### LMS Course

Required fields: `title`, `description`, `short_introduction`, `instructors`.

Published field: `published`, explicitly set to `0`.

Other relevant fields: `status` remains LMS default `In Progress`; chapters are stored through the `chapters` child table.

### Course Chapter

Required fields: `course`, `title`.

Ordering: child-table `idx` follows adapter source order after sorting by module order.

### Course Lesson

Required fields: `chapter`, `title`; `course` is populated through the actual LMS field.

Content requirement: `body` is optional, so the adapter stores an empty string as a structural placeholder. No instructional content is fabricated.

Ordering: child-table `idx` follows lesson order within each module.

## 4. CurriculumPlan → LMS Mapping

| Curriculum Field | LMS Field | Transformation | Persisted? | Notes |
|---|---|---|---|---|
| `course_title` | `LMS Course.title` | Trimmed text | Yes | Canonical title |
| `course_description` | `description`, `short_introduction` | Trimmed text; short intro capped at 1000 chars | Yes | Same source description |
| `module.title` | `Course Chapter.title` | Trimmed text | Yes | One chapter per module |
| `module.order` | Chapter child-table `idx` | Sort ascending before append | Yes | Relative source order preserved |
| `lesson.title` | `Course Lesson.title` | Trimmed text | Yes | One lesson per plan lesson |
| `lesson.order` | Lesson child-table `idx` | Sort ascending within chapter | Yes | Relative source order preserved |
| `lesson.objective_refs` | None | Not mapped | No | No canonical LMS field |
| `estimated_minutes` | None | Not mapped | No | No canonical LMS field |
| `lesson_type` | None | Not mapped | No | No canonical LMS field |
| lesson content | `Course Lesson.body` | Empty structural placeholder | Yes | Content generation is out of scope |
| publication state | `LMS Course.published` | Constant `0` | Yes | Never auto-published |

## 5. Eligibility Contract

Required CurriculumPlan status: `CONFIRMED`.

Latest/current requirement: the exact plan must still be `CONFIRMED`; superseded plans are not eligible because the lifecycle marks them non-confirmed.

Ownership requirement: local `_get_request` ownership plus authenticated Core-AI actor context; returned `authoring_request_ref` must equal the local `PAI Request.pai_request_id`.

Rejected states: missing plan, plan reference mismatch, `PLANNED`, `VALIDATED`, `READY_FOR_REVIEW`, `NEEDS_REVISION`, `READY_FOR_CONFIRMATION`, `SUPERSEDED`, malformed response, and cross-request plan.

## 6. Adapter

Adapter: `pai_frappe.curriculum_materialization.adapt_curriculum_plan`.

Input: authenticated Core-AI `CurriculumPlanV1` JSON projection.

Output: immutable `CurriculumCourseDraftSpec` containing ordered `CurriculumChapterDraftSpec` and `CurriculumLessonDraftSpec` values.

Model call: NO.

Generated-course DTO reused: NO.

The Core-AI response contract was extended to include `authoring_request_ref`, `course_title`, and `course_description`, because the previous projection did not contain enough canonical data for safe LMS materialization.

## 7. Materialization API

Frappe function: `pai_frappe.api.materialize_curriculum_plan`.

Input: local `PAI Request` name, exact `plan_id`, optional validated Instructor account.

Output: import name, source plan reference/version, LMS Course reference, chapter references, lesson references, import status, and `already_materialized`.

Authorization: existing `Instructor`, `Moderator`, or `System Manager` authoring policy; local request ownership, Instructor validation, Core-AI signed actor identity, and request/plan binding are enforced. Browser-supplied curriculum bodies are not accepted.

## 8. Idempotency

Source plan ref: `PAI Course Import.source_plan_ref`.

Stored linkage: unique `source_plan_ref` → `PAI Course Import.lms_course`; `source_plan_version` is stored alongside it.

Duplicate behavior: same confirmed plan returns the existing Imported Course and `already_materialized=true`.

Second call created duplicate: NO. Live calls both returned `CRS-2026-00003`.

## 9. Version Behavior

Materialized plan: `curriculum-plan:08ee70cb8d70494f900ead1a54ff2f5b`.

Version: `2`.

Newer curriculum behavior: a newer revision must be explicitly confirmed and materialized as a separate future action; the existing LMS draft is not silently updated.

Existing LMS draft auto-updated: NO.

## 10. Transaction Safety

Failure scenario tested: exception during the multi-record tree creation.

Rollback/cleanup behavior: Frappe savepoint rollback is executed; the import record is retained as `Failed` with a bounded safe error so the operation can be retried. The failed tree is not left as a usable partial draft.

Result: PASS.

## 11. Live Smoke

Plan ref: `curriculum-plan:08ee70cb8d70494f900ead1a54ff2f5b`.

Plan status: `CONFIRMED`.

LMS Course: `CRS-2026-00003`.

Course published: `0`.

Chapter count: `2`.

Expected: `2`.

Lesson count: `4`.

Expected: `4`.

Ordering verified: YES.

Source linkage verified: YES (`PAI Course Import a3dojo05nk`).

Repeated materialization: PASS; no duplicate Course.

## 12. Curriculum Integrity

Plan changed: NO.

Plan version changed: NO; remains version `2`.

Plan status changed: NO; remains `CONFIRMED`.

TrainingBrief changed: NO; brief revision count was `2` before and `2` after the materialization/repeat smoke.

## 13. Publish Safety

Auto-publish: NO.

`published`: `0`.

Publish API called: NO.

Recent PAI backend logs for the smoke contain only authenticated `GET /curriculum-plans/{plan_id}` calls; no generation/model or publish request was emitted.

## 14. Negative Cases

| Case | Expected | Actual | Result |
|---|---|---|---|
| Non-confirmed plan | Reject before import lookup | Validation rejection | PASS |
| Cross-request plan | Permission denial | Permission rejection | PASS |
| Requested/ref returned plan mismatch | Reject | Validation rejection | PASS |
| Mid-tree failure | Roll back savepoint, mark Failed | Tested | PASS |
| Same plan twice | Reuse one Course | `CRS-2026-00003` reused | PASS |
| Publish path | No publish | `published=0`, no publish API | PASS |

## 15. Test Results

Adapter: `9 passed` in focused `pai_frappe` materialization tests.

Materialization: confirmed flow, idempotency, negative cases, and rollback covered; live smoke passed.

pai_frappe: `45 passed`.

Existing generated_course regression: included in the `44 passed` suite; existing readiness and materialization tests pass.

Core-AI curriculum/bridge: `72 passed`.

Runtime migration: `bench --site lms.localhost migrate` passed.

## 16. Changes Made

CORE_AI: extended `CurriculumPlanV1` with canonical request/title/description fields; no Core-AI materialization domain or database write added.

PAI_FRAPPE: added dedicated adapter/service, confirmed-only endpoint, unique source-plan linkage fields, idempotent response, and savepoint handling.

LMS: no LMS repository source changes.

TESTS: adapter, bridge, authorization, idempotency, rollback, unpublished draft, and generated-course regression tests.

DOCS: this report and execution plan.

EVIDENCE: `test/results/curr-02c/` with contract, mapping, negative-case, test, live-smoke, and summary artifacts.

## 17. Remaining Gap for CURR-02B

Backend capabilities now available for future UI wiring:

- Generate
- Review
- Feedback preview
- Revise
- Confirm
- Materialize

The planning UI and Materialize button remain out of scope for CURR-02C.

## 18. Remaining Gap for CURR-02D

Publish remains: NOT_IMPLEMENTED.

Required human role: future LMS Moderator/publication authority, according to LMS ownership rules.

## 19. Final Decision

Can a confirmed CurriculumPlan now become an LMS Course draft? YES.

Are modules materialized as Course Chapters? YES.

Are lessons materialized as Course Lessons? YES.

Is the course always unpublished? YES.

Is materialization idempotent? YES.

Was any model called? NO.

Is publish implemented? NO.

Can CURR-02B now wire the full planning UI through Materialize? YES, backend endpoint is available; UI implementation remains a separate milestone.

## 20. Git Status

Core-AI: modified/untracked CURR-02A and CURR-02C work plus pre-existing evidence; no commit created.

LMS: pre-existing UI/Cypress/docs changes only; no LMS source modified.

No commit. No push. No publish.
