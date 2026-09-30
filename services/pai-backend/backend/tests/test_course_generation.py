import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.authorization.schemas import ActorContext, Role
from app.content_generation.repository import InMemoryContentGenerationRepository
from app.content_generation.schemas import (
    AssessmentQuestion,
    AssessmentQuestionType,
    ContentSectionType,
    GeneratedAssessmentDraft,
    GeneratedCourse,
    GeneratedCourseDraft,
    GeneratedCourseLesson,
    GeneratedCourseModule,
    GeneratedCourseSection,
    GenerationRun,
    GenerationRunStatus,
)
from app.course_authoring.schemas import (
    AudienceSnapshot,
    AudienceSnapshotSource,
    CourseAuthoringMode,
    CourseAuthoringRequest,
    CourseAuthoringStatus,
    TrainingBrief,
)
from app.course_generation.context import CourseGenerationContext, CourseGenerationContextBuilder
from app.course_generation.errors import (
    CourseGenerationOutputInvalidError,
    CourseGenerationProviderError,
)
from app.course_generation.generator import ModelGatewayCourseContentGenerator
from app.course_generation.service import CourseGenerationService
from app.course_generation.validation import (
    GeneratedCourseValidationError,
    validate_generated_course,
)
from app.instructional_blueprint.schemas import InstructionalPattern, LessonType
from app.learning_authoring.schemas import (
    InstructionalBlueprintProjection,
    LearningObjectiveProjection,
)

ACTOR_ID = UUID('11111111-1111-1111-1111-111111111111')


def actor() -> ActorContext:
    return ActorContext(
        actor_id=ACTOR_ID,
        organization_id=UUID('22222222-2222-2222-2222-222222222222'),
        roles=frozenset({Role.REVIEWER}),
        authentication_method='signed_actor_context',
    )


def objective() -> LearningObjectiveProjection:
    return LearningObjectiveProjection(
        id='objective-001',
        learning_need_ref='learning-need-001',
        statement='Handle invalid tabular values',
        bloom_level='apply',
        evidence_required=['cleaned dataset'],
        competency_id='python-cleaning',
        current_level=1,
        target_level=3,
        measurable_outcome='Clean invalid tabular values with Python.',
        gap_id='gap-001',
        sequence=1,
    )


def blueprint() -> InstructionalBlueprintProjection:
    return InstructionalBlueprintProjection(
        id='blueprint-001',
        version='instructional-blueprint-v1',
        learning_need_ref='learning-need-001',
        objective_refs=['objective-001'],
        course={
            'id': 'course-blueprint-001',
            'title': 'Python cleaning',
            'objective_refs': ['objective-001'],
            'module_refs': ['module-001'],
        },
        modules=[{
            'id': 'module-001',
            'title': 'Cleaning basics',
            'objective_refs': ['objective-001'],
            'lesson_refs': ['lesson-001'],
            'sequence': 1,
        }],
        lessons=[{
            'id': 'lesson-001',
            'title': 'Handle invalid values',
            'objective_refs': ['objective-001'],
            'lesson_type': LessonType.SKILL_PRACTICE,
            'estimated_minutes': 30,
            'instructional_pattern': [InstructionalPattern.CONCEPT_INTRODUCTION],
            'assessment_refs': [],
            'sequence': 1,
        }],
    )


def authoring_request(mode: CourseAuthoringMode = CourseAuthoringMode.GAP_DRIVEN) -> CourseAuthoringRequest:
    return CourseAuthoringRequest(
        id='course-authoring-request-001',
        title='Python foundations',
        training_brief=TrainingBrief(
            goal='Build practical Python foundations',
            language='vi',
            duration_constraint='90 minutes',
            target_completion_context='Before site rotation',
        ),
        audience_snapshot=AudienceSnapshot(
            id='audience-001',
            learner_refs=('learner-1', 'learner-2'),
            learner_count=2,
            captured_at=datetime(2026, 8, 24, tzinfo=UTC),
            source=AudienceSnapshotSource.MANUAL_SELECTION,
        ),
        learning_need_refs=('learning-need-001',) if mode is CourseAuthoringMode.GAP_DRIVEN else (),
        objective_refs=('objective-001',) if mode is CourseAuthoringMode.GAP_DRIVEN else (),
        instructional_blueprint_ref='blueprint-001' if mode is CourseAuthoringMode.GAP_DRIVEN else None,
        mode=mode,
        status=CourseAuthoringStatus.DRAFT,
        created_by_actor_ref=ACTOR_ID,
        created_at=datetime(2026, 8, 24, tzinfo=UTC),
    )


def draft(*, objective_ref: str = 'objective-001') -> GeneratedCourseDraft:
    minimums = {
        ContentSectionType.INTRODUCTION: 60,
        ContentSectionType.CONCEPT: 180,
        ContentSectionType.EXAMPLE: 100,
        ContentSectionType.GUIDED_PRACTICE: 100,
        ContentSectionType.INDEPENDENT_PRACTICE: 80,
        ContentSectionType.SUMMARY: 60,
    }
    return GeneratedCourseDraft(
        course=GeneratedCourse(
            title='Python foundations',
            description='A practical draft course for SME review with concrete learning activities.',
        ),
        modules=[GeneratedCourseModule(
            title='Foundations',
            order=1,
            lessons=[GeneratedCourseLesson(
                title='Clean invalid values',
                order=1,
                objective_refs=[objective_ref] if objective_ref else [],
                sections=[GeneratedCourseSection(
                    type=section_type,
                    title=section_type.value.replace('_', ' ').title(),
                    content=' '.join(f'word{index}' for index in range(count)),
                    order=index,
                    steps=['Inspect the task', 'Complete the guided action']
                    if section_type is ContentSectionType.GUIDED_PRACTICE
                    else [],
                    success_criteria=['The learner produces the expected result']
                    if section_type is ContentSectionType.INDEPENDENT_PRACTICE
                    else [],
                ) for index, (section_type, count) in enumerate(minimums.items(), start=1)],
            )],
        )],
        assessment=GeneratedAssessmentDraft(questions=[AssessmentQuestion(
            prompt='What should be checked first?',
            question_type=AssessmentQuestionType.SHORT_ANSWER,
            expected_answer='Inspect missing and invalid values.',
            objective_refs=[objective_ref] if objective_ref else [],
        )]),
    )


class ReferenceReader:
    async def get_learning_need(self, artifact_id: str, _actor: ActorContext) -> object:
        return SimpleNamespace(id=artifact_id)

    async def get_learning_objective(self, artifact_id: str, _actor: ActorContext) -> object:
        assert artifact_id == 'objective-001'
        return objective()

    async def get_instructional_blueprint(self, artifact_id: str, _actor: ActorContext) -> object:
        assert artifact_id == 'blueprint-001'
        return blueprint()


@pytest.mark.asyncio
async def test_generation_context_resolves_gap_artifacts_without_raw_audience_records() -> None:
    context = await CourseGenerationContextBuilder(ReferenceReader()).build(
        authoring_request(), actor()
    )

    assert context.authoring_request_ref == 'course-authoring-request-001'
    assert context.course_title == 'Python foundations'
    assert context.audience_summary.learner_count == 2
    assert context.audience_summary.model_dump().keys() == {'learner_count', 'source'}
    assert [item.id for item in context.learning_objectives] == ['objective-001']
    assert context.instructional_blueprint is not None


@pytest.mark.asyncio
async def test_goal_driven_context_does_not_fabricate_gap_artifacts() -> None:
    reader = ReferenceReader()
    context = await CourseGenerationContextBuilder(reader).build(
        authoring_request(CourseAuthoringMode.GOAL_DRIVEN), actor()
    )

    assert context.learning_need_refs == []
    assert context.learning_objectives == []
    assert context.instructional_blueprint is None


def test_generated_course_validation_preserves_supplied_objective_refs() -> None:
    context = CourseGenerationContext(
        authoring_request_ref='request-001',
        course_title='Python foundations',
        training_brief=TrainingBrief(goal='Goal'),
        audience_summary={'learner_count': 1, 'source': 'MANUAL_SELECTION'},
        learning_need_refs=['learning-need-001'],
        learning_objectives=[objective()],
        instructional_blueprint=blueprint(),
        language='vi',
        duration_constraint=None,
        target_completion_context=None,
    )

    validate_generated_course(draft(), context)
    with pytest.raises(GeneratedCourseValidationError, match='objective_reference'):
        validate_generated_course(draft(objective_ref='objective-invented'), context)


@pytest.mark.asyncio
async def test_model_gateway_generator_requests_structured_course_output() -> None:
    calls: list[object] = []

    class Gateway:
        async def infer_structured(self, request: object, output_schema: object) -> object:
            calls.append((request, output_schema))
            return SimpleNamespace(
                parsed=draft(),
                audit=SimpleNamespace(provider='fake-provider', model='fake-model'),
            )

    context = await CourseGenerationContextBuilder(ReferenceReader()).build(
        authoring_request(), actor()
    )
    generator = ModelGatewayCourseContentGenerator(
        gateway=Gateway(), requested_provider='fake-provider', correlation_id='corr-001'
    )

    result = await generator.generate(authoring_request(), context)

    assert result.course.title == 'Python foundations'
    assert len(result.modules[0].lessons[0].sections) == 6
    assert calls
    request, output_schema = calls[0]
    assert request.output_contract.schema_id == 'course_content_generation'
    assert output_schema is GeneratedCourseDraft
    assert request.payload['course_title'] == 'Python foundations'


class AuthoringReader:
    async def get(self, request_id: str, _actor: ActorContext) -> CourseAuthoringRequest | None:
        return authoring_request(CourseAuthoringMode.GOAL_DRIVEN) if request_id else None


class DraftGenerator:
    model_audits: list[object] = []

    async def generate(self, _request: CourseAuthoringRequest, _context: CourseGenerationContext) -> GeneratedCourseDraft:
        return draft(objective_ref='goal-driven-objective:course-authoring-request-001:1')


@pytest.mark.asyncio
async def test_generation_recovers_stale_running_run_before_starting_new_run() -> None:
    repository = InMemoryContentGenerationRepository()
    stale_run = GenerationRun(
        run_id='generation-run-stale',
        request_ref='course-authoring-request-001',
        provider='fake-provider',
        model='fake-model',
        prompt_version='sep-02-v3',
        started_at=datetime.now(UTC) - timedelta(minutes=10),
        status=GenerationRunStatus.RUNNING,
    )
    await repository.create_run(stale_run)
    service = CourseGenerationService(
        authoring=AuthoringReader(),
        context_builder=CourseGenerationContextBuilder(ReferenceReader()),
        generator=DraftGenerator(),
        repository=repository,
        provider='fake-provider',
        model='fake-model',
        stale_run_after_seconds=60,
    )

    accepted = await service.generate('course-authoring-request-001', actor())

    assert accepted.version == 1
    assert repository.runs['generation-run-stale'].status is GenerationRunStatus.FAILED
    assert repository.runs['generation-run-stale'].error_code == 'stale_run_recovered'


@pytest.mark.asyncio
async def test_cancelled_generation_marks_running_run_failed() -> None:
    class CancelledGenerator:
        model_audits: list[object] = []

        async def generate(
            self, _request: CourseAuthoringRequest, _context: CourseGenerationContext
        ) -> GeneratedCourseDraft:
            raise asyncio.CancelledError

    repository = InMemoryContentGenerationRepository()
    service = CourseGenerationService(
        authoring=AuthoringReader(),
        context_builder=CourseGenerationContextBuilder(ReferenceReader()),
        generator=CancelledGenerator(),
        repository=repository,
        provider='fake-provider',
        model='fake-model',
    )

    with pytest.raises(asyncio.CancelledError):
        await service.generate('course-authoring-request-001', actor())

    run = next(iter(repository.runs.values()))
    assert run.status is GenerationRunStatus.FAILED
    assert run.error_code == 'generation_cancelled'


@pytest.mark.asyncio
async def test_generation_timeout_marks_running_run_failed() -> None:
    class SlowGenerator:
        model_audits: list[object] = []

        async def generate(
            self, _request: CourseAuthoringRequest, _context: CourseGenerationContext
        ) -> GeneratedCourseDraft:
            await asyncio.sleep(1)
            return draft(objective_ref='goal-driven-objective:course-authoring-request-001:1')

    repository = InMemoryContentGenerationRepository()
    service = CourseGenerationService(
        authoring=AuthoringReader(),
        context_builder=CourseGenerationContextBuilder(ReferenceReader()),
        generator=SlowGenerator(),
        repository=repository,
        provider='fake-provider',
        model='fake-model',
        generation_timeout_seconds=0.01,
    )

    with pytest.raises(CourseGenerationProviderError, match='generation_timeout'):
        await service.generate('course-authoring-request-001', actor())

    run = next(iter(repository.runs.values()))
    assert run.status is GenerationRunStatus.FAILED
    assert run.error_code == 'generation_timeout'


@pytest.mark.asyncio
async def test_generation_service_persists_run_and_immutable_result_version_one() -> None:
    repository = InMemoryContentGenerationRepository()
    service = CourseGenerationService(
        authoring=AuthoringReader(),
        context_builder=CourseGenerationContextBuilder(ReferenceReader()),
        generator=DraftGenerator(),
        repository=repository,
        provider='fake-provider',
        model='fake-model',
    )

    accepted = await service.generate('course-authoring-request-001', actor())

    assert accepted.version == 1
    assert accepted.request_ref == 'course-authoring-request-001'
    assert accepted.result_ref
    result = await repository.get_result(accepted.result_ref)
    assert result is not None
    assert result.generated_course is not None
    assert result.supersedes_result_ref is None
    run = repository.runs[accepted.generation_run_ref]
    assert run.status.value == 'SUCCEEDED'
    assert run.provider == 'fake-provider'
    assert run.model == 'fake-model'
    assert run.prompt_version == 'sep-02-v3'


@pytest.mark.asyncio
async def test_generation_service_rejects_malformed_semantic_output_and_records_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class InvalidGenerator:
        model_audits: list[object] = []

        async def generate(self, _request: CourseAuthoringRequest, _context: CourseGenerationContext) -> GeneratedCourseDraft:
            return draft(objective_ref='objective-invented')

    repository = InMemoryContentGenerationRepository()
    service = CourseGenerationService(
        authoring=AuthoringReader(),
        context_builder=CourseGenerationContextBuilder(ReferenceReader()),
        generator=InvalidGenerator(),
        repository=repository,
        provider='fake-provider',
        model='fake-model',
    )

    with pytest.raises(CourseGenerationOutputInvalidError):
        await service.generate('course-authoring-request-001', actor())
    assert next(iter(repository.runs.values())).status.value == 'FAILED'
    assert 'lesson_objective_reference_invalid' in caplog.text


@pytest.mark.asyncio
async def test_generation_service_maps_gateway_failure() -> None:
    class FailedGenerator:
        model_audits: list[object] = []

        async def generate(self, _request: CourseAuthoringRequest, _context: CourseGenerationContext) -> GeneratedCourseDraft:
            raise RuntimeError('provider down')

    service = CourseGenerationService(
        authoring=AuthoringReader(),
        context_builder=CourseGenerationContextBuilder(ReferenceReader()),
        generator=FailedGenerator(),
        repository=InMemoryContentGenerationRepository(),
        provider='fake-provider',
        model='fake-model',
    )

    with pytest.raises(CourseGenerationProviderError):
        await service.generate('course-authoring-request-001', actor())
