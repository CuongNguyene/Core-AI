from typing import cast

from fastapi import APIRouter, Depends, Request, status

from app.authorization.schemas import ActorContext
from app.content_generation.errors import ContentGenerationNotFoundError
from app.integration.actor_context import get_signed_actor_context
from app.content_generation.schemas import ContentGenerationResult
from app.content_generation.service import (
    ContentGenerationRequestAccepted,
    ContentGenerationRequestCreate,
    ContentGenerationService,
)
from app.integration.auth import verify_integration_api_key
from app.integration.content_generation_schemas import (
    ContentGenerationRequestAcceptedV1,
    ContentGenerationRequestCreateV1,
    ContentGenerationResultV1,
)
from app.integration.schemas import IntegrationEnvelopeV1
from app.shared.errors import APIError

router = APIRouter(
    prefix="/api/v1/content-generation",
    tags=["content-generation"],
    dependencies=[Depends(verify_integration_api_key)],
)


def _service(request: Request) -> ContentGenerationService:
    service = getattr(request.app.state, "content_generation_service", None)
    if service is None:
        raise APIError(503, "content_generation_unavailable", "Content generation is not ready.")
    return cast(ContentGenerationService, service)


@router.post(
    "/requests",
    response_model=IntegrationEnvelopeV1[ContentGenerationRequestAcceptedV1],
    status_code=status.HTTP_201_CREATED,
)
async def create_content_generation_request(
    body: IntegrationEnvelopeV1[ContentGenerationRequestCreateV1],
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[ContentGenerationRequestAcceptedV1]:
    # A service API key identifies pai_frappe; the signed context identifies the
    # acting LMS user. Repository-level organization scope follows next.
    del actor
    accepted: ContentGenerationRequestAccepted = await _service(request).create(
        ContentGenerationRequestCreate(**body.data.model_dump())
    )
    return IntegrationEnvelopeV1(schema_version="v1", data=accepted)


@router.get(
    "/results/{result_id}",
    response_model=IntegrationEnvelopeV1[ContentGenerationResultV1],
)
async def get_content_generation_result(
    result_id: str,
    request: Request,
    actor: ActorContext = Depends(get_signed_actor_context),
) -> IntegrationEnvelopeV1[ContentGenerationResultV1]:
    del actor
    durable_repository = getattr(request.app.state, "content_generation_repository", None)
    if durable_repository is not None:
        durable_result = await durable_repository.get_result(result_id)
        if durable_result is not None:
            return IntegrationEnvelopeV1(schema_version="v1", data=durable_result)
    try:
        result: ContentGenerationResult = await _service(request).get_result(result_id)
    except ContentGenerationNotFoundError as exc:
        raise APIError(404, "content_generation_not_found", "Content generation result was not found.") from exc
    return IntegrationEnvelopeV1(schema_version="v1", data=result)
