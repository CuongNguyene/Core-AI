import pytest
from test_course_authoring_revision import seeded_service, stored_result
from test_course_generation import actor

from app.content_generation.repository import InMemoryContentGenerationRepository
from app.course_authoring.revision_schemas import CourseDraftRevisionRequest, SectionRevision
from app.course_authoring.revision_service import (
    CourseDraftRevisionService,
    CourseRevisionValidationError,
)


class AuthoringReader:
    async def get(self, _request_id: str, _actor: object) -> object:
        return stored_result()


@pytest.mark.asyncio
async def test_revision_preserves_all_protected_traceability_and_generation_fields() -> None:
    service, repository = await seeded_service()
    source = stored_result()
    revised = await service.create_revision(
        CourseDraftRevisionRequest(
            source_result_ref=source.id,
            change_summary="Clarified example",
            section_changes=[
                SectionRevision(
                    module_order=1,
                    lesson_order=1,
                    section_order=1,
                    content="New example content.",
                )
            ],
        ),
        actor(),
    )

    assert revised.request_ref == source.request_ref
    assert revised.objective_refs == source.objective_refs
    assert revised.learning_need_refs == source.learning_need_refs
    assert revised.source_blueprint_ref == source.source_blueprint_ref
    assert revised.course_authoring_request_ref == source.course_authoring_request_ref
    assert revised.generation_run == source.generation_run
    assert revised.generation_metadata == source.generation_metadata
    assert (await repository.get_result(source.id)) == source


@pytest.mark.asyncio
async def test_revision_without_a_generated_course_cannot_be_marked_ready() -> None:
    repository = InMemoryContentGenerationRepository()
    source = stored_result().model_copy(update={"generated_course": None})
    await repository.create_result(source)
    service = CourseDraftRevisionService(
        repository=repository,
        authoring=AuthoringReader(),
    )

    with pytest.raises(CourseRevisionValidationError, match="generated_course_required"):
        await service.mark_ready(source.id, actor())
