import pytest

from app.content_generation.schemas import (
    ContentGenerationStatus,
    ContentGenerationType,
)
from app.content_generation.service import (
    ContentGenerationNotFoundError,
    ContentGenerationRequestCreate,
    ContentGenerationService,
)


def valid_request() -> ContentGenerationRequestCreate:
    return ContentGenerationRequestCreate(
        blueprint_ref="blueprint-001",
        lesson_ref="lesson-001",
        objective_refs=["objective-001"],
        learning_need_refs=["learning-need-001"],
        generation_type=ContentGenerationType.LESSON_CONTENT,
    )


@pytest.mark.asyncio
async def test_create_returns_created_request_and_placeholder_result() -> None:
    service = ContentGenerationService()

    accepted = await service.create(valid_request())
    result = await service.get_result(accepted.result_id)

    assert accepted.status is ContentGenerationStatus.CREATED
    assert accepted.request_id
    assert result.request_ref == accepted.request_id
    assert result.lesson_ref == "lesson-001"
    assert result.source_blueprint_ref == "blueprint-001"
    assert result.objective_refs == ["objective-001"]
    assert result.learning_need_refs == ["learning-need-001"]
    assert result.version == 1
    assert result.supersedes_result_ref is None
    assert result.generation_run is None
    assert result.sections == []


@pytest.mark.asyncio
async def test_unknown_result_reference_fails_closed() -> None:
    service = ContentGenerationService()

    with pytest.raises(ContentGenerationNotFoundError):
        await service.get_result("content-missing")


@pytest.mark.asyncio
async def test_created_placeholder_does_not_invent_generation_metadata() -> None:
    service = ContentGenerationService()

    accepted = await service.create(valid_request())
    result = await service.get_result(accepted.result_id)

    assert result.generation_metadata.model_dump(exclude_none=True) == {}
