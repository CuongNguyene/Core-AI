from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_course_generation import actor, authoring_request, draft
from test_course_generation_plan import plan, task
from test_curriculum_planning import small_plan
from test_lesson_generation import lesson_draft

from app.content_generation.repository import SqlAlchemyContentGenerationRepository
from app.content_generation.schemas import (
    ContentGenerationResult,
    ContentGenerationStatus,
    CurriculumPlanningAttempt,
    CurriculumPlanningAttemptStatus,
    GeneratedLessonDraft,
    GenerationMetadata,
    GenerationRun,
    GenerationRunStatus,
    GoalDerivedLearningObjective,
    LessonAssessmentValidationSummary,
    LessonValidationDiagnostic,
    LessonValidationIssue,
    LessonValidationSectionMetrics,
)
from app.course_authoring.repository import SqlAlchemyCourseAuthoringRepository
from app.course_authoring.revision_schemas import CourseDraftRevisionRequest, CourseMetadataRevision
from app.course_authoring.revision_service import CourseDraftRevisionService
from app.course_generation.plan_schemas import LessonGenerationTaskStatus
from app.curriculum_planning.duration import (
    DurationUnit,
    NormalizedTrainingDuration,
    WeeklyEffortSource,
)
from app.curriculum_planning.schemas import CurriculumPlanValidationIssue
from app.shared.database import Base


@pytest.mark.asyncio
async def test_sql_repositories_round_trip_request_generation_run_and_draft() -> None:
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    authoring_repository = SqlAlchemyCourseAuthoringRepository(session_factory)
    request = authoring_request()
    await authoring_repository.create(request)
    restored_request = await authoring_repository.get(request.id)
    assert restored_request is not None
    assert restored_request.audience_snapshot.learner_refs == ('learner-1', 'learner-2')

    generation_repository = SqlAlchemyContentGenerationRepository(session_factory)
    run = GenerationRun(
        run_id='generation-run-001',
        request_ref=request.id,
        provider='fake-provider',
        model='fake-model',
        prompt_version='sep-02-v2',
        started_at=datetime(2026, 8, 24, tzinfo=UTC),
        status=GenerationRunStatus.RUNNING,
    )
    await generation_repository.create_run(run)
    completed = run.model_copy(update={
        'finished_at': datetime(2026, 8, 24, 0, 1, tzinfo=UTC),
        'status': GenerationRunStatus.SUCCEEDED,
    })
    await generation_repository.update_run(completed)
    result = ContentGenerationResult(
        id='content-generation-result-001',
        request_ref=request.id,
        version=1,
        status=ContentGenerationStatus.DRAFT,
        generation_metadata=GenerationMetadata(
            provider='fake-provider',
            model='fake-model',
        prompt_version='sep-02-v2',
            generation_run_id=run.run_id,
            created_at=datetime(2026, 8, 24, 0, 1, tzinfo=UTC),
        ),
        generation_run=completed,
        source_blueprint_ref='blueprint-001',
        course_authoring_request_ref=request.id,
        generated_course=draft(),
        generated_objectives=[GoalDerivedLearningObjective(
            id="goal-driven-objective:request-goal-001:1",
            statement="Build practical foundations",
            measurable_outcome=None,
            sequence=1,
            origin="GOAL_DRIVEN_TRAINING_BRIEF",
        )],
    )
    await generation_repository.create_result(result)

    restored_result = await generation_repository.get_result(result.id)
    assert restored_result is not None
    assert restored_result.version == 1
    assert restored_result.generated_course is not None
    assert restored_result.generation_run is not None
    assert restored_result.generation_run.status is GenerationRunStatus.SUCCEEDED
    assert restored_result.generated_objectives[0].origin == "GOAL_DRIVEN_TRAINING_BRIEF"
    assert restored_result.generated_objectives[0].measurable_outcome is None
    await engine.dispose()


@pytest.mark.asyncio
async def test_sql_repository_round_trips_curriculum_plan_for_get_projection() -> None:
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    repository = SqlAlchemyContentGenerationRepository(session_factory)
    plan_value = small_plan()
    await repository.create_curriculum_plan(plan_value)

    restored = await repository.get_curriculum_plan(plan_value.id)
    latest = await repository.list_curriculum_plans(plan_value.authoring_request_ref)

    assert restored is not None
    assert restored.id == plan_value.id
    assert restored.normalized_duration.duration_unit.value == 'months'
    assert restored.status.value == 'PLANNED'
    assert latest[0].modules[0].lessons[0].title == 'Backend skill 1'
    await engine.dispose()


@pytest.mark.asyncio
async def test_sql_repository_round_trips_failed_curriculum_planning_attempt() -> None:
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    repository = SqlAlchemyContentGenerationRepository(session_factory)
    attempt = CurriculumPlanningAttempt(
        id='curriculum-planning-attempt:001',
        authoring_request_ref='course-authoring-request-001',
        correlation_id='correlation-001',
        provider='gemini',
        model='gemini-test',
        prompt_id='curriculum_planning',
        prompt_version='sep-02.3-v1',
        created_at=datetime(2026, 8, 25, tzinfo=UTC),
        completed_at=datetime(2026, 8, 25, 0, 1, tzinfo=UTC),
        status=CurriculumPlanningAttemptStatus.FAILED,
        original_duration_constraint='12 months',
        normalized_duration=NormalizedTrainingDuration(
            duration_value=12,
            duration_unit=DurationUnit.MONTHS,
            estimated_total_weeks=52,
            weekly_effort_hours=3,
            weekly_effort_source=WeeklyEffortSource.DEFAULT,
            estimated_total_learning_hours=156,
        ),
        weekly_effort_hours=3,
        weekly_effort_source=WeeklyEffortSource.DEFAULT,
        estimated_total_learning_hours=156,
        min_modules=5,
        max_modules=10,
        min_lessons=18,
        max_lessons=40,
        objective_count=1,
        module_count=3,
        lesson_count=6,
        estimated_candidate_hours=24,
        covered_objective_count=0,
        validation_issues=[CurriculumPlanValidationIssue(
            code='lesson_count_out_of_bounds',
            message='Lesson count is outside the duration policy bounds.',
            path='modules.lessons',
            actual=6,
            expected='18-40',
        )],
        uncovered_objective_refs=['goal-driven-objective:request:001'],
        unknown_objective_refs=[],
        sanitized_parsed_candidate={
            'id': 'candidate-001',
            'authoring_request_ref': 'course-authoring-request-001',
            'course_title': 'Python Backend Developer',
        },
    )

    await repository.create_curriculum_planning_attempt(attempt)
    restored = await repository.get_curriculum_planning_attempt(attempt.id)
    latest = await repository.list_curriculum_planning_attempts(attempt.authoring_request_ref)

    assert restored is not None
    assert restored.id == attempt.id
    assert restored.status is CurriculumPlanningAttemptStatus.FAILED
    assert restored.normalized_duration.estimated_total_weeks == 52
    assert restored.weekly_effort_source is WeeklyEffortSource.DEFAULT
    assert restored.min_modules == 5
    assert restored.max_lessons == 40
    assert restored.objective_count == 1
    assert restored.module_count == 3
    assert restored.lesson_count == 6
    assert latest[0].id == attempt.id
    assert latest[0].sanitized_parsed_candidate['course_title'] == 'Python Backend Developer'
    assert latest[0].validation_issues[0].code == 'lesson_count_out_of_bounds'
    await engine.dispose()


@pytest.mark.asyncio
async def test_sql_repository_round_trips_rejected_lesson_validation_diagnostic() -> None:
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    repository = SqlAlchemyContentGenerationRepository(session_factory)
    diagnostic = LessonValidationDiagnostic(
        id='lesson-validation-diagnostic:001',
        authoring_request_ref='course-authoring-request-001',
        plan_ref='plan-001',
        task_ref='task-001',
        lesson_ref='lesson-001',
        attempt=2,
        generation_run_ref='generation-run-001',
        provider='gemini',
        model='gemini-3.5-flash-lite',
        prompt_version='sep-02.2-v1',
        created_at=datetime(2026, 8, 25, tzinfo=UTC),
        sanitized_parsed_draft=lesson_draft().model_dump(mode='json'),
        validation_issues=[LessonValidationIssue(
            code='section_depth_invalid',
            path='lesson.sections[1].content',
            message='section below threshold',
            actual=100,
            expected=180,
        )],
        section_metrics=[LessonValidationSectionMetrics(
            section_type='concept',
            content_words=100,
            steps_words=0,
            success_criteria_words=0,
            effective_words=100,
            threshold=180,
        )],
        assessment_summary=LessonAssessmentValidationSummary(
            present=True,
            question_count=1,
            multiple_choice_count=0,
            short_answer_count=1,
            objective_refs=['objective-001'],
            invalid_objective_refs=[],
            mcq_invalid_count=0,
            missing_answer_count=0,
        ),
    )

    await repository.create_lesson_validation_diagnostic(diagnostic)
    restored = await repository.get_lesson_validation_diagnostic(diagnostic.id)
    listed = await repository.list_lesson_validation_diagnostics(
        diagnostic.authoring_request_ref
    )

    assert restored is not None
    assert restored.attempt == 2
    assert restored.issue_codes == ['section_depth_invalid']
    assert restored.section_metrics[0].effective_words == 100
    assert restored.assessment_summary.question_count == 1
    assert listed[0].id == diagnostic.id
    await engine.dispose()


@pytest.mark.asyncio
async def test_sql_repository_round_trips_hierarchical_plan_and_task_descriptors() -> None:
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    repository = SqlAlchemyContentGenerationRepository(session_factory)
    await repository.create_plan(plan())
    await repository.create_task(task())
    generated_task = task().model_copy(update={
        'status': LessonGenerationTaskStatus.SUCCEEDED,
        'generated_lesson': GeneratedLessonDraft(
            lesson_ref='lesson-1',
            lesson=draft().modules[0].lessons[0],
            assessment=draft().assessment,
        ),
    })
    await repository.update_task(generated_task)

    restored_plan = await repository.get_plan('plan-001')
    restored_tasks = await repository.list_tasks('plan-001')

    assert restored_plan is not None
    assert restored_plan.lesson_descriptors[0].lesson_ref == 'lesson-1'
    assert len(restored_tasks) == 1
    assert restored_tasks[0].status.value == 'SUCCEEDED'
    assert restored_tasks[0].generated_lesson is not None
    assert restored_tasks[0].generated_lesson.lesson.sections[0].type.value == 'introduction'
    await engine.dispose()


@pytest.mark.asyncio
async def test_sql_repository_persists_immutable_sme_revision_metadata() -> None:
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    repository = SqlAlchemyContentGenerationRepository(session_factory)
    original = ContentGenerationResult(
        id='result-v1',
        request_ref='course-authoring-request-001',
        version=1,
        status=ContentGenerationStatus.DRAFT,
        generation_metadata=GenerationMetadata(
            provider='fake-provider',
            model='fake-model',
        prompt_version='sep-02-v2',
            created_at=datetime(2026, 8, 24, 0, 1, tzinfo=UTC),
        ),
        generated_course=draft(),
        created_at=datetime(2026, 8, 24, 0, 1, tzinfo=UTC),
    )
    await repository.create_result(original)

    class Authoring:
        async def get(self, _request_ref: str, _actor: object) -> object:
            return object()

    revised = await CourseDraftRevisionService(
        repository=repository,
        authoring=Authoring(),
    ).create_revision(CourseDraftRevisionRequest(
        source_result_ref='result-v1',
        change_summary='Updated title',
        course_changes=CourseMetadataRevision(title='Reviewed Python foundations'),
    ), actor=actor())

    restored = await repository.get_result(revised.id)
    assert restored is not None
    assert restored.version == 2
    assert restored.revision_metadata is not None
    assert restored.revision_metadata.change_summary == 'Updated title'
    assert (await repository.get_result('result-v1')).version == 1
    await engine.dispose()
