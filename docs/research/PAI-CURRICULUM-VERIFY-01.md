# PAI-CURRICULUM-VERIFY-01 — EXISTING CURRICULUM INVENTORY + LIVE GAP ANALYSIS

## Status

COMPLETE

## 1. Repository

Canonical repo: `/Users/mac/Developers/work/LMS/Core-AI`
Branch: `feat/deterministic-ai-course-planning-workspace`
HEAD: `2bd68ac23f51630ce60d08ab9a0f7516daff5d3f`
Pre-existing changes: untracked `graphify-out/` only; no tracked source diff. LMS was not modified.

## 2. Existing Curriculum Implementation

| Layer | File | Object/Function | Status | Notes |
|---|---|---|---|---|
| Brief contract | `services/pai-backend/backend/app/course_authoring/brief_revision_schemas.py` | `AuthoringBriefRevision`, `AuthoringBriefRevisionStatus` | EXISTS_AND_VERIFIED | `CONFIRMED` is an explicit lifecycle state. |
| Brief persistence | `services/pai-backend/backend/app/course_authoring/brief_revision_repository.py` | `SqlAlchemyAuthoringBriefRevisionRepository` | EXISTS_AND_VERIFIED | Versioned revisions and latest lookup are persisted. |
| Planning input | `services/pai-backend/backend/app/curriculum_planning/schemas.py` | `CurriculumPlanningContext` | EXISTS_AND_VERIFIED | Context is derived from an authoring request and confirmed revision payload. |
| Planner | `services/pai-backend/backend/app/curriculum_planning/planner.py` | `ModelGatewayCurriculumPlanner` | EXISTS_NOT_LIVE_VERIFIED | Uses production `ModelGateway.infer_structured`. |
| Deterministic fallback | `services/pai-backend/backend/app/curriculum_planning/planner.py` | `DeterministicCurriculumPlanner` | EXISTS_AND_VERIFIED | Used for `GAP_DRIVEN`; goal-driven path uses the model gateway. |
| Output schema | `services/pai-backend/backend/app/curriculum_planning/schemas.py` | `CurriculumPlanningOutput` | EXISTS_AND_VERIFIED | Strict Pydantic structured-output contract. |
| Domain plan | `services/pai-backend/backend/app/curriculum_planning/schemas.py` | `CurriculumPlan` | EXISTS_AND_VERIFIED | Immutable domain object with objectives, modules, lessons and metadata. |
| Deterministic validation | `services/pai-backend/backend/app/curriculum_planning/validation.py` | `collect_curriculum_plan_validation`, `validate_curriculum_plan` | EXISTS_AND_VERIFIED | Blocking validation raises `CurriculumPlanValidationError`. |
| Workload normalization | `services/pai-backend/backend/app/curriculum_planning/workload.py` | `allocate_curriculum_plan_workload` | EXISTS_AND_VERIFIED | Applied before final validation. |
| Planning service | `services/pai-backend/backend/app/curriculum_planning/service.py` | `CurriculumPlanningService.plan` | EXISTS_NOT_LIVE_VERIFIED | Resolves confirmed brief, plans, versions and persists. |
| Persistence | `services/pai-backend/backend/app/content_generation/repository.py` | `SqlAlchemyContentGenerationRepository` | EXISTS_AND_VERIFIED | `curriculum_plans` and failed planning attempts are stored in SQLAlchemy tables. |
| API | `services/pai-backend/backend/app/integration/course_authoring_api.py` | `POST /api/v1/course-authoring/requests/{request_id}/plan` | EXISTS_AND_VERIFIED | Signed actor context is required. |
| Reload API | `services/pai-backend/backend/app/integration/course_authoring_api.py` | `GET /api/v1/course-authoring/requests/{request_id}/plan` | EXISTS_AND_VERIFIED | Returns latest persisted plan after authorization. |
| Model provider | `services/pai-backend/backend/app/model_gateway/service.py`, `main.py` | `ModelGatewayService`, provider composition | EXISTS_NOT_LIVE_VERIFIED | Adapter and structured-output repair path exist; current local config is placeholder. |

## 3. Confirmed Brief → Curriculum Trace

Confirmed Brief
→ `CurriculumPlanningService.plan(request_id, actor)`
→ `SqlAlchemyCourseAuthoringRepository.get` through `CourseAuthoringService`
→ `SqlAlchemyAuthoringBriefRevisionRepository.latest(request.id)` when workflow is `sep-08a-v1`
→ reject unless revision status is `CONFIRMED`
→ `_request_from_confirmed_payload`
→ `CourseGenerationContextBuilder.build`
→ `planning_context_from_generation_context`
→ `ModelGatewayCurriculumPlanner.plan`
→ `ModelGatewayService.infer_structured(..., CurriculumPlanningOutput)`
→ provider adapter (`CTPAIGatewayProvider`, `LocalVLLMProvider`, or `GeminiProvider` selected by config)
→ Pydantic `CurriculumPlanningOutput` parsing
→ `_from_model_output`
→ workload allocation and `validate_curriculum_plan`
→ assign persisted `curriculum-plan:{uuid}`, version and `authoring_brief_revision_ref`
→ `SqlAlchemyContentGenerationRepository.create_curriculum_plan`
→ `GET /requests/{request_id}/plan` → `get_latest` → reload.

The `GAP_DRIVEN` branch uses `DeterministicCurriculumPlanner` and does not require a model call; the goal-driven branch is the relevant real-model path for this milestone.

## 4. Input Contract

Generation input: `request_id` in `POST /api/v1/course-authoring/requests/{request_id}/plan`.
Pinned revision: the service resolves the latest `CONFIRMED` revision and stores its ID in `planning_metadata.authoring_brief_revision_ref`; there is no caller-supplied `confirmed_revision_id` parameter.
Allowed lifecycle state: `AuthoringBriefRevisionStatus.CONFIRMED` for `sep-08a-v1` requests.
Rejected states: missing revision, `DRAFT`, `NEEDS_CLARIFICATION`, and `READY_FOR_CONFIRMATION` produce `authoring_brief_not_confirmed`.
Ownership/auth: signed actor context is required by the integration route; the authoring repository checks actor access to the request.
Contract classification: `NEEDS_HARDENING` — the current latest-confirmed lookup is tested and safe for the existing API, but exact revision pinning is implicit rather than caller-explicit and can be exposed to latest-state drift under concurrent revision changes. No redesign was implemented.

## 5. CurriculumPlan Contract

| Field | Type | Required | Source/Generated | Notes |
|---|---|---:|---|---|
| `id` | `str` | yes | persistence internal | Immutable `curriculum-plan:{uuid}`. |
| `authoring_request_ref` | `str` | yes | source from request | Links plan to authoring request. |
| `version` | `int` | yes | persistence internal | Incremented from prior plans. |
| `supersedes_plan_ref` | `str \| None` | no | persistence internal | Immutable revision chain. |
| `course_title` | `str` | yes | source/context | From authoring request. |
| `course_description` | `str` | yes | source/model-derived | Current goal-driven path uses training goal. |
| `normalized_duration` | `NormalizedTrainingDuration` | yes | deterministic-derived | Normalized from brief constraints. |
| `learning_objectives` | `list[CurriculumObjective]` | yes | model-generated or source brief | Each has statement, measurable outcome, sequence and origin. |
| `modules` | `list[CurriculumModulePlan]` | yes | model-generated or deterministic | Ordered modules with objective refs and lessons. |
| `estimated_total_learning_hours` | `float` | yes | model/context-derived | Checked against module allocation. |
| `planning_metadata` | `dict[str, str]` | no | mixed provenance/governance | Holds prompt/policy, revision ref, strategy and review metadata. |
| `status` | `CurriculumPlanStatus` | yes | governance | `PLANNED`, `VALIDATED`, review states and `CONFIRMED`. |
| `CurriculumObjective.statement` | `str` | yes | model/source | Objective text. |
| `CurriculumObjective.measurable_outcome` | `str` | yes | model/source | Measurable outcome. |
| `CurriculumObjective.sequence` | `int` | yes | deterministic-derived | Contiguous order. |
| `CurriculumModulePlan.lessons` | `list[CurriculumLessonPlan]` | yes | model/deterministic | Non-empty ordered lesson list. |
| `CurriculumLessonPlan.objective_refs` | `list[str]` | yes | model/deterministic | Explicit coverage links. |
| `CurriculumLessonPlan.estimated_minutes` | `int` | yes | model/deterministic | Positive workload estimate. |
| `CurriculumLessonPlan.lesson_type` | `str` | yes | model/deterministic | Used by workload policy. |
| `CurriculumPlanValidationReport` | report object | derived | deterministic | Issues, counts, coverage and unknown refs; not a top-level plan field. |

Prerequisites and assessment strategy are not first-class `CurriculumPlan` fields in this contract. Brief prerequisites can enter the context, but the current plan schema does not persist a dedicated prerequisite or assessment-strategy object. Model/provider metadata is represented indirectly in `planning_metadata` and failed attempts; successful plan persistence does not store the full `InferenceAuditMetadata`.

## 6. Validator Inventory

| Validator | Production-wired | Blocking | Findings | Notes |
|---|---:|---:|---:|---|
| Pydantic `CurriculumPlanningOutput` | yes | yes | schema errors | Structured model response must match registered schema. |
| Objective ID/statement uniqueness | yes | yes | yes | `collect_curriculum_plan_validation`. |
| Objective sequence continuity | yes | yes | yes | Contiguous `1..N`. |
| Module ID/order continuity | yes | yes | yes | Duplicate and ordering checks. |
| Lesson ID/order continuity | yes | yes | yes | Duplicate and ordering checks within modules. |
| Objective reference validity | yes | yes | yes | Unknown refs and uncovered objectives are reported. |
| Module/lesson duration allocation | yes | yes | yes | 20% allocation tolerance and positive duration checks. |
| Workload category/type consistency | yes | yes | yes | Unsupported lesson types block finalization. |
| Microlearning effort range/target | conditional | yes | yes | Wired when `sep-08b-v1` strategy is active. |
| Prerequisite consistency | no dedicated validator found | no | no | Brief prerequisite text is not a dedicated plan validation dimension. |
| Assessment alignment | no dedicated curriculum validator found | no | no | Assessment exists elsewhere, but is not part of this plan validator. |
| Cognitive/Bloom level | no dedicated validator found | no | no | Not a current CurriculumPlan contract field. |

Invalid candidates are rejected before successful plan persistence. Failed model candidates are persisted as `CurriculumPlanningAttempt` with sanitized candidate and validation issues.

## 7. Model Runtime

Provider abstraction: `ModelGateway` protocol → `ModelGatewayService` → `ProviderRegistry` → configured adapter.
Configured provider: `gemini`.
Configured model: `gemini-3.5-flash-lite`.
Placeholder: NO.
Credentials available: YES; live Gemini call returned HTTP 200. The key is not recorded in evidence.
Structured output: YES in architecture; JSON object/schema is requested and Pydantic parsing plus one bounded repair retry is implemented.
Timeout: configured `MODEL_TIMEOUT_SECONDS=200`, provider-specific timeout mapping exists.
Retry: configured `MODEL_MAX_RETRIES=1`; provider adapters implement bounded retry/error mapping.
Provenance: `InferenceAuditMetadata` captures provider, model, revision, prompt/schema versions, routing, latency, usage and outcome; successful `CurriculumPlan` only carries selected metadata, while failed attempts persist provider/model/prompt and sanitized candidate.

Runtime classification: `MODEL_RUNTIME_READY`.

## 8. Model Smoke

Real model called: YES

Provider: `gemini`
Model: `gemini-3.5-flash-lite`
Structured response: PASS; HTTP 200.
Schema parse: PASS; 3 objectives and 3 modules parsed as `CurriculumPlanningOutput`.
Latency: 7458 ms.
Errors: none; attempt 1 succeeded. No secret or sensitive prompt was logged.

## 9. Live Curriculum Generation

Confirmed brief ref: `course-authoring-request-33df73339b5943048bebd21705b89b7a`.
Confirmed revision ref: `authoring-brief-revision:036a67dd60924262aa5ae79e23f024a0` (version 1).
Generation service: `CurriculumPlanningService.plan`.
Plan ID: `curriculum-plan:b6ea4666438a47618eeb4b5e7bc968c1`.
Schema validation: PASS; API returned `201`.
Deterministic validation: PASS; generated plan contained 3 objectives, 3 modules and 7 lessons.
Findings: no blocking validation findings.
Provider/model metadata: Gemini / `gemini-3.5-flash-lite`; raw smoke audit succeeded on attempt 1.

## 10. Persistence / Reload

Persisted:
YES — live API returned `201` and repository implementation/focused tests pass.

Reloaded:
YES — live API GET returned `200` with the same `plan_ref`; repository/API round-trip tests also pass.

Source brief preserved:
YES — live request used the confirmed revision and persisted `authoring_request_ref` plus `authoring_brief_revision_ref`; exact revision pin is metadata rather than a dedicated field.

Validation findings preserved:
YES for failed planning attempts (`CurriculumPlanningAttempt.validation_issues`); successful plans have no dedicated validation-report column.

Model provenance preserved:
PARTIAL — live provider/model was verified and selected planning metadata is persisted, but full successful `InferenceAuditMetadata` is not persisted as a dedicated object.

## 11. Negative Cases

| Case | Expected | Actual | PASS/FAIL |
|---|---|---|---|
| unconfirmed brief | reject before planning | `authoring_brief_not_confirmed` covered by service tests | PASS |
| missing brief/revision | stable not-found/not-confirmed error | covered by authoring/API tests | PASS |
| stale/invalid curriculum revision | reject stale/non-latest revision | revision service tests cover latest-bound confirmation; brief generation uses latest lookup | PASS / hardening noted |
| unauthorized actor | reject signed actor without ownership | authoring hardening tests pass | PASS |
| invalid model JSON | bounded repair then safe failure | model gateway tests pass without raw content logging | PASS |
| schema-invalid model output | bounded repair then `StructuredOutputFailedError` | model gateway tests pass | PASS |
| validator failure | reject persistence and persist diagnostic attempt | planning tests and repository tests pass | PASS |
| provider timeout | bounded retry then mapped timeout | Gemini/local provider tests pass | PASS |
| provider rejection | mapped provider error, no sensitive body | provider tests pass | PASS |
| duplicate/retry behavior | immutable plan/attempt IDs; explicit version chain | repository tests pass; no live idempotency acceptance run | PASS / live unverified |

## 12. Blockers

| Blocker | Classification | File/Function | Impact | Smallest Next Action |
|---|---|---|---|---|
| Exact revision is implicit latest lookup | `IMPLEMENTATION_GAP` / hardening | `CurriculumPlanningService.plan` | Concurrent revision changes can make source selection less explicit than the acceptance contract requires. | Add a focused explicit confirmed-revision pin only after product contract approval; not changed in this milestone. |
| Full successful audit not persisted | `IMPLEMENTATION_GAP` | `CurriculumPlanRecord`, `_curriculum_plan_record` | Reload proves plan content but not complete model audit provenance. | Decide whether successful audit persistence is required; avoid schema change until confirmed. |
| No dedicated prerequisite/assessment/Bloom fields | `IMPLEMENTATION_GAP` | `CurriculumPlan` schema | Limits those dimensions in deterministic curriculum validation. | Freeze current contract first; do not redesign in this verification milestone. |

## 13. Changes Made

CONFIG: rebuilt/restarted Docker `backend` service with the supplied Gemini environment; no repository config files changed.
CODE: none.
TEST: none.
DOC: this report only.
EVIDENCE: `test/results/pai-curriculum-verify-01/`.
LMS: unchanged.

## 14. Test Results

- `UV_CACHE_DIR=/tmp/pai-curriculum-uv-cache uv run pytest -q tests/test_curriculum_planning.py tests/test_curriculum_planning_api.py tests/test_curriculum_revision_service.py tests/test_curriculum_conversation_adapter.py tests/test_course_generation.py tests/test_hierarchical_generation.py tests/test_course_generation_repository.py tests/test_model_gateway.py tests/test_local_vllm.py tests/test_gemini_provider.py tests/test_provider_selection.py` — **97 passed**.
- `UV_CACHE_DIR=/tmp/pai-curriculum-uv-cache uv run pytest -q tests/test_course_authoring_api.py tests/test_course_authoring_service.py tests/test_course_authoring_revision.py tests/test_course_generation_api.py tests/test_integration_api.py tests/test_course_authoring_hardening.py tests/test_authoring_brief_revision.py` — **42 passed**.
- Initial command including a non-existent `tests/test_authoring_brief_revision_api.py` was corrected; it ran no tests and is not counted as a product failure.
- Raw structured model smoke: **PASS** — Gemini HTTP 200, schema parse pass, 7458 ms, attempt 1.
- Live route flow: **PASS** — POST `/api/v1/course-authoring/requests/{request_id}/plan` returned 201; GET returned 200 with identical plan reference.

## 15. End-of-Day Acceptance

CONFIRMED TrainingBrief:
PASS — existing confirmed-revision guard and tests.

Real model:
PASS

Schema-valid CurriculumPlan:
PASS

Deterministic validation:
PASS

Persist:
PASS

Reload:
PASS

## 16. Final Decision

Is AI Curriculum Plan live end-to-end?
YES.

Is model runtime the blocker?
NO.

Is CurriculumPlan contract already sufficient?
YES for the existing objective/module/lesson planning flow; NO if prerequisite, assessment strategy, Bloom level or full successful audit provenance are required as first-class fields.

Is major redesign required?
NO for this milestone.

What is the exact next action for the afternoon?
Keep the verified Gemini runtime and decide whether to harden explicit confirmed-revision pinning and successful inference-audit persistence; do not redesign the curriculum domain before that contract decision.

## 17. Git Status

Core-AI:

```text
branch: feat/deterministic-ai-course-planning-workspace
tracking: origin/feat/deterministic-ai-course-planning-workspace
status: clean except for untracked graphify-out/
```

LMS:
UNCHANGED

STOP.

Do not implement LMS UI.
Do not implement Learning Path.
Do not implement Recommendation.
Do not implement ATS integration.
Do not commit.
Do not push.
