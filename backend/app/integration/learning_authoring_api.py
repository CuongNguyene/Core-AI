from typing import cast

from fastapi import APIRouter, Depends, Request

from app.authorization.schemas import ActorContext
from app.integration.actor_context import get_signed_actor_context
from app.integration.auth import verify_integration_api_key
from app.integration.learning_authoring_schemas import (
    InstructionalBlueprintProjectionV1,
    LearningNeedProjectionV1,
    LearningObjectiveProjectionV1,
)
from app.integration.schemas import IntegrationEnvelopeV1
from app.learning_authoring.service import (
    LearningAuthoringAccessDeniedError,
    LearningAuthoringNotFoundError,
    LearningAuthoringService,
)
from app.shared.errors import APIError

router = APIRouter(
    prefix="/api/v1/authoring",
    tags=["learning-authoring"],
    dependencies=[Depends(verify_integration_api_key)],
)


def _service(request: Request) -> LearningAuthoringService:
    service = getattr(request.app.state, "learning_authoring_service", None)
    if service is None:
        raise APIError(503, "learning_authoring_unavailable", "Learning authoring is not ready.")
    return cast(LearningAuthoringService, service)


def _error(exc: Exception, resource_code: str) -> APIError:
    if isinstance(exc, APIError):
        return exc
    if isinstance(exc, LearningAuthoringNotFoundError):
        return APIError(404, resource_code, "Learning authoring reference was not found.")
    if isinstance(exc, LearningAuthoringAccessDeniedError):
        return APIError(403, "learning_authoring_access_denied", "Learning authoring access is denied.")
    return APIError(502, "learning_authoring_projection_error", "Learning authoring projection failed.")


@router.get(
    "/learning-needs/{learning_need_id}",
    response_model=IntegrationEnvelopeV1[LearningNeedProjectionV1],
)
async def get_learning_need(
    learning_need_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[LearningNeedProjectionV1]:
    try:
        projection = await _service(request).get_learning_need(learning_need_id, actor)
    except Exception as exc:
        raise _error(exc, "learning_need_not_found") from exc
    return IntegrationEnvelopeV1(schema_version="v1", data=projection)


@router.get(
    "/learning-objectives/{objective_id}",
    response_model=IntegrationEnvelopeV1[LearningObjectiveProjectionV1],
)
async def get_learning_objective(
    objective_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[LearningObjectiveProjectionV1]:
    try:
        projection = await _service(request).get_learning_objective(objective_id, actor)
    except Exception as exc:
        raise _error(exc, "learning_objective_not_found") from exc
    return IntegrationEnvelopeV1(schema_version="v1", data=projection)


@router.get(
    "/instructional-blueprints/{blueprint_id}",
    response_model=IntegrationEnvelopeV1[InstructionalBlueprintProjectionV1],
)
async def get_instructional_blueprint(
    blueprint_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[InstructionalBlueprintProjectionV1]:
    try:
        projection = await _service(request).get_instructional_blueprint(blueprint_id, actor)
    except Exception as exc:
        raise _error(exc, "instructional_blueprint_not_found") from exc
    return IntegrationEnvelopeV1(schema_version="v1", data=projection)
