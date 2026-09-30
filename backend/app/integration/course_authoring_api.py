from typing import cast

from fastapi import APIRouter, Depends, Header, Request, status

from app.authorization.schemas import ActorContext
from app.course_authoring.errors import (
    CourseAuthoringAccessDeniedError,
    CourseAuthoringReferenceNotFoundError,
    CourseAuthoringReferenceValidationError,
    CourseAuthoringRequestNotFoundError,
)
from app.course_authoring.revision_errors import (
    CourseRevisionAccessDeniedError,
    CourseRevisionConflictError,
    CourseRevisionNotFoundError,
    CourseRevisionValidationError,
)
from app.course_authoring.revision_service import CourseDraftRevisionService
from app.course_authoring.schemas import CourseAuthoringRequest
from app.course_authoring.service import CourseAuthoringService
from app.course_generation.errors import (
    CourseGenerationAlreadyInProgressError,
    CourseGenerationArtifactNotFoundError,
    CourseGenerationOutputInvalidError,
    CourseGenerationProviderError,
)
from app.course_generation.hierarchical_service import HierarchicalCourseGenerationService
from app.course_generation.service import CourseGenerationService
from app.curriculum_planning.revision_service import CurriculumRevisionService
from app.curriculum_planning.schemas import CurriculumPlan
from app.curriculum_planning.service import CurriculumPlanningService
from app.curriculum_planning.validation import CurriculumPlanValidationError
from app.integration.actor_context import get_signed_actor_context
from app.integration.auth import verify_integration_api_key
from app.integration.content_generation_schemas import ContentGenerationResultV1
from app.integration.course_authoring_schemas import (
    AuthoringBriefRevisionEnvelopeV1,
    AuthoringBriefRevisionListEnvelopeV1,
    AuthoringBriefRevisionV1,
    AuthoringConversationRespondV1,
    AuthoringConversationResponseV1,
    BriefRevisionChangesV1,
    ContentReviewRejectEnvelopeV1,
    CourseAuthoringAcceptedEnvelopeV1,
    CourseAuthoringCreateEnvelopeV1,
    CourseAuthoringRequestAcceptedV1,
    CourseAuthoringRequestEnvelopeV1,
    CourseAuthoringRequestListEnvelopeV1,
    CourseAuthoringRequestV1,
    CourseAuthoringResultVersionListV1,
    CourseAuthoringResultVersionV1,
    CourseDraftRevisionEnvelopeV1,
    CourseGenerationAcceptedEnvelopeV1,
    CourseGenerationAcceptedV1,
    CourseGenerationProgressV1,
    CurriculumPlanEnvelopeV1,
    CurriculumPlanListEnvelopeV1,
    CurriculumPlanRevisionRequestV1,
    CurriculumPlanV1,
)
from app.integration.schemas import IntegrationEnvelopeV1
from app.shared.errors import APIError

router = APIRouter(
    prefix="/api/v1/course-authoring",
    tags=["course-authoring"],
    dependencies=[Depends(verify_integration_api_key)],
)


def _service(request: Request) -> CourseAuthoringService:
    service = getattr(request.app.state, "course_authoring_service", None)
    if service is None:
        raise APIError(503, "course_authoring_unavailable", "Course authoring is not ready.")
    return cast(CourseAuthoringService, service)


def _error(exc: Exception) -> APIError:
    if isinstance(exc, ValueError):
        codes = {
            "authoring_brief_not_confirmed": (
                409,
                "The authoring brief must be confirmed before planning.",
            ),
            "revision_not_found": (404, "The authoring brief revision was not found."),
            "revision_not_latest": (
                409,
                "Only the latest authoring brief revision may be confirmed.",
            ),
            "revision_request_mismatch": (422, "The revision does not belong to this request."),
            "required_clarification_unresolved": (409, "Required clarification is unresolved."),
            "revision_not_ready_for_confirmation": (
                409,
                "The revision is not ready for confirmation.",
            ),
            "authoring_revision_access_denied": (403, "Authoring brief access is denied."),
            "authoring_revision_not_required": (
                409,
                "This request does not use the revision workflow.",
            ),
            "authoring_revision_not_found": (404, "The authoring brief revision was not found."),
            "authoring_conversation_not_required": (
                409,
                "Conversational authoring is not enabled for this request.",
            ),
            "course_authoring_idempotency_conflict": (
                409,
                "An authoring request already exists for this idempotency key with different data.",
            ),
            "conversation_response_invalid": (502, "AI assistance returned an invalid response."),
            "curriculum_plan_not_latest": (
                409,
                "Only the latest curriculum plan may be changed or confirmed.",
            ),
            "curriculum_review_not_required": (
                409,
                "This curriculum plan uses the historical compatibility workflow.",
            ),
            "curriculum_review_blocking_findings": (
                409,
                "The curriculum plan is not ready for confirmation.",
            ),
            "curriculum_revision_invalid": (
                422,
                "The proposed curriculum revision failed validation.",
            ),
            "SCOPE_EXPANSION_REQUIRES_BRIEF_REVISION": (
                409,
                "This change expands the confirmed training scope and requires a brief revision.",
            ),
            "curriculum_revision_operation_not_supported": (
                422,
                "The proposed curriculum operation is not supported.",
            ),
        }
        if str(exc) in codes:
            status_code, message = codes[str(exc)]
            return APIError(status_code, str(exc), message)
    if isinstance(exc, CourseAuthoringRequestNotFoundError):
        return APIError(
            404, "course_authoring_request_not_found", "Course authoring request was not found."
        )
    if isinstance(exc, CourseAuthoringReferenceNotFoundError):
        return APIError(
            404, "course_authoring_reference_not_found", "Course authoring reference was not found."
        )
    if isinstance(exc, CourseAuthoringReferenceValidationError):
        return APIError(
            409, "course_authoring_reference_invalid", "Course authoring references are invalid."
        )
    if isinstance(exc, CourseAuthoringAccessDeniedError):
        return APIError(403, "course_authoring_access_denied", "Course authoring access is denied.")
    if isinstance(exc, CourseGenerationArtifactNotFoundError):
        if str(exc) == "curriculum_plan_not_found":
            return APIError(404, "curriculum_plan_not_found", "A curriculum plan was not found.")
        if str(exc) == "curriculum_plan_not_confirmed":
            return APIError(
                409,
                "curriculum_plan_not_confirmed",
                "The latest curriculum plan must be confirmed before generation.",
            )
        return APIError(
            404,
            "course_generation_artifact_not_found",
            "A required generation artifact was not found.",
        )
    if isinstance(exc, CourseGenerationAlreadyInProgressError):
        return APIError(
            409,
            "course_generation_already_in_progress",
            "Course generation is already in progress.",
        )
    if isinstance(exc, CourseGenerationOutputInvalidError):
        return APIError(
            422, "course_generation_output_invalid", "The generated course draft failed validation."
        )
    if isinstance(exc, CourseGenerationProviderError):
        status_code = 504 if str(exc) in {"provider_timeout", "generation_timeout"} else 502
        return APIError(
            status_code,
            "course_generation_provider_failed",
            "The course-generation provider failed.",
        )
    if isinstance(exc, CurriculumPlanValidationError):
        safe_issues = [
            {
                "code": issue.code,
                "message": issue.message,
                "path": issue.path,
                "actual": issue.actual,
                "expected": issue.expected,
            }
            for issue in exc.report.issues
        ]
        return APIError(
            422,
            "curriculum_plan_invalid",
            "The curriculum plan failed validation.",
            details={"issues": safe_issues},
        )
    if isinstance(exc, CourseRevisionNotFoundError):
        return APIError(404, "course_revision_not_found", "The course draft version was not found.")
    if isinstance(exc, CourseRevisionAccessDeniedError):
        return APIError(403, "course_revision_access_denied", "Course draft access is denied.")
    if isinstance(exc, CourseRevisionConflictError):
        conflict_codes = {
            "only_latest_result_can_be_approved": "Only the latest content version can be approved.",
            "only_latest_result_can_be_rejected": "Only the latest content version can be rejected.",
            "rejected_result_cannot_be_approved": "Rejected content cannot be approved.",
            "approved_result_cannot_be_rejected": "Approved content cannot be rejected.",
            "result_not_approvable": "This content version is not available for approval.",
        }
        if str(exc) in conflict_codes:
            return APIError(409, str(exc), conflict_codes[str(exc)])
        return APIError(
            409,
            "course_revision_conflict",
            "The course draft version is stale or unavailable for this action.",
        )
    if isinstance(exc, CourseRevisionValidationError):
        return APIError(422, "course_revision_invalid", "The course draft revision is invalid.")
    return APIError(502, "course_authoring_integration_error", "Course authoring request failed.")


def _generation_service(
    request: Request,
) -> CourseGenerationService | HierarchicalCourseGenerationService:
    service = getattr(request.app.state, "course_generation_service", None)
    if service is None:
        raise APIError(503, "course_generation_unavailable", "Course generation is not ready.")
    return cast(CourseGenerationService | HierarchicalCourseGenerationService, service)


def _revision_service(request: Request) -> CourseDraftRevisionService:
    service = getattr(request.app.state, "course_draft_revision_service", None)
    if service is None:
        raise APIError(503, "course_revision_unavailable", "Course draft revision is not ready.")
    return cast(CourseDraftRevisionService, service)


def _planning_service(request: Request) -> CurriculumPlanningService:
    service = getattr(request.app.state, "curriculum_planning_service", None)
    if service is None:
        raise APIError(503, "curriculum_planning_unavailable", "Curriculum planning is not ready.")
    return cast(CurriculumPlanningService, service)


def _curriculum_revision_service(request: Request) -> CurriculumRevisionService:
    service = getattr(request.app.state, "curriculum_revision_service", None)
    if service is None:
        raise APIError(503, "curriculum_revision_unavailable", "Curriculum review is not ready.")
    return cast(CurriculumRevisionService, service)


async def _authorize_curriculum_plan(
    request: Request, plan_id: str, actor: ActorContext
) -> CurriculumPlan:
    plan = await _curriculum_revision_service(request).get(plan_id)
    await _service(request).get(plan.authoring_request_ref, actor)
    return plan


@router.post(
    "/requests",
    response_model=CourseAuthoringAcceptedEnvelopeV1,
    status_code=status.HTTP_201_CREATED,
)
async def create_course_authoring_request(
    body: CourseAuthoringCreateEnvelopeV1,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[CourseAuthoringRequestAcceptedV1]:
    if not idempotency_key:
        raise APIError(400, "idempotency_key_required", "Idempotency-Key is required.")
    if len(idempotency_key) > 128:
        raise APIError(422, "idempotency_key_invalid", "Idempotency-Key is invalid.")
    try:
        accepted = await _service(request).create(
            body.data.to_domain(), actor, idempotency_key=idempotency_key
        )
    except Exception as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(
        schema_version="v1",
        data=CourseAuthoringRequestAcceptedV1.from_domain(accepted),
    )


@router.get(
    "/requests",
    response_model=CourseAuthoringRequestListEnvelopeV1,
)
async def list_course_authoring_requests(
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[list[CourseAuthoringRequestV1]]:
    try:
        requests = await _service(request).list(actor)
    except Exception as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(
        schema_version="v1",
        data=[CourseAuthoringRequestV1.from_domain(item) for item in requests],
    )


@router.get(
    "/requests/{request_id}",
    response_model=CourseAuthoringRequestEnvelopeV1,
)
async def get_course_authoring_request(
    request_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[CourseAuthoringRequestV1]:
    try:
        course_request: CourseAuthoringRequest = await _service(request).get(request_id, actor)
    except Exception as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(
        schema_version="v1",
        data=CourseAuthoringRequestV1.from_domain(course_request),
    )


@router.get(
    "/requests/{request_id}/revisions",
    response_model=AuthoringBriefRevisionListEnvelopeV1,
)
async def list_authoring_brief_revisions(
    request_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[list[AuthoringBriefRevisionV1]]:
    try:
        revisions = await _service(request).list_brief_revisions(request_id, actor)
    except Exception as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(
        schema_version="v1",
        data=[AuthoringBriefRevisionV1.from_domain(item) for item in revisions],
    )


@router.post(
    "/requests/{request_id}/conversation/respond",
    response_model=IntegrationEnvelopeV1[AuthoringConversationResponseV1],
)
async def respond_to_authoring_conversation(
    request_id: str,
    body: IntegrationEnvelopeV1[AuthoringConversationRespondV1],
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[AuthoringConversationResponseV1]:
    try:
        response = await _service(request).conversation_respond(
            request_id, body.data.user_message, actor
        )
    except Exception as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(
        schema_version="v1",
        data=AuthoringConversationResponseV1.from_domain(response),
    )


@router.post(
    "/requests/{request_id}/clarify",
    response_model=AuthoringBriefRevisionEnvelopeV1,
)
async def clarify_authoring_brief(
    request_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[AuthoringBriefRevisionV1]:
    try:
        revision = await _service(request).clarify_brief(request_id, actor)
    except Exception as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(
        schema_version="v1",
        data=AuthoringBriefRevisionV1.from_domain(revision),
    )


@router.post(
    "/requests/{request_id}/revisions",
    response_model=AuthoringBriefRevisionEnvelopeV1,
    status_code=status.HTTP_201_CREATED,
)
async def create_authoring_brief_revision(
    request_id: str,
    body: IntegrationEnvelopeV1[BriefRevisionChangesV1],
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[AuthoringBriefRevisionV1]:
    try:
        revision = await _service(request).create_brief_revision(
            request_id, body.data.to_domain(), actor
        )
    except Exception as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(
        schema_version="v1",
        data=AuthoringBriefRevisionV1.from_domain(revision),
    )


@router.post(
    "/requests/{request_id}/revisions/{revision_id}/confirm",
    response_model=AuthoringBriefRevisionEnvelopeV1,
)
async def confirm_authoring_brief_revision(
    request_id: str,
    revision_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[AuthoringBriefRevisionV1]:
    try:
        revision = await _service(request).confirm_brief(request_id, revision_id, actor)
    except Exception as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(
        schema_version="v1",
        data=AuthoringBriefRevisionV1.from_domain(revision),
    )


@router.post(
    "/requests/{request_id}/plan",
    response_model=CurriculumPlanEnvelopeV1,
    status_code=status.HTTP_201_CREATED,
)
async def plan_course_authoring_request(
    request_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[CurriculumPlanV1]:
    try:
        plan = await _planning_service(request).plan(request_id, actor)
    except Exception as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(
        schema_version="v1",
        data=CurriculumPlanV1.from_domain(plan),
    )


@router.get(
    "/requests/{request_id}/plan",
    response_model=CurriculumPlanEnvelopeV1,
)
async def get_course_authoring_plan(
    request_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[CurriculumPlanV1]:
    try:
        await _service(request).get(request_id, actor)
        plan = await _planning_service(request).get_latest(request_id)
    except Exception as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(
        schema_version="v1",
        data=CurriculumPlanV1.from_domain(plan),
    )


@router.get(
    "/requests/{request_id}/curriculum-plans",
    response_model=CurriculumPlanListEnvelopeV1,
)
async def list_curriculum_plans(
    request_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[list[CurriculumPlanV1]]:
    try:
        await _service(request).get(request_id, actor)
        plans = await _curriculum_revision_service(request).list_for_request(request_id)
    except Exception as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(
        schema_version="v1",
        data=[CurriculumPlanV1.from_domain(plan) for plan in plans],
    )


@router.post(
    "/curriculum-plans/{plan_id}/review",
    response_model=CurriculumPlanEnvelopeV1,
)
async def review_curriculum_plan(
    plan_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[CurriculumPlanV1]:
    try:
        await _authorize_curriculum_plan(request, plan_id, actor)
        plan = await _curriculum_revision_service(request).review(plan_id)
    except Exception as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(schema_version="v1", data=CurriculumPlanV1.from_domain(plan))


@router.post(
    "/curriculum-plans/{plan_id}/revisions",
    response_model=CurriculumPlanEnvelopeV1,
    status_code=status.HTTP_201_CREATED,
)
async def revise_curriculum_plan(
    plan_id: str,
    body: CurriculumPlanRevisionRequestV1,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[CurriculumPlanV1]:
    try:
        await _authorize_curriculum_plan(request, plan_id, actor)
        plan = await _curriculum_revision_service(request).revise(
            plan_id,
            [item.model_dump() for item in body.operations],
            body.rationale,
            actor,
        )
    except Exception as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(schema_version="v1", data=CurriculumPlanV1.from_domain(plan))


@router.post(
    "/curriculum-plans/{plan_id}/confirm",
    response_model=CurriculumPlanEnvelopeV1,
)
async def confirm_curriculum_plan(
    plan_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[CurriculumPlanV1]:
    try:
        await _authorize_curriculum_plan(request, plan_id, actor)
        plan = await _curriculum_revision_service(request).confirm(plan_id, actor)
    except Exception as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(schema_version="v1", data=CurriculumPlanV1.from_domain(plan))


@router.post(
    "/requests/{request_id}/generate",
    response_model=CourseGenerationAcceptedEnvelopeV1,
    status_code=status.HTTP_200_OK,
)
async def generate_course_authoring_request(
    request_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[CourseGenerationAcceptedV1 | CourseGenerationProgressV1]:
    try:
        service = _generation_service(request)
        accepted: CourseGenerationAcceptedV1 | CourseGenerationProgressV1
        if isinstance(service, HierarchicalCourseGenerationService):
            accepted = await service.start(request_id, actor)
        else:
            accepted = await service.generate(request_id, actor)
    except Exception as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(
        schema_version="v1",
        data=accepted,
    )


@router.get(
    "/requests/{request_id}/generation",
    response_model=IntegrationEnvelopeV1[CourseGenerationProgressV1],
)
async def get_course_generation_progress(
    request_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[CourseGenerationProgressV1]:
    service = _generation_service(request)
    if not isinstance(service, HierarchicalCourseGenerationService):
        raise APIError(
            503,
            "course_generation_progress_unavailable",
            "Course generation progress is not ready.",
        )
    try:
        progress = await service.get_latest_progress(request_id)
    except Exception as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(schema_version="v1", data=progress)


@router.post(
    "/requests/{request_id}/generation/retry",
    response_model=IntegrationEnvelopeV1[CourseGenerationProgressV1],
)
async def retry_course_generation(
    request_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[CourseGenerationProgressV1]:
    service = _generation_service(request)
    if not isinstance(service, HierarchicalCourseGenerationService):
        raise APIError(
            503, "course_generation_retry_unavailable", "Course generation retry is not ready."
        )
    try:
        progress = await service.get_latest_progress(request_id)
        progress = await service.retry_failed(progress.plan_ref, actor)
    except Exception as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(schema_version="v1", data=progress)


@router.post(
    "/results/{result_id}/revisions",
    response_model=IntegrationEnvelopeV1[ContentGenerationResultV1],
    status_code=status.HTTP_201_CREATED,
)
async def create_course_draft_revision(
    result_id: str,
    body: CourseDraftRevisionEnvelopeV1,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[ContentGenerationResultV1]:
    if body.data.source_result_ref != result_id:
        raise APIError(
            422, "course_revision_invalid", "Revision source does not match the route result."
        )
    try:
        result = await _revision_service(request).create_revision(body.data, actor)
    except Exception as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(schema_version="v1", data=result)


@router.get(
    "/requests/{request_id}/results",
    response_model=IntegrationEnvelopeV1[CourseAuthoringResultVersionListV1],
)
async def list_course_draft_versions(
    request_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[CourseAuthoringResultVersionListV1]:
    try:
        results = await _revision_service(request).list_versions(request_id, actor)
    except Exception as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(
        schema_version="v1",
        data=[CourseAuthoringResultVersionV1.from_domain(result) for result in results],
    )


@router.get(
    "/results/{result_id}",
    response_model=IntegrationEnvelopeV1[ContentGenerationResultV1],
)
async def get_course_draft_version(
    result_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[ContentGenerationResultV1]:
    try:
        result = await _revision_service(request).get_version(result_id, actor)
    except Exception as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(schema_version="v1", data=result)


@router.post(
    "/results/{result_id}/approve",
    response_model=IntegrationEnvelopeV1[ContentGenerationResultV1],
)
async def approve_course_draft(
    result_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[ContentGenerationResultV1]:
    try:
        result = await _revision_service(request).approve(result_id, actor)
    except Exception as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(schema_version="v1", data=result)


@router.post(
    "/results/{result_id}/reject",
    response_model=IntegrationEnvelopeV1[ContentGenerationResultV1],
)
async def reject_course_draft(
    result_id: str,
    body: ContentReviewRejectEnvelopeV1,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[ContentGenerationResultV1]:
    try:
        result = await _revision_service(request).reject(result_id, actor, reason=body.data.reason)
    except Exception as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(schema_version="v1", data=result)


@router.post(
    "/results/{result_id}/ready-for-materialization",
    response_model=IntegrationEnvelopeV1[ContentGenerationResultV1],
)
async def mark_course_draft_ready(
    result_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[ContentGenerationResultV1]:
    try:
        result = await _revision_service(request).mark_ready(result_id, actor)
    except Exception as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(schema_version="v1", data=result)
