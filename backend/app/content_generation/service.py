from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from .errors import ContentGenerationNotFoundError
from .schemas import (
    ContentGenerationConstraints,
    ContentGenerationRequest,
    ContentGenerationResult,
    ContentGenerationStatus,
    ContentGenerationType,
    GenerationMetadata,
)


class ContentGenerationRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    blueprint_ref: str = Field(min_length=1)
    lesson_ref: str = Field(min_length=1)
    objective_refs: list[str] = Field(min_length=1)
    learning_need_refs: list[str] = Field(default_factory=list)
    generation_type: ContentGenerationType
    constraints: ContentGenerationConstraints = Field(
        default_factory=ContentGenerationConstraints
    )
    generation_metadata: GenerationMetadata = Field(default_factory=GenerationMetadata)


class ContentGenerationRequestAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    request_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    status: ContentGenerationStatus


class ContentGenerationService:
    """Non-durable workflow store for content-generation authoring contracts."""

    _REQUEST_PREFIX: Final[str] = "request-"
    _RESULT_PREFIX: Final[str] = "content-"

    def __init__(self) -> None:
        self._next_id = 1
        self._requests: dict[str, ContentGenerationRequest] = {}
        self._results: dict[str, ContentGenerationResult] = {}

    async def create(
        self, request: ContentGenerationRequestCreate
    ) -> ContentGenerationRequestAccepted:
        request_id = f"{self._REQUEST_PREFIX}{self._next_id:03d}"
        result_id = f"{self._RESULT_PREFIX}{self._next_id:03d}"
        self._next_id += 1

        stored_request = ContentGenerationRequest(
            id=request_id,
            blueprint_ref=request.blueprint_ref,
            lesson_ref=request.lesson_ref,
            objective_refs=request.objective_refs,
            learning_need_refs=request.learning_need_refs,
            generation_type=request.generation_type,
            constraints=request.constraints,
            generation_metadata=request.generation_metadata,
        )
        result = ContentGenerationResult(
            id=result_id,
            request_ref=request_id,
            lesson_ref=request.lesson_ref,
            objective_refs=request.objective_refs,
            learning_need_refs=request.learning_need_refs,
            version=1,
            supersedes_result_ref=None,
            status=ContentGenerationStatus.CREATED,
            sections=[],
            generation_metadata=GenerationMetadata(),
            generation_run=None,
            source_blueprint_ref=request.blueprint_ref,
        )
        self._requests[request_id] = stored_request
        self._results[result_id] = result
        return ContentGenerationRequestAccepted(
            request_id=request_id,
            result_id=result_id,
            status=ContentGenerationStatus.CREATED,
        )

    async def get_result(self, result_id: str) -> ContentGenerationResult:
        try:
            return self._results[result_id]
        except KeyError as exc:
            raise ContentGenerationNotFoundError("content_generation_not_found") from exc
