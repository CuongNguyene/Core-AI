# CURR-02A — Curriculum Review & Revision Bridge Completion

## Scope

CURR-02A completes the server-side CurriculumPlan review/revision bridge. It does not add LMS UI, course materialization, or publish behavior.

## Contract

The supported lifecycle is:

```text
Confirmed TrainingBrief
  -> CurriculumPlan
  -> get/list
  -> feedback preview
  -> feedback revision
  -> review
  -> confirm
```

Feedback is intentionally bounded to the existing service contract:

```json
{
  "feedback": {
    "kind": "ADJUST_EFFORT",
    "target_ref": "<lesson_ref>",
    "estimated_minutes": 30
  },
  "rationale": "optional reviewer note"
}
```

The preview is non-persisting. The revision creates a new immutable plan version with `supersedes_plan_ref`. Unsupported actions remain rejected; they are not silently translated into a different curriculum change.

## Public Core-AI surface

Added:

- `GET /api/v1/course-authoring/curriculum-plans/{plan_id}`
- `POST /api/v1/course-authoring/curriculum-plans/{plan_id}/feedback/preview`
- `POST /api/v1/course-authoring/curriculum-plans/{plan_id}/feedback`

Existing list, review, explicit revisions, and confirm routes remain unchanged. All use the existing integration API key, signed actor context, ownership authorization, request ID, and `IntegrationEnvelopeV1` path.

## pai_frappe bridge

Added server-side wrappers:

- `list_curriculum_plans`
- `get_curriculum_plan`
- `preview_curriculum_feedback`
- `revise_curriculum_plan`

Existing `review_course_authoring_plan` and `confirm_course_authoring_plan` remain the review/confirm entry points. TrainingBrief functions `clarify_authoring_brief` and `revise_authoring_brief` are not called by CurriculumPlan revision.

## Verification

Live Frappe bridge smoke used existing request `dboeftbdlp` and created no new TrainingBrief. Preview left the plan count at 1. The supported `ADJUST_EFFORT` feedback created version 2, preserved version 1, reviewed and confirmed version 2, and reloaded it as `CONFIRMED`. TrainingBrief revision count stayed at 2.

Focused suites:

- Core-AI curriculum/course-authoring/auth/error suite: 72 passed.
- pai_frappe focused unittest suite: 36 passed.

Evidence JSON is in `test/results/curr-02a/`.

## Explicit non-scope

- No `AICoursePlanning.vue` changes.
- No `LMS Course`, `Course Chapter`, or `Course Lesson` materialization.
- No publish action.
- No Learning Path, Recommendation, ATS, or lesson-content changes.
- No commit or push.
