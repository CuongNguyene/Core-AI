from pydantic import BaseModel, ConfigDict, Field

from app.content_generation.schemas import (
    ContentGenerationConstraints,
    ContentGenerationResult,
    ContentGenerationType,
    GenerationMetadata,
)
from app.content_generation.service import ContentGenerationRequestAccepted

ContentGenerationRequestAcceptedV1 = ContentGenerationRequestAccepted
ContentGenerationResultV1 = ContentGenerationResult


class ContentGenerationRequestCreateV1(BaseModel):
    """JSON-compatible API input; the service keeps the strict domain model."""

    model_config = ConfigDict(extra="forbid")

    blueprint_ref: str = Field(min_length=1)
    lesson_ref: str = Field(min_length=1)
    objective_refs: list[str] = Field(min_length=1)
    learning_need_refs: list[str] = Field(default_factory=list)
    generation_type: ContentGenerationType
    constraints: ContentGenerationConstraints = Field(
        default_factory=ContentGenerationConstraints
    )
    generation_metadata: GenerationMetadata = Field(default_factory=GenerationMetadata)

__all__ = [
    "ContentGenerationRequestAcceptedV1",
    "ContentGenerationRequestCreateV1",
    "ContentGenerationResultV1",
]
