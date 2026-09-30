from datetime import UTC, datetime

import pytest
from test_course_generation import actor, authoring_request, draft

from app.content_generation.repository import InMemoryContentGenerationRepository
from app.content_generation.schemas import (
    ContentGenerationResult,
    ContentGenerationStatus,
    GenerationMetadata,
    GenerationRun,
    GenerationRunStatus,
)
from app.course_authoring.revision_schemas import (
    AssessmentQuestionRevision,
    CourseDraftRevisionRequest,
    CourseMetadataRevision,
    LessonTitleRevision,
    ModuleTitleRevision,
    SectionRevision,
)
from app.course_authoring.revision_service import (
    CourseDraftRevisionService,
    CourseRevisionConflictError,
    CourseRevisionValidationError,
)


class AuthoringReader:
    async def get(self, request_id: str, _actor: object) -> object:
        return authoring_request()


def stored_result() -> ContentGenerationResult:
    run = GenerationRun(
        run_id='generation-run-001',
        request_ref='course-authoring-request-001',
        provider='fake-provider',
        model='fake-model',
        prompt_version='sep-02-v2',
        started_at=datetime(2026, 8, 24, tzinfo=UTC),
        finished_at=datetime(2026, 8, 24, 0, 1, tzinfo=UTC),
        status=GenerationRunStatus.SUCCEEDED,
    )
    return ContentGenerationResult(
        id='content-generation-result-001',
        request_ref='course-authoring-request-001',
        version=1,
        status=ContentGenerationStatus.DRAFT,
        generation_metadata=GenerationMetadata(
            provider='fake-provider',
            model='fake-model',
            prompt_version='sep-02-v2',
            generation_run_id=run.run_id,
            created_at=run.finished_at,
        ),
        generation_run=run,
        source_blueprint_ref='blueprint-001',
        course_authoring_request_ref='course-authoring-request-001',
        generated_course=draft(),
        created_at=run.finished_at,
    )


async def seeded_service() -> tuple[CourseDraftRevisionService, InMemoryContentGenerationRepository]:
    repository = InMemoryContentGenerationRepository()
    await repository.create_result(stored_result())
    return CourseDraftRevisionService(
        repository=repository,
        authoring=AuthoringReader(),
    ), repository


@pytest.mark.asyncio
async def test_revision_creates_v2_preserves_content_and_records_sme_metadata() -> None:
    service, repository = await seeded_service()
    request = CourseDraftRevisionRequest(
        source_result_ref='content-generation-result-001',
        change_summary='Clarified the opening lesson for site use.',
        course_changes=CourseMetadataRevision(
            title='Python foundations for site teams',
            description=None,
        ),
        module_changes=[ModuleTitleRevision(module_order=1, title='Practical foundations')],
        lesson_changes=[LessonTitleRevision(module_order=1, lesson_order=1, title='Clean invalid values safely')],
        section_changes=[SectionRevision(
            module_order=1,
            lesson_order=1,
            section_order=1,
            title='Why this matters on site',
            content='Learners examine invalid values before analysis.',
        )],
        assessment_changes=[AssessmentQuestionRevision(
            question_index=0,
            prompt='What should be checked first on site?',
            expected_answer='Inspect missing and invalid values.',
        )],
    )

    revised = await service.create_revision(request, actor())

    assert revised.version == 2
    assert revised.supersedes_result_ref == 'content-generation-result-001'
    assert revised.status is ContentGenerationStatus.IN_REVIEW
    assert revised.revision_metadata is not None
    assert revised.revision_metadata.editor_actor_ref == str(actor().actor_id)
    assert revised.revision_metadata.source_version == 1
    assert revised.generation_run is not None
    assert revised.generation_run.run_id == 'generation-run-001'
    assert revised.generated_course is not None
    assert revised.generated_course.course.title == 'Python foundations for site teams'
    assert revised.generated_course.modules[0].lessons[0].sections[0].type.value == 'introduction'
    assert revised.generated_course.modules[0].lessons[0].sections[0].content == 'Learners examine invalid values before analysis.'
    assert (await repository.get_result('content-generation-result-001')).version == 1


@pytest.mark.asyncio
async def test_revision_rejects_stale_source_and_unknown_targets() -> None:
    service, repository = await seeded_service()
    await repository.create_result(stored_result().model_copy(update={
        'id': 'content-generation-result-002',
        'version': 2,
        'supersedes_result_ref': 'content-generation-result-001',
    }))

    stale = CourseDraftRevisionRequest(
        source_result_ref='content-generation-result-001',
        change_summary='Stale edit',
        lesson_changes=[LessonTitleRevision(module_order=1, lesson_order=1, title='Stale')],
    )
    with pytest.raises(CourseRevisionConflictError, match='stale'):
        await service.create_revision(stale, actor())

    unknown = CourseDraftRevisionRequest(
        source_result_ref='content-generation-result-002',
        change_summary='Unknown target',
        section_changes=[SectionRevision(
            module_order=9,
            lesson_order=1,
            section_order=1,
            title='Unknown',
            content='Unknown',
        )],
    )
    with pytest.raises(CourseRevisionValidationError, match='module_target'):
        await service.create_revision(unknown, actor())


@pytest.mark.asyncio
async def test_only_latest_result_can_be_marked_ready() -> None:
    service, repository = await seeded_service()
    revised = await service.create_revision(CourseDraftRevisionRequest(
        source_result_ref='content-generation-result-001',
        change_summary='Ready review',
        course_changes=CourseMetadataRevision(title='Reviewed foundations'),
    ), actor())

    with pytest.raises(CourseRevisionConflictError, match='latest'):
        await service.mark_ready('content-generation-result-001', actor())

    latest = await service.mark_ready(revised.id, actor())
    assert latest is not None
    assert latest.status is ContentGenerationStatus.READY_FOR_MATERIALIZATION


@pytest.mark.asyncio
async def test_content_approval_is_explicit_and_latest_version_bound() -> None:
    service, repository = await seeded_service()
    approved = await service.approve('content-generation-result-001', actor())

    assert approved.status is ContentGenerationStatus.APPROVED
    assert (await repository.get_result('content-generation-result-001')).status is ContentGenerationStatus.APPROVED


@pytest.mark.asyncio
async def test_rejected_content_cannot_be_approved_or_materialized() -> None:
    service, repository = await seeded_service()

    rejected = await service.reject('content-generation-result-001', actor(), reason='Needs factual review')

    assert rejected.status is ContentGenerationStatus.REJECTED
    with pytest.raises(CourseRevisionConflictError, match='rejected'):
        await service.approve('content-generation-result-001', actor())
    assert (await repository.get_result('content-generation-result-001')).status is ContentGenerationStatus.REJECTED
