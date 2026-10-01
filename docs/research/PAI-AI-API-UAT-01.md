# PAI-AI-API-UAT-01 — CORE-AI API INVENTORY + FUNCTIONAL SMOKE

## Status

COMPLETE

Discovery is complete; COMPLETE means every registered route has an explicit verification status, not that every API is live-ready.

## 1. Environment

- Branch: `feat/deterministic-ai-course-planning-workspace` (recovered verification clone; no commit/push in this milestone)
- HEAD: `ceea727` (pre-existing bundled branch snapshot)
- Core-AI health: `200`
- Postgres: `up`
- Redis: `up`
- MinIO: `up`, `/minio/health/ready` `200`
- ClamAV: TCP `3310` ready
- Workers: `not running` (`worker`, `course-generation-worker` absent)
- Model provider: `local-vllm`, model placeholder `replace-with-approved-model`; no model service running

## 2. Route Inventory Summary

- OpenAPI: **116 paths / 131 operations**
- Source cross-check: FastAPI `create_app()` includes 21 routers; decorator scan matched registered route modules.
- Health/internal routes: 3 health operations.
- Legacy/deferred routes: content generation and model-backed generation paths are retained and explicitly classified.

| Domain | Endpoint count |
| --- | ---: |
| ADMIN_INTERNAL | 12 |
| ASSESSMENT | 5 |
| CANDIDATE_PROFILE | 15 |
| CAPABILITY_ANALYSIS | 11 |
| CONTENT_GENERATION | 2 |
| COURSE_AUTHORING | 23 |
| COURSE_CAPABILITY | 8 |
| CV_DOCUMENT | 1 |
| CV_EXTRACTION | 12 |
| HEALTH | 3 |
| INTEGRATION_AUTH | 5 |
| INTERNAL_RECOMMENDATION | 3 |
| LEARNING_NEED | 3 |
| LEARNING_PATH | 8 |
| ROLE_GOVERNANCE | 14 |
| ROLE_PROFILE | 6 |

## 3. Capability Summary

| Capability | API | Implemented | Automated tests | Live smoke | Storage | Model | Worker | LMS | User UAT | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Health / integration auth | True | True | PASS/covered | PASS | False | False | False | True | PASS for bridge | VERIFIED |
| Course authoring deterministic brief | True | True | PASS/covered | PASS baseline + UAT | False | False | False | True | PASS | VERIFIED |
| Course authoring conversation / planning / generation | True | registered; not live verified | covered with adjacent suites | NOT_RUN | False | True | True | False | NO | BLOCKED_BY_MODEL |
| CV document / extraction | True | True | API + worker suites | NOT_RUN | True | True | True | False | NO | BLOCKED_BY_DEPENDENCY |
| Candidate profile | True | True | API + domain suites | NOT_RUN | False | False | False | False | NO | NOT_YET_VERIFIED |
| JD / role profile / governance | True | True | API + governance suites | NOT_RUN | False | some authoring paths | False | False | NO | NOT_YET_VERIFIED |
| Capability analysis / gap projection | True | True | API suite has auth fixture drift | NOT_RUN | False | False | False | False | NO | CONTRACT_DEFECT |
| Learning need / authoring projections | True | True | API/openapi suites | NOT_RUN | False | False | False | False | NO | NOT_YET_VERIFIED |
| Instructional design HTTP API | False | internal modules only | internal contract suites | NOT_EXPOSED | False | True | False | False | NO | NOT_EXPOSED |
| Curriculum planning | True | True | curriculum planning API suites | NOT_RUN | False | True | False | False | NO | BLOCKED_BY_MODEL |
| Course capability / internal recommendation | True | True | matching/competency suites | NOT_RUN | False | False | False | False | NO | NOT_YET_VERIFIED |
| External recommendation | False | False | NO_TEST | NOT_EXPOSED | False | False | False | False | NO | NOT_EXPOSED |
| Learning path | True | True | learning API + integration suites | NOT_RUN | False | True | False | False | NO | NOT_YET_VERIFIED |
| Content generation / legacy generation | True | legacy/deferred route registered | suite blocked by fixture drift | NOT_RUN | False | True | True | False | NO | DEFERRED |

## 4. Endpoint Inventory

| Method | Path | Domain | Auth | Dependencies | Tests | Live | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GET | /api/v1/authoring/instructional-blueprints/{blueprint_id} | LEARNING_NEED | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_learning_authoring_api.py,tests/test_learning_openapi.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /api/v1/authoring/learning-needs/{learning_need_id} | LEARNING_NEED | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_learning_authoring_api.py,tests/test_learning_openapi.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /api/v1/authoring/learning-objectives/{objective_id} | LEARNING_NEED | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_learning_authoring_api.py,tests/test_learning_openapi.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /api/v1/candidates | CANDIDATE_PROFILE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_candidate_api.py,tests/test_candidate_governance.py,tests/test_candidate_profile.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/candidates | CANDIDATE_PROFILE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_candidate_api.py,tests/test_candidate_governance.py,tests/test_candidate_profile.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /api/v1/candidates/{candidate_id} | CANDIDATE_PROFILE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_candidate_api.py,tests/test_candidate_governance.py,tests/test_candidate_profile.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/candidates/{candidate_id}/accept | CANDIDATE_PROFILE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_candidate_api.py,tests/test_candidate_governance.py,tests/test_candidate_profile.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /api/v1/candidates/{candidate_id}/claims/{claim_id}/evidence | CANDIDATE_PROFILE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_candidate_api.py,tests/test_candidate_governance.py,tests/test_candidate_profile.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /api/v1/candidates/{candidate_id}/cv/versions | CANDIDATE_PROFILE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_candidate_api.py,tests/test_candidate_governance.py,tests/test_candidate_profile.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/candidates/{candidate_id}/cv/versions | CANDIDATE_PROFILE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_candidate_api.py,tests/test_candidate_governance.py,tests/test_candidate_profile.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/candidates/{candidate_id}/documents | CANDIDATE_PROFILE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_candidate_api.py,tests/test_candidate_governance.py,tests/test_candidate_profile.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /api/v1/candidates/{candidate_id}/extraction-status | CANDIDATE_PROFILE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_candidate_api.py,tests/test_candidate_governance.py,tests/test_candidate_profile.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /api/v1/candidates/{candidate_id}/profiles | CANDIDATE_PROFILE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_candidate_api.py,tests/test_candidate_governance.py,tests/test_candidate_profile.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/candidates/{candidate_id}/profiles | CANDIDATE_PROFILE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_candidate_api.py,tests/test_candidate_governance.py,tests/test_candidate_profile.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/candidates/{candidate_id}/profiles/{profile_id}/accept | CANDIDATE_PROFILE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_candidate_api.py,tests/test_candidate_governance.py,tests/test_candidate_profile.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/candidates/{candidate_id}/profiles/{profile_id}/reject | CANDIDATE_PROFILE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_candidate_api.py,tests/test_candidate_governance.py,tests/test_candidate_profile.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/candidates/{candidate_id}/reject | CANDIDATE_PROFILE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_candidate_api.py,tests/test_candidate_governance.py,tests/test_candidate_profile.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/candidates/{candidate_id}/request-revision | CANDIDATE_PROFILE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_candidate_api.py,tests/test_candidate_governance.py,tests/test_candidate_profile.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/content-generation/requests | CONTENT_GENERATION | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | MODEL_PROVIDER,POSTGRES,REDIS,WORKER | tests/test_content_generation_api.py,tests/test_content_generation.py | NOT_RUN | DEFERRED |
| GET | /api/v1/content-generation/results/{result_id} | CONTENT_GENERATION | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | MODEL_PROVIDER,POSTGRES,REDIS,WORKER | tests/test_content_generation_api.py,tests/test_content_generation.py | NOT_RUN | DEFERRED |
| POST | /api/v1/course-authoring/curriculum-plans/{plan_id}/confirm | COURSE_AUTHORING | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_course_authoring_api.py,tests/test_course_authoring_revision_api.py,tests/test_course_generation_api.py,tests/test_curriculum_planning_api.py | PASS | VERIFIED |
| POST | /api/v1/course-authoring/curriculum-plans/{plan_id}/review | COURSE_AUTHORING | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_course_authoring_api.py,tests/test_course_authoring_revision_api.py,tests/test_course_generation_api.py,tests/test_curriculum_planning_api.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/course-authoring/curriculum-plans/{plan_id}/revisions | COURSE_AUTHORING | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_course_authoring_api.py,tests/test_course_authoring_revision_api.py,tests/test_course_generation_api.py,tests/test_curriculum_planning_api.py | PASS | VERIFIED |
| GET | /api/v1/course-authoring/requests | COURSE_AUTHORING | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_course_authoring_api.py,tests/test_course_authoring_revision_api.py,tests/test_course_generation_api.py,tests/test_curriculum_planning_api.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/course-authoring/requests | COURSE_AUTHORING | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_course_authoring_api.py,tests/test_course_authoring_revision_api.py,tests/test_course_generation_api.py,tests/test_curriculum_planning_api.py | PASS | VERIFIED |
| GET | /api/v1/course-authoring/requests/{request_id} | COURSE_AUTHORING | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_course_authoring_api.py,tests/test_course_authoring_revision_api.py,tests/test_course_generation_api.py,tests/test_curriculum_planning_api.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/course-authoring/requests/{request_id}/clarify | COURSE_AUTHORING | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_course_authoring_api.py,tests/test_course_authoring_revision_api.py,tests/test_course_generation_api.py,tests/test_curriculum_planning_api.py | PASS | VERIFIED |
| POST | /api/v1/course-authoring/requests/{request_id}/conversation/respond | COURSE_AUTHORING | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | MODEL_PROVIDER,POSTGRES | tests/test_course_authoring_api.py,tests/test_course_authoring_revision_api.py,tests/test_course_generation_api.py,tests/test_curriculum_planning_api.py | BLOCKED | BLOCKED_BY_MODEL |
| GET | /api/v1/course-authoring/requests/{request_id}/curriculum-plans | COURSE_AUTHORING | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_course_authoring_api.py,tests/test_course_authoring_revision_api.py,tests/test_course_generation_api.py,tests/test_curriculum_planning_api.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/course-authoring/requests/{request_id}/generate | COURSE_AUTHORING | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | MODEL_PROVIDER,POSTGRES | tests/test_course_authoring_api.py,tests/test_course_authoring_revision_api.py,tests/test_course_generation_api.py,tests/test_curriculum_planning_api.py | BLOCKED | BLOCKED_BY_MODEL |
| GET | /api/v1/course-authoring/requests/{request_id}/generation | COURSE_AUTHORING | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES,WORKER | tests/test_course_authoring_api.py,tests/test_course_authoring_revision_api.py,tests/test_course_generation_api.py,tests/test_curriculum_planning_api.py | BLOCKED | BLOCKED_BY_DEPENDENCY |
| POST | /api/v1/course-authoring/requests/{request_id}/generation/retry | COURSE_AUTHORING | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | MODEL_PROVIDER,POSTGRES,WORKER | tests/test_course_authoring_api.py,tests/test_course_authoring_revision_api.py,tests/test_course_generation_api.py,tests/test_curriculum_planning_api.py | BLOCKED | BLOCKED_BY_MODEL |
| GET | /api/v1/course-authoring/requests/{request_id}/plan | COURSE_AUTHORING | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | MODEL_PROVIDER,POSTGRES | tests/test_course_authoring_api.py,tests/test_course_authoring_revision_api.py,tests/test_course_generation_api.py,tests/test_curriculum_planning_api.py | BLOCKED | BLOCKED_BY_MODEL |
| POST | /api/v1/course-authoring/requests/{request_id}/plan | COURSE_AUTHORING | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | MODEL_PROVIDER,POSTGRES | tests/test_course_authoring_api.py,tests/test_course_authoring_revision_api.py,tests/test_course_generation_api.py,tests/test_curriculum_planning_api.py | BLOCKED | BLOCKED_BY_MODEL |
| GET | /api/v1/course-authoring/requests/{request_id}/results | COURSE_AUTHORING | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_course_authoring_api.py,tests/test_course_authoring_revision_api.py,tests/test_course_generation_api.py,tests/test_curriculum_planning_api.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /api/v1/course-authoring/requests/{request_id}/revisions | COURSE_AUTHORING | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_course_authoring_api.py,tests/test_course_authoring_revision_api.py,tests/test_course_generation_api.py,tests/test_curriculum_planning_api.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/course-authoring/requests/{request_id}/revisions | COURSE_AUTHORING | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_course_authoring_api.py,tests/test_course_authoring_revision_api.py,tests/test_course_generation_api.py,tests/test_curriculum_planning_api.py | PASS | VERIFIED |
| POST | /api/v1/course-authoring/requests/{request_id}/revisions/{revision_id}/confirm | COURSE_AUTHORING | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_course_authoring_api.py,tests/test_course_authoring_revision_api.py,tests/test_course_generation_api.py,tests/test_curriculum_planning_api.py | PASS | VERIFIED |
| GET | /api/v1/course-authoring/results/{result_id} | COURSE_AUTHORING | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_course_authoring_api.py,tests/test_course_authoring_revision_api.py,tests/test_course_generation_api.py,tests/test_curriculum_planning_api.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/course-authoring/results/{result_id}/approve | COURSE_AUTHORING | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_course_authoring_api.py,tests/test_course_authoring_revision_api.py,tests/test_course_generation_api.py,tests/test_curriculum_planning_api.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/course-authoring/results/{result_id}/ready-for-materialization | COURSE_AUTHORING | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_course_authoring_api.py,tests/test_course_authoring_revision_api.py,tests/test_course_generation_api.py,tests/test_curriculum_planning_api.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/course-authoring/results/{result_id}/reject | COURSE_AUTHORING | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_course_authoring_api.py,tests/test_course_authoring_revision_api.py,tests/test_course_generation_api.py,tests/test_curriculum_planning_api.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/course-authoring/results/{result_id}/revisions | COURSE_AUTHORING | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_course_authoring_api.py,tests/test_course_authoring_revision_api.py,tests/test_course_generation_api.py,tests/test_curriculum_planning_api.py | PASS | VERIFIED |
| GET | /api/v1/integration/candidates/{candidate_id}/capability-analyses | CAPABILITY_ANALYSIS | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_capability_gap_integration_api.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/integration/candidates/{candidate_id}/capability-analyses | CAPABILITY_ANALYSIS | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_capability_gap_integration_api.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/integration/candidates/{candidate_id}/learning-paths | LEARNING_PATH | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | MODEL_PROVIDER,POSTGRES | tests/test_learning_path_integration.py | BLOCKED | BLOCKED_BY_MODEL |
| GET | /api/v1/integration/candidates/{candidate_id}/lms-user-link | INTEGRATION_AUTH | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_candidate_identity_bridge.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/integration/candidates/{candidate_id}/lms-user-link | INTEGRATION_AUTH | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_candidate_identity_bridge.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/integration/candidates/{candidate_id}/roles/{role_id}/capability-analyses | CAPABILITY_ANALYSIS | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_capability_gap_integration_api.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /api/v1/integration/capability-analyses/{analysis_id} | CAPABILITY_ANALYSIS | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_capability_gap_integration_api.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /api/v1/integration/capability-analyses/{analysis_id}/candidate-evidence | CAPABILITY_ANALYSIS | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_capability_gap_integration_api.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /api/v1/integration/capability-analyses/{analysis_id}/gaps/{gap_id}/evidence | CAPABILITY_ANALYSIS | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_capability_gap_integration_api.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /api/v1/integration/capability-analyses/{analysis_id}/learning-decision | CAPABILITY_ANALYSIS | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_capability_gap_integration_api.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/integration/capability-analyses/{analysis_id}/reanalyse-with-evidence | CAPABILITY_ANALYSIS | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_capability_gap_integration_api.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /api/v1/integration/competency-results/{result_id} | INTEGRATION_AUTH | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_integration_api.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /api/v1/integration/course-blueprints/{blueprint_id} | INTEGRATION_AUTH | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_integration_api.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /api/v1/integration/learning-paths/{learning_path_id} | LEARNING_PATH | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_learning_path_integration.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /api/v1/integration/learning-results | INTEGRATION_AUTH | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_integration_api.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /api/v1/integration/roles/{role_id}/capability-analyses | CAPABILITY_ANALYSIS | INTEGRATION_API_KEY + SIGNED_ACTOR_CONTEXT | POSTGRES | tests/test_capability_gap_integration_api.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /assessment-decisions | ASSESSMENT | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_assessment_competency_api.py,tests/test_assessment_repository.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /assessment-decisions/{record_id}/mark-assessed | COURSE_CAPABILITY | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_assessment_competency_api.py,tests/test_competency_repository.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /assessment-decisions/{record_id}/request-verification | COURSE_CAPABILITY | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_assessment_competency_api.py,tests/test_competency_repository.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /assessment-decisions/{record_id}/return-for-review | COURSE_CAPABILITY | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_assessment_competency_api.py,tests/test_competency_repository.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /assessment-decisions/{record_id}/verify | COURSE_CAPABILITY | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_assessment_competency_api.py,tests/test_competency_repository.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /assessment-submissions | ASSESSMENT | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_assessment_competency_api.py,tests/test_assessment_repository.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /assessment-submissions/{submission_id} | ASSESSMENT | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_assessment_competency_api.py,tests/test_assessment_repository.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /assessment-templates | ASSESSMENT | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_assessment_competency_api.py,tests/test_assessment_repository.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /assessment-templates/{template_id} | ASSESSMENT | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_assessment_competency_api.py,tests/test_assessment_repository.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /capability-gap-portfolios | CAPABILITY_ANALYSIS | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_capability_analysis_api.py,tests/test_capability_analysis_service.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /capability-gap-portfolios/{portfolio_id} | CAPABILITY_ANALYSIS | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_capability_analysis_api.py,tests/test_capability_analysis_service.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /competencies/{record_id}/mark-assessed | COURSE_CAPABILITY | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_assessment_competency_api.py,tests/test_competency_repository.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /competencies/{record_id}/require-reassessment | COURSE_CAPABILITY | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_assessment_competency_api.py,tests/test_competency_repository.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /competencies/{record_id}/revoke-verification | COURSE_CAPABILITY | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_assessment_competency_api.py,tests/test_competency_repository.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /competencies/{record_id}/verify | COURSE_CAPABILITY | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_assessment_competency_api.py,tests/test_competency_repository.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /credential-requests | ADMIN_INTERNAL | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_credential_api.py,tests/test_credential_authorization.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /credential-requests/{request_id} | ADMIN_INTERNAL | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_credential_api.py,tests/test_credential_authorization.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /credential-requests/{request_id}/approve | ADMIN_INTERNAL | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_credential_api.py,tests/test_credential_authorization.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /credential-requests/{request_id}/issue | ADMIN_INTERNAL | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_credential_api.py,tests/test_credential_authorization.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /credential-requests/{request_id}/reject | ADMIN_INTERNAL | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_credential_api.py,tests/test_credential_authorization.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /credentials/{credential_id}/expire | ADMIN_INTERNAL | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_credential_api.py,tests/test_credential_authorization.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /credentials/{credential_id}/revoke | ADMIN_INTERNAL | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_credential_api.py,tests/test_credential_authorization.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /credentials/{credential_id}/verify | ADMIN_INTERNAL | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_credential_api.py,tests/test_credential_authorization.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /delegations | ADMIN_INTERNAL | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_delegation_repository.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /delegations/{delegation_id} | ADMIN_INTERNAL | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_delegation_repository.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /delegations/{delegation_id}/{target} | ADMIN_INTERNAL | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_delegation_repository.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /documents | CV_DOCUMENT | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | CLAMAV,MINIO,POSTGRES | tests/test_document_api.py,tests/test_documents.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /extraction-jobs | CV_EXTRACTION | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | CLAMAV,MINIO,POSTGRES | tests/test_extraction_api.py,tests/test_extraction_router.py,tests/test_extraction_worker.py | BLOCKED | BLOCKED_BY_DEPENDENCY |
| DELETE | /extraction-jobs/{job_id} | CV_EXTRACTION | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_extraction_api.py,tests/test_extraction_router.py,tests/test_extraction_worker.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /extraction-jobs/{job_id} | CV_EXTRACTION | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_extraction_api.py,tests/test_extraction_router.py,tests/test_extraction_worker.py | NOT_RUN | NOT_YET_VERIFIED |
| DELETE | /extraction-profiles/{profile_id} | CV_EXTRACTION | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_extraction_api.py,tests/test_extraction_router.py,tests/test_extraction_worker.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /extraction-profiles/{profile_id} | CV_EXTRACTION | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_extraction_api.py,tests/test_extraction_router.py,tests/test_extraction_worker.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /extraction-profiles/{profile_id}/accept | CV_EXTRACTION | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | CLAMAV,MINIO,POSTGRES | tests/test_extraction_api.py,tests/test_extraction_router.py,tests/test_extraction_worker.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /extraction-profiles/{profile_id}/corrections | CV_EXTRACTION | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | CLAMAV,MINIO,POSTGRES | tests/test_extraction_api.py,tests/test_extraction_router.py,tests/test_extraction_worker.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /extraction-profiles/{profile_id}/reject | CV_EXTRACTION | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | CLAMAV,MINIO,POSTGRES | tests/test_extraction_api.py,tests/test_extraction_router.py,tests/test_extraction_worker.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /extraction-profiles/{profile_id}/request-revision | CV_EXTRACTION | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | CLAMAV,MINIO,POSTGRES | tests/test_extraction_api.py,tests/test_extraction_router.py,tests/test_extraction_worker.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /extraction-profiles/{profile_id}/review | CV_EXTRACTION | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_extraction_api.py,tests/test_extraction_router.py,tests/test_extraction_worker.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /extraction-profiles/{profile_id}/review-corrections | CV_EXTRACTION | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | CLAMAV,MINIO,POSTGRES | tests/test_extraction_api.py,tests/test_extraction_router.py,tests/test_extraction_worker.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /health | HEALTH | NONE | POSTGRES | tests/test_health.py | PASS | VERIFIED |
| GET | /health/live | HEALTH | NONE | POSTGRES | tests/test_health.py | PASS | VERIFIED |
| GET | /health/ready | HEALTH | NONE | POSTGRES | tests/test_health.py | PASS | VERIFIED |
| GET | /jd-extraction-profiles | CV_EXTRACTION | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_extraction_api.py,tests/test_extraction_router.py,tests/test_extraction_worker.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /learning-paths | LEARNING_PATH | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | MODEL_PROVIDER,POSTGRES | tests/test_learning_api.py,tests/test_learning_path_integration.py | BLOCKED | BLOCKED_BY_MODEL |
| GET | /learning-paths/{path_id} | LEARNING_PATH | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_learning_api.py,tests/test_learning_path_integration.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /learning-paths/{path_id}/approve | LEARNING_PATH | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | MODEL_PROVIDER,POSTGRES | tests/test_learning_api.py,tests/test_learning_path_integration.py | BLOCKED | BLOCKED_BY_MODEL |
| POST | /learning-paths/{path_id}/regenerate | LEARNING_PATH | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | MODEL_PROVIDER,POSTGRES | tests/test_learning_api.py,tests/test_learning_path_integration.py | BLOCKED | BLOCKED_BY_MODEL |
| POST | /learning-paths/{path_id}/review | LEARNING_PATH | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | MODEL_PROVIDER,POSTGRES | tests/test_learning_api.py,tests/test_learning_path_integration.py | BLOCKED | BLOCKED_BY_MODEL |
| POST | /learning-paths/{path_id}/supersede | LEARNING_PATH | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | MODEL_PROVIDER,POSTGRES | tests/test_learning_api.py,tests/test_learning_path_integration.py | BLOCKED | BLOCKED_BY_MODEL |
| POST | /preliminary-matches | INTERNAL_RECOMMENDATION | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_matching_api.py,tests/test_matching_review.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /preliminary-matches/{match_id} | INTERNAL_RECOMMENDATION | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_matching_api.py,tests/test_matching_review.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /preliminary-matches/{match_id}/review | INTERNAL_RECOMMENDATION | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_matching_api.py,tests/test_matching_review.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /role-profile-drafts | ROLE_PROFILE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_role_profile_authoring_api.py,tests/test_role_profile_authoring_quality_gate.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /role-profile-drafts | ROLE_PROFILE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_role_profile_authoring_api.py,tests/test_role_profile_authoring_quality_gate.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /role-profile-drafts/{draft_id} | ROLE_PROFILE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_role_profile_authoring_api.py,tests/test_role_profile_authoring_quality_gate.py | NOT_RUN | NOT_YET_VERIFIED |
| PATCH | /role-profile-drafts/{draft_id} | ROLE_PROFILE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_role_profile_authoring_api.py,tests/test_role_profile_authoring_quality_gate.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /role-profile-drafts/{draft_id}/approve | ROLE_PROFILE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_role_profile_authoring_api.py,tests/test_role_profile_authoring_quality_gate.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /role-profile-drafts/{draft_id}/validate | ROLE_PROFILE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_role_profile_authoring_api.py,tests/test_role_profile_authoring_quality_gate.py | NOT_RUN | NOT_YET_VERIFIED |
| PUT | /role-profiles/{role_profile_id}/semantic-policy | ROLE_GOVERNANCE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_semantic_policy_api.py,tests/test_semantic_policy_governance.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /roles | ROLE_GOVERNANCE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_role_registry.py,tests/test_role_profile_governance.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /roles | ROLE_GOVERNANCE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_role_registry.py,tests/test_role_profile_governance.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /roles/{role_id} | ROLE_GOVERNANCE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_role_registry.py,tests/test_role_profile_governance.py | NOT_RUN | NOT_YET_VERIFIED |
| PATCH | /roles/{role_id} | ROLE_GOVERNANCE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_role_registry.py,tests/test_role_profile_governance.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /roles/{role_id}/competency-profiles | ROLE_GOVERNANCE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_role_registry.py,tests/test_role_profile_governance.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /roles/{role_id}/competency-profiles/active | ROLE_GOVERNANCE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_role_registry.py,tests/test_role_profile_governance.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /roles/{role_id}/competency-profiles/{profile_id}/activate | ROLE_GOVERNANCE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_role_registry.py,tests/test_role_profile_governance.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /roles/{role_id}/jd/versions | ROLE_GOVERNANCE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_role_registry.py,tests/test_role_profile_governance.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /roles/{role_id}/jd/versions | ROLE_GOVERNANCE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_role_registry.py,tests/test_role_profile_governance.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /semantic-policies | ROLE_GOVERNANCE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_semantic_policy_api.py,tests/test_semantic_policy_governance.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /semantic-policies/{policy_id}/versions/{version} | ROLE_GOVERNANCE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_semantic_policy_api.py,tests/test_semantic_policy_governance.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /semantic-policies/{policy_id}/versions/{version}/activate | ROLE_GOVERNANCE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_semantic_policy_api.py,tests/test_semantic_policy_governance.py | NOT_RUN | NOT_YET_VERIFIED |
| POST | /semantic-policies/{policy_id}/versions/{version}/deprecate | ROLE_GOVERNANCE | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_semantic_policy_api.py,tests/test_semantic_policy_governance.py | NOT_RUN | NOT_YET_VERIFIED |
| GET | /users/{user_id}/delegations | ADMIN_INTERNAL | DEVELOPMENT_ACTOR_HEADER (local); signed context for integration | POSTGRES | tests/test_delegation_repository.py | NOT_RUN | NOT_YET_VERIFIED |

## 5. TEST GROUP 01 — Health/Auth

- Health `/health`, `/health/live`, `/health/ready`: live `200`.
- Integration auth negative: missing API key returned `401 integration_authentication_failed`.
- Local product auth negative: missing development actor returned `403 development_identity_required`.
- Signed authenticated bridge and deterministic authoring baseline were already externally verified; no secrets printed.
- Status: **VERIFIED** for health/auth boundary.

## 6. TEST GROUP 02 — Course Authoring

- Deterministic create/list/get/revisions/create revision/clarify/confirm paths: baseline and LMS UAT PASS.
- Conversation, planning, curriculum planning, generation and generation retry are registered but model/worker blocked or not yet verified.
- Stale revision, unresolved clarification, idempotency and reload behavior are covered by the existing baseline evidence.
- Status: deterministic subset **VERIFIED**; model-backed subset **BLOCKED_BY_MODEL**.

## 7. TEST GROUP 03 — CV/Candidate

- Candidate and document/extraction routes exist; API/domain tests exist.
- MinIO and ClamAV are healthy, but extraction worker is not running and model config is placeholder.
- No personal/private CV was uploaded.
- Status: CV/extraction **BLOCKED_BY_DEPENDENCY**; candidate profile **NOT_YET_VERIFIED**.

## 8. TEST GROUP 04 — JD/Role

- JD extraction projections, role profile drafts, role registry, validation and activation routes are exposed.
- Focused API/governance tests exist; no authenticated synthetic end-to-end JD flow was run in this bounded pass.
- Status: **NOT_YET_VERIFIED**.

## 9. TEST GROUP 05 — Capability Analysis

- Candidate/role analysis, projections, evidence and reanalysis routes are exposed.
- Existing integration API suite has 11 failures because fixtures send legacy actor/API auth while the route requires signed actor context; this is recorded as `PAI-AI-API-UAT-01-D01`.
- Status: **CONTRACT_DEFECT** pending fixture/contract reconciliation.

## 10. TEST GROUP 06 — Learning Need

- HTTP read projections exist for learning needs/objectives/blueprints.
- No safe authenticated persisted learning-need smoke was run.
- Status: **NOT_YET_VERIFIED**.

## 11. TEST GROUP 07 — Instructional Design

- No instructional-design creation/execution HTTP router is registered; internal modules and tests exist.
- Status: **NOT_EXPOSED** as an HTTP product API.

## 12. TEST GROUP 08 — Curriculum Planning

- Course-authoring plan/curriculum routes are exposed.
- Planner is model-backed; provider/model is not configured for live execution.
- Status: **BLOCKED_BY_MODEL**.

## 13. TEST GROUP 09 — Course Capability / Internal Recommendation

- Competency and preliminary matching APIs are exposed; no standalone CourseCapabilityProfile API was found.
- Status: **NOT_YET_VERIFIED**.

## 14. TEST GROUP 10 — External Recommendation

- No external provider recommendation adapter/API was registered.
- Status: **NOT_EXPOSED**.

## 15. TEST GROUP 11 — Learning Path

- Core learning-path CRUD/review/approve/regenerate and integration projection routes are exposed.
- Model-backed create/regenerate and persisted prerequisites were not live-smoked.
- Status: **NOT_YET_VERIFIED**; model-backed operations remain dependency-blocked.

## 16. TEST GROUP 12 — Content / Legacy

| Endpoint group | Classification | Reason |
| --- | --- |
| `/api/v1/content-generation/*` | DEFERRED | Registered legacy/deferred model-backed path; no live call; 4 tests fail before request due stale `authentication_method="test"` fixture (`D02`). |
| `/api/v1/course-authoring/*generation*` | BLOCKED_BY_MODEL / BLOCKED_BY_DEPENDENCY | Model placeholder and absent generation worker. |

## 17. Dependency Matrix

| Dependency | Current evidence | Affected groups |
| --- | --- | --- |
| Postgres | running/used by PAI | all persisted domains |
| Redis | running | queues/idempotency where used |
| MinIO | healthy `200` | documents/CV/JD transport |
| ClamAV | TCP ready | document safety scan |
| Worker | absent | extraction and generation async paths |
| Model | placeholder/no service | conversation, planning, curriculum, generation |
| External provider | not configured | external recommendation |

## 18. Automated Test Coverage

- Focused run: `110 passed, 15 failed`.
- Relevant API test files are recorded in `automated-test-coverage.json` and per-endpoint rows.
- The 15 failures are isolated to two known fixture/auth drift clusters; no code fix was made.

## 19. State Transition / Governance Tests

- Verified live: auth rejection, domain-specific not-found behavior, existing deterministic course-authoring lifecycle baseline.
- Not run in this bounded pass: capability provisional/active transitions, JD approval activation, extraction immutability, cross-actor/org persisted access.

## 20. Live Verified Capabilities

- Health/readiness and dependency health.
- Integration authentication boundary negative cases.
- Deterministic course-authoring brief flow via existing authenticated LMS bridge baseline.
- Safe development reads for role registry/role drafts and domain-specific not-found guards.

## 21. Not Yet Verified

- Candidate profile persisted flow.
- JD/role end-to-end extraction/approval.
- Capability analysis authenticated signed-context flow.
- Learning-need projection with real gap.
- Internal matching/recommendation.
- Learning path persisted flow.

## 22. Blocked Capabilities

### Storage

- None currently: MinIO and ClamAV are healthy.

### Model

- Conversation, curriculum planning, generation, and model-backed learning-path operations.

### Worker

- Extraction and course-generation async operations.

### Data

- Broader flows need bounded synthetic persisted candidate/JD/role records with signed actor context.

### External dependency

- External recommendation has no configured provider/API.

## 23. Defects Found

| ID | Scope | Type | Severity | Expected | Actual | Status |
| --- | --- | --- | --- | --- | --- | --- |
| PAI-AI-API-UAT-01-D01 | capability-gap integration tests | CONTRACT_DEFECT | medium | signed integration fixture reaches route | legacy header fixture receives 401 | OPEN |
| PAI-AI-API-UAT-01-D02 | content-generation API tests | CONTRACT_DEFECT | medium | test actor fixture accepted | `authentication_method="test"` rejected by current schema | OPEN |

## 24. Security

- No secret, private signing key or raw Authorization header was printed or persisted.
- No personal/private CV was used.
- Artifact scan is clean for secret values.
- Auth negative probes returned safe error codes without secret disclosure.

## 25. Evidence Artifacts

- `test/results/pai-ai-api-uat-01/api-inventory.json`
- `test/results/pai-ai-api-uat-01/route-registration-crosscheck.json`
- `test/results/pai-ai-api-uat-01/api-capability-matrix.json`
- `test/results/pai-ai-api-uat-01/dependency-matrix.json`
- `test/results/pai-ai-api-uat-01/automated-test-coverage.json`
- `test/results/pai-ai-api-uat-01/live-smoke-results.json`
- `test/results/pai-ai-api-uat-01/state-transition-results.json`
- `test/results/pai-ai-api-uat-01/blockers.json`
- `test/results/pai-ai-api-uat-01/summary.json`
- `docs/research/PAI-AI-API-UAT-01.md`

## 26. API Readiness Matrix

- `VERIFIED`: health/auth boundary; deterministic course authoring baseline.
- `NOT_YET_VERIFIED`: candidate, JD/role, capability analysis pending auth fixture reconciliation, learning need, matching, learning path.
- `BLOCKED_BY_MODEL`: model-backed planning/generation.
- `BLOCKED_BY_DEPENDENCY`: extraction/generation worker paths.
- `NOT_EXPOSED`: instructional-design HTTP API and external recommendation API.
- `DEFERRED`: legacy content-generation API.
- `CONTRACT_DEFECT`: two test/auth fixture clusters above.

## 27. Frappe Integration Readiness

| Capability | Core-AI ready? | Contract stable? | Safe to integrate? | Reason |
| --- | --- | --- | --- | --- |
| Deterministic course authoring | YES | YES for confirmed brief boundary | YES | Existing signed bridge and UAT pass. |
| Capability analysis | NO | NO | NO | Auth fixture/contract defect and no live signed-context smoke. |
| Learning need | NO | NOT_YET_VERIFIED | NO | No persisted live evidence. |
| Curriculum planning | NO | NOT_YET_VERIFIED | NO | Model provider unavailable. |
| Recommendation | NO | NOT_YET_VERIFIED | NO | No live catalog/recommendation evidence. |
| Learning path | NO | NOT_YET_VERIFIED | NO | No persisted live evidence; model-backed operations unverified. |

## 28. Next Decision

- Conversational Brief: **NOT READY** (model-backed endpoint blocked).
- Curriculum Planning: **NOT READY** (model provider unavailable).
- Capability Analysis: **NOT READY** (contract/auth fixture defect unresolved).
- Recommendation: **NOT READY** (not live verified).
- Learning Path: **NOT READY** (not live verified).

## 29. Git Status

- Core-AI: source `.git` metadata is unavailable in the original local checkout; evidence was generated without commit/push. Recovered verification clone remains at `/private/tmp/core-ai-push-recovery-20261001`.
- LMS: **UNCHANGED by this milestone**.
- Product code: no changes made for this milestone; only evidence artifacts were generated under the Core-AI checkout.
