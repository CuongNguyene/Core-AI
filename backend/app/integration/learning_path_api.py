from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status

from app.authorization.schemas import ActorContext
from app.integration.actor_context import get_signed_actor_context
from app.integration.auth import verify_integration_api_key
from app.integration.learning_path_schemas import LearningPathCreateV1, LearningPathProjectionV1
from app.integration.schemas import IntegrationEnvelopeV1
from app.learning.errors import (
    LearningPathNotFoundError,
    LearningPathValidationError,
)
from app.learning.schemas import LearningPath
from app.learning.service import LearningPathService
from app.shared.errors import APIError

router = APIRouter(
    prefix="/api/v1/integration",
    tags=["integration-learning-path"],
    dependencies=[Depends(verify_integration_api_key)],
)


def _service(request: Request) -> LearningPathService:
    service = getattr(request.app.state, "learning_path_service", None)
    if service is None:
        raise APIError(503, "learning_path_unavailable", "Learning path service is not ready.")
    return cast(LearningPathService, service)


def _projection(path: LearningPath) -> LearningPathProjectionV1:
    if path.source_type.value != "capability_analysis" or path.source_candidate_id is None or path.capability_analysis_id is None:
        raise APIError(502, "invalid_learning_path_source", "Learning path source is not projectable.")
    return LearningPathProjectionV1(
        learning_path_id=path.id,
        version=path.version,
        status=path.status.value,
        source_type="capability_analysis",
        candidate_reference=path.source_candidate_id,
        capability_analysis_reference=path.capability_analysis_id,
        target_reference=f"{path.source_target_id}@{path.source_target_version}",
        gap_references=list(path.source_gap_ids),
        evidence_references=list(path.source_evidence_refs),
        recommendation_references=[f"recommendation:{gap_id}" for gap_id in path.source_gap_ids[: len(path.source_recommendation_refs)]],
        ready_for_review=path.validation.ready_for_review,
        is_stale=path.is_stale,
    )


def _error(exc: Exception) -> APIError:
    code = str(exc)
    mapping = {
        "learning_path_idempotency_conflict": (409, "learning_path_idempotency_conflict", "Idempotency key conflicts with a previous request."),
        "capability_analysis_not_found": (404, "capability_analysis_not_found", "Capability analysis was not found."),
        "capability_analysis_access_denied": (403, "capability_analysis_access_denied", "Capability analysis access is denied."),
        "capability_analysis_target_not_active": (409, "capability_analysis_target_not_active", "Capability analysis target is not active."),
        "capability_analysis_target_level_required": (409, "learning_path_target_level_required", "Target profile requires reviewer-authored numeric target levels."),
        "no_actionable_capability_gaps": (409, "no_actionable_capability_gaps", "No actionable capability gaps are available."),
        "learning_path_not_found": (404, "learning_path_not_found", "Learning path was not found."),
    }
    status_code, public_code, message = mapping.get(
        code, (409, "learning_path_integration_error", "Learning path request was rejected.")
    )
    return APIError(status_code, public_code, message)


@router.post(
    "/candidates/{candidate_id}/learning-paths",
    response_model=IntegrationEnvelopeV1[LearningPathProjectionV1],
    status_code=status.HTTP_201_CREATED,
)
async def create_learning_path(
    candidate_id: UUID,
    body: IntegrationEnvelopeV1[LearningPathCreateV1],
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> IntegrationEnvelopeV1[LearningPathProjectionV1]:
    if not idempotency_key:
        raise APIError(400, "idempotency_key_required", "Idempotency-Key is required.")
    try:
        path = await _service(request).create_for_candidate(
            actor=actor,
            candidate_id=candidate_id,
            development_goal=body.data.development_goal,
            target_completion_date=body.data.target_completion_date,
            idempotency_key=idempotency_key,
        )
    except LearningPathValidationError as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(schema_version="v1", data=_projection(path))


@router.get(
    "/learning-paths/{learning_path_id}",
    response_model=IntegrationEnvelopeV1[LearningPathProjectionV1],
)
async def get_learning_path(
    learning_path_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[LearningPathProjectionV1]:
    try:
        path = await _service(request).get(learning_path_id, actor=actor)
    except LearningPathValidationError as exc:
        raise _error(exc) from exc
    except LearningPathNotFoundError as exc:
        raise _error(exc) from exc
    return IntegrationEnvelopeV1(schema_version="v1", data=_projection(path))
