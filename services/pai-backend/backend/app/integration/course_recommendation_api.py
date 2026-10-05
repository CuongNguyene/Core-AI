from typing import cast

from fastapi import APIRouter, Depends, Request, Response, status

from app.authorization.schemas import ActorContext
from app.course_recommendation.execution_schemas import RecommendationExecutionRecord
from app.course_recommendation.execution_service import (
    CourseRecommendationExecutionService,
    RecommendationExecutionAccessDeniedError,
    RecommendationExecutionNotFoundError,
)
from app.course_recommendation.execution_snapshots import RecommendationSnapshotInconsistent
from app.course_recommendation.repository import (
    RecommendationIdempotencyConflict,
    RecommendationPersistenceError,
)
from app.integration.actor_context import get_signed_actor_context
from app.integration.auth import verify_integration_api_key
from app.integration.course_recommendation_schemas import CourseRecommendationExecutionCreateV1
from app.integration.schemas import IntegrationEnvelopeV1
from app.shared.errors import APIError

router = APIRouter(
    prefix="/api/v1/course-recommendations",
    tags=["course-recommendations"],
    dependencies=[Depends(verify_integration_api_key)],
)


def _service(request: Request) -> CourseRecommendationExecutionService:
    service = getattr(request.app.state, "course_recommendation_execution_service", None)
    if service is None:
        raise APIError(
            503, "course_recommendation_unavailable", "Course recommendation is not ready."
        )
    return cast(CourseRecommendationExecutionService, service)


def _map_error(exc: Exception) -> APIError:
    if isinstance(exc, RecommendationSnapshotInconsistent):
        return APIError(
            422,
            "recommendation_snapshot_inconsistent",
            "Resolved recommendation inputs are inconsistent.",
        )
    if isinstance(exc, RecommendationIdempotencyConflict):
        return APIError(
            409,
            "recommendation_idempotency_conflict",
            "The request key conflicts with a different execution.",
        )
    if isinstance(exc, RecommendationExecutionNotFoundError):
        return APIError(404, "recommendation_not_found", "Recommendation execution was not found.")
    if isinstance(exc, RecommendationExecutionAccessDeniedError):
        return APIError(
            403, "recommendation_access_denied", "Recommendation execution access is denied."
        )
    if isinstance(exc, RecommendationPersistenceError):
        return APIError(
            503,
            "recommendation_persistence_unavailable",
            "Recommendation execution could not be persisted.",
        )
    return APIError(
        422, "recommendation_snapshot_inconsistent", "Resolved recommendation inputs were rejected."
    )


@router.post("", response_model=IntegrationEnvelopeV1[RecommendationExecutionRecord])
async def create_course_recommendation(
    body: IntegrationEnvelopeV1[CourseRecommendationExecutionCreateV1],
    request: Request,
    response: Response,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[RecommendationExecutionRecord]:
    payload = body.data
    try:
        result = await _service(request).execute(
            target_projection=payload.target_projection,
            course_projections=payload.course_projections,
            max_results=payload.max_results,
            request_key=payload.request_key,
            actor=actor,
        )
    except (
        RecommendationSnapshotInconsistent,
        RecommendationIdempotencyConflict,
        RecommendationPersistenceError,
    ) as exc:
        raise _map_error(exc) from exc
    response.status_code = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    return IntegrationEnvelopeV1(schema_version="v1", data=result.execution)


@router.get(
    "/{recommendation_id}", response_model=IntegrationEnvelopeV1[RecommendationExecutionRecord]
)
async def get_course_recommendation(
    recommendation_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[RecommendationExecutionRecord]:
    try:
        record = await _service(request).get(recommendation_id, actor)
    except (RecommendationExecutionNotFoundError, RecommendationExecutionAccessDeniedError) as exc:
        raise _map_error(exc) from exc
    return IntegrationEnvelopeV1(schema_version="v1", data=record)
