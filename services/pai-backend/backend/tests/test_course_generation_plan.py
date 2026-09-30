from datetime import UTC, datetime

import pytest

from app.content_generation.repository import InMemoryContentGenerationRepository
from app.content_generation.schemas import (
    GenerationRun,
    GenerationRunStatus,
)
from app.course_generation.plan_schemas import (
    CourseGenerationPlan,
    CourseGenerationPlanStatus,
    CourseLessonPlan,
    CourseModulePlan,
    LessonGenerationTask,
    LessonGenerationTaskStatus,
)


def plan() -> CourseGenerationPlan:
    return CourseGenerationPlan(
        id="plan-001",
        authoring_request_ref="request-001",
        parent_run_ref="run-course-001",
        course_title="Python foundations",
        course_description_context="Practical self-study course",
        module_plans=[CourseModulePlan(title="Foundations", order=1, lesson_refs=["lesson-1"])],
        lesson_descriptors=[CourseLessonPlan(
            lesson_ref="lesson-1",
            module_order=1,
            lesson_order=1,
            title="Clean invalid values",
            objective_refs=["objective-001"],
        )],
        language="vi",
        duration_constraint="90 minutes",
        prompt_version="sep-02.2-v1",
        quality_policy_version="sep-02.1-v1",
        status=CourseGenerationPlanStatus.PLANNED,
        created_at=datetime.now(UTC),
    )


def task() -> LessonGenerationTask:
    return LessonGenerationTask(
        id="task-001",
        plan_ref="plan-001",
        lesson_ref="lesson-1",
        module_order=1,
        lesson_order=1,
        lesson_title="Clean invalid values",
        objective_refs=["objective-001"],
        status=LessonGenerationTaskStatus.PENDING,
        attempt_count=0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def test_plan_preserves_immutable_module_and_lesson_descriptors() -> None:
    stored = plan()

    assert stored.module_plans[0].lesson_refs == ["lesson-1"]
    assert stored.lesson_descriptors[0].lesson_order == 1
    assert not hasattr(stored.lesson_descriptors[0], "status")


@pytest.mark.asyncio
async def test_repository_round_trips_plan_and_runtime_task_state() -> None:
    repository = InMemoryContentGenerationRepository()

    await repository.create_plan(plan())
    await repository.create_task(task())
    restored = await repository.get_task("task-001")

    assert restored is not None
    assert restored.status is LessonGenerationTaskStatus.PENDING
    assert restored.generated_lesson is None


def test_generation_run_supports_parent_and_lesson_hierarchy() -> None:
    run = GenerationRun(
        run_id="run-lesson-001",
        request_ref="request-001",
        parent_run_ref="run-course-001",
        unit_type="LESSON",
        unit_ref="lesson-1",
        provider="fake-provider",
        model="fake-model",
        prompt_version="sep-02.2-v1",
        started_at=datetime.now(UTC),
        status=GenerationRunStatus.RUNNING,
    )

    assert run.parent_run_ref == "run-course-001"
    assert run.unit_type == "LESSON"
    assert run.unit_ref == "lesson-1"
