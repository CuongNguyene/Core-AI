from typing import cast

from fastapi import APIRouter, Depends, Request

from app.integration.auth import verify_integration_api_key
from app.integration.schemas import (
    CompetencyResultReference,
    CourseBlueprintV1,
    IntegrationEnvelopeV1,
    LearningResultAccepted,
    LearningResultRequest,
)
from app.integration.service import IntegrationService
from app.shared.errors import APIError

router = APIRouter(
    prefix="/api/v1/integration",
    tags=["integration"],
    dependencies=[Depends(verify_integration_api_key)],
)


def _service(request: Request) -> IntegrationService:
    service = getattr(request.app.state, "integration_service", None)
    if service is None:
        raise APIError(503, "integration_service_unavailable", "Integration service is not ready.")
    return cast(IntegrationService, service)


@router.get(
    "/course-blueprints/{blueprint_id}",
    response_model=IntegrationEnvelopeV1[CourseBlueprintV1],
)
async def get_course_blueprint(blueprint_id: str, request: Request) -> IntegrationEnvelopeV1[CourseBlueprintV1]:
    blueprint = await _service(request).get_blueprint(blueprint_id)
    if blueprint is None:
        raise APIError(404, "course_blueprint_not_found", "Course blueprint was not found.")
    return IntegrationEnvelopeV1(schema_version="v1", data=blueprint)


@router.post(
    "/learning-results",
    response_model=IntegrationEnvelopeV1[LearningResultAccepted],
)
async def accept_learning_result(
    body: IntegrationEnvelopeV1[LearningResultRequest], request: Request
) -> IntegrationEnvelopeV1[LearningResultAccepted]:
    result = await _service(request).accept_learning_result(body)
    return IntegrationEnvelopeV1(schema_version="v1", data=result)


@router.get(
    "/competency-results/{result_id}",
    response_model=IntegrationEnvelopeV1[CompetencyResultReference],
)
async def get_competency_result(
    result_id: str, request: Request
) -> IntegrationEnvelopeV1[CompetencyResultReference]:
    result = await _service(request).get_competency_result(result_id)
    if result is None:
        raise APIError(404, "competency_result_not_found", "Competency result was not found.")
    return IntegrationEnvelopeV1(schema_version="v1", data=result)
