import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from test_course_generation import ReferenceReader, actor, authoring_request, draft

from app.content_generation.repository import InMemoryContentGenerationRepository
from app.content_generation.schemas import (
    GeneratedLessonDraft,
    GenerationRun,
    GenerationRunStatus,
)
from app.course_authoring.schemas import CourseAuthoringMode, CourseAuthoringRequest
from app.course_generation.context import CourseGenerationContextBuilder
from app.course_generation.hierarchical_service import HierarchicalCourseGenerationService
from app.course_generation.plan_schemas import LessonGenerationTask, LessonGenerationTaskStatus
from app.curriculum_planning.duration import normalize_training_duration
from app.curriculum_planning.planner import DeterministicCurriculumPlanner
from app.curriculum_planning.schemas import CurriculumPlanningContext


class GoalAuthoring:
    async def get(self, _request_id: str, _actor: object) -> CourseAuthoringRequest:
        return authoring_request(CourseAuthoringMode.GOAL_DRIVEN)


def lesson_for(plan: object) -> GeneratedLessonDraft:
    objective_ref = plan.objective_refs[0] if plan.objective_refs else ""
    source = draft(objective_ref=objective_ref).modules[0].lessons[0]
    return GeneratedLessonDraft(
        lesson_ref=plan.lesson_ref,
        lesson=source.model_copy(
            update={
                "title": plan.title,
                "order": plan.lesson_order,
                "objective_refs": list(plan.objective_refs),
            }
        ),
        assessment=draft(objective_ref=objective_ref).assessment if objective_ref else None,
    )


class FakeLessonGenerator:
    def __init__(self, *, fail_once: set[str] | None = None, delay: float = 0.0) -> None:
        self.fail_once = fail_once or set()
        self.delay = delay
        self.calls: list[str] = []
        self.active = 0
        self.max_seen = 0

    async def generate(self, plan: object, _context: object, _prior: object = ()) -> GeneratedLessonDraft:
        self.calls.append(plan.lesson_ref)
        self.active += 1
        self.max_seen = max(self.max_seen, self.active)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            if plan.lesson_ref in self.fail_once:
                self.fail_once.remove(plan.lesson_ref)
                raise RuntimeError("provider_failure")
            return lesson_for(plan)
        finally:
            self.active -= 1


class ShallowLessonGenerator(FakeLessonGenerator):
    async def generate(self, plan: object, _context: object, _prior: object = ()) -> GeneratedLessonDraft:
        generated = lesson_for(plan)
        return generated.model_copy(
            update={
                "lesson": generated.lesson.model_copy(
                    update={
                        "sections": [
                            section.model_copy(
                                update={
                                    "content": "too short",
                                    "steps": [],
                                    "success_criteria": [],
                                }
                            )
                            for section in generated.lesson.sections
                        ]
                    }
                )
            }
        )


class RepairingLessonGenerator(FakeLessonGenerator):
    def __init__(
        self,
        *,
        repair_fails: bool = False,
        repair_breaks_objective_refs: bool = False,
    ) -> None:
        super().__init__()
        self.repair_fails = repair_fails
        self.repair_breaks_objective_refs = repair_breaks_objective_refs
        self.repair_contexts: list[object | None] = []

    async def generate(
        self,
        plan: object,
        _context: object,
        _prior: object = (),
        *,
        repair_context: object | None = None,
    ) -> GeneratedLessonDraft:
        self.calls.append(plan.lesson_ref)
        self.repair_contexts.append(repair_context)
        if repair_context is None and plan.lesson_order == 1:
            generated = lesson_for(plan)
            return generated.model_copy(
                update={
                    "lesson": generated.lesson.model_copy(
                        update={
                            "sections": [
                                section.model_copy(
                                    update={
                                        "content": "too short",
                                        "steps": [],
                                        "success_criteria": [],
                                    }
                                )
                                for section in generated.lesson.sections
                            ]
                        }
                    )
                }
            )
        generated = lesson_for(plan)
        if repair_context is not None and self.repair_fails and plan.lesson_order == 1:
            return generated.model_copy(
                update={
                    "lesson": generated.lesson.model_copy(
                        update={
                            "sections": [
                                section.model_copy(update={"content": "still too short"})
                                for section in generated.lesson.sections
                            ]
                        }
                    )
                }
            )
        if repair_context is not None and self.repair_breaks_objective_refs and plan.lesson_order == 1:
            return generated.model_copy(
                update={
                    "lesson": generated.lesson.model_copy(
                        update={"objective_refs": ["objective-changed"]}
                    )
                }
            )
        return generated


class FixedCurriculumPlanner:
    def __init__(self, plan: object) -> None:
        self.fixed_plan = plan

    async def plan(self, _context: object) -> object:
        return self.fixed_plan


def service(generator: FakeLessonGenerator) -> HierarchicalCourseGenerationService:
    return HierarchicalCourseGenerationService(
        authoring=GoalAuthoring(),
        context_builder=CourseGenerationContextBuilder(ReferenceReader()),
        generator=generator,
        repository=InMemoryContentGenerationRepository(),
        provider="fake-provider",
        model="fake-model",
        max_concurrency=2,
        generation_timeout_seconds=2,
    )


@pytest.mark.asyncio
async def test_goal_driven_generation_uses_duration_aware_curriculum_plan() -> None:
    generator = FakeLessonGenerator(delay=0.001)
    generation = service(generator)

    progress = await generation.start("request-goal-001", actor())
    completed = await generation.wait_for_plan(progress.plan_ref)

    assert completed.status == "COMPLETED"
    assert completed.total_lessons == 2
    assert completed.succeeded_lessons == 2
    assert completed.result_ref is not None
    assert generator.max_seen <= 2
    assert len(generator.calls) == 2

    result = await generation.get_result(completed.result_ref)
    assert result is not None
    persisted_plan = await generation._repository.get_plan(progress.plan_ref)
    assert persisted_plan is not None
    assert result.generation_metadata.curriculum_plan_ref == persisted_plan.curriculum_plan_ref
    assert len(result.generated_course.modules) == 1
    assert sum(len(module.lessons) for module in result.generated_course.modules) == 2
    assert all(
        lesson.lesson_ref is not None
        for module in result.generated_course.modules
        for lesson in module.lessons
    )
    assert len(result.generated_course.lesson_assessments) == 2


@pytest.mark.asyncio
async def test_module_smoke_scopes_tasks_and_never_assembles_course_result() -> None:
    repository = InMemoryContentGenerationRepository()
    planning_context = CurriculumPlanningContext(
        authoring_request_ref="course-authoring-request-001",
        mode=CourseAuthoringMode.GOAL_DRIVEN,
        course_title="Python Backend Developer",
        training_goal="Build production-ready backend capability",
        audience_summary={"learner_count": 10, "source": "MANUAL_SELECTION"},
        duration=normalize_training_duration("12 months"),
    )
    curriculum_plan = DeterministicCurriculumPlanner().plan_goal(planning_context)
    assert len(curriculum_plan.modules) > 1
    generation = HierarchicalCourseGenerationService(
        authoring=GoalAuthoring(),
        context_builder=CourseGenerationContextBuilder(ReferenceReader()),
        generator=FakeLessonGenerator(delay=0.001),
        repository=repository,
        provider="fake-provider",
        model="fake-model",
        max_concurrency=2,
        generation_timeout_seconds=2,
    )
    await repository.create_curriculum_plan(curriculum_plan)

    progress = await generation.start_module_smoke(
        "request-goal-001",
        actor(),
        curriculum_plan_ref=curriculum_plan.id,
        module_order=2,
    )
    completed = await generation.wait_for_plan(progress.plan_ref)
    tasks = await repository.list_tasks(progress.plan_ref)

    assert completed.status == "COMPLETED"
    assert completed.result_ref is None
    assert tasks
    smoke_plan = await repository.get_plan(progress.plan_ref)
    assert smoke_plan is not None
    assert smoke_plan.curriculum_plan_ref == curriculum_plan.id
    assert all(task.module_order == 2 for task in tasks)
    assert len(tasks) == len(curriculum_plan.modules[1].lessons)
    assert all(
        descriptor.estimated_total_effort_minutes
        == curriculum_plan.modules[1].lessons[index].estimated_total_effort_minutes
        for index, descriptor in enumerate(
            (await repository.get_plan(progress.plan_ref)).lesson_descriptors
        )
    )
    assert await repository.list_results("course-authoring-request-001") == []
    parent = await repository.get_run(completed.generation_run_ref)
    assert parent is not None
    assert parent.unit_type == "MODULE_SMOKE"


@pytest.mark.asyncio
async def test_module_smoke_retries_failed_lessons_only_once_without_full_result() -> None:
    repository = InMemoryContentGenerationRepository()
    planning_context = CurriculumPlanningContext(
        authoring_request_ref="course-authoring-request-001",
        mode=CourseAuthoringMode.GOAL_DRIVEN,
        course_title="Python Backend Developer",
        training_goal="Build production-ready backend capability",
        audience_summary={"learner_count": 10, "source": "MANUAL_SELECTION"},
        duration=normalize_training_duration("12 months"),
    )
    curriculum_plan = DeterministicCurriculumPlanner().plan_goal(planning_context)
    selected = curriculum_plan.modules[1]
    failed_ref = selected.lessons[-1].id
    generator = FakeLessonGenerator(fail_once={failed_ref})
    generation = HierarchicalCourseGenerationService(
        authoring=GoalAuthoring(),
        context_builder=CourseGenerationContextBuilder(ReferenceReader()),
        generator=generator,
        repository=repository,
        provider="fake-provider",
        model="fake-model",
        max_concurrency=2,
        generation_timeout_seconds=2,
    )
    await repository.create_curriculum_plan(curriculum_plan)

    progress = await generation.start_module_smoke(
        "request-goal-001",
        actor(),
        curriculum_plan_ref=curriculum_plan.id,
        module_order=2,
    )
    partial = await generation.wait_for_plan(progress.plan_ref)
    assert partial.status == "PARTIAL"
    await generation.retry_module_smoke(progress.plan_ref, actor())
    completed = await generation.wait_for_plan(progress.plan_ref)

    assert completed.status == "COMPLETED"
    assert completed.result_ref is None
    assert generator.calls.count(failed_ref) == 2
    assert len(generator.calls) == len(selected.lessons) + 1
    assert all(
        generator.calls.count(lesson.id) == 1
        for lesson in selected.lessons
        if lesson.id != failed_ref
    )


@pytest.mark.asyncio
async def test_rejected_lesson_persists_diagnostic_but_not_success_artifact() -> None:
    repository = InMemoryContentGenerationRepository()
    generation = HierarchicalCourseGenerationService(
        authoring=GoalAuthoring(),
        context_builder=CourseGenerationContextBuilder(ReferenceReader()),
        generator=ShallowLessonGenerator(),
        repository=repository,
        provider="fake-provider",
        model="fake-model",
        max_concurrency=2,
        generation_timeout_seconds=2,
    )

    progress = await generation.start("request-goal-001", actor())
    terminal = await generation.wait_for_plan(progress.plan_ref)
    tasks = await repository.list_tasks(progress.plan_ref)
    diagnostics = await repository.list_lesson_validation_diagnostics(
        "course-authoring-request-001"
    )

    assert terminal.status == "FAILED"
    assert all(task.generated_lesson is None for task in tasks)
    assert len(diagnostics) == len(tasks)
    assert all(diagnostic.sanitized_parsed_draft for diagnostic in diagnostics)
    assert all(
        set(diagnostic.issue_codes)
        >= {
            "section_depth_invalid",
            "guided_steps_missing",
            "independent_success_criteria_missing",
        }
        for diagnostic in diagnostics
    )
    replayed = await generation.replay_validation_diagnostic(diagnostics[0].id, actor())
    assert replayed.issue_codes == diagnostics[0].issue_codes
    assert replayed.section_metrics == diagnostics[0].section_metrics
    assert await repository.list_results("request-goal-001") == []


@pytest.mark.asyncio
async def test_persisted_lesson_task_ids_fit_storage_limit() -> None:
    generation = service(FakeLessonGenerator())

    progress = await generation.start("request-goal-001", actor())
    tasks = await generation._repository.list_tasks(progress.plan_ref)

    assert tasks
    assert all(len(task.id) <= 128 for task in tasks)
    assert all(task.lesson_ref.startswith("curriculum-lesson:") for task in tasks)

    await generation.wait_for_plan(progress.plan_ref)


@pytest.mark.asyncio
async def test_partial_plan_retries_failed_tasks_without_regenerating_successes() -> None:
    generator = FakeLessonGenerator(
        fail_once={"curriculum-lesson:course-authoring-request-001:001:002"}
    )
    generation = service(generator)

    progress = await generation.start("request-goal-001", actor())
    partial = await generation.wait_for_plan(progress.plan_ref)

    assert partial.status == "PARTIAL"
    assert partial.succeeded_lessons == 1
    assert partial.failed_lessons == 1
    first_calls = list(generator.calls)

    await generation.retry_failed(progress.plan_ref, actor())
    completed = await generation.wait_for_plan(progress.plan_ref)
    assert completed.status == "COMPLETED"
    assert completed.succeeded_lessons == 2
    assert generator.calls.count("curriculum-lesson:course-authoring-request-001:001:001") == 1
    assert generator.calls.count("curriculum-lesson:course-authoring-request-001:001:002") == 2
    assert len(generator.calls) == len(first_calls) + 1


@pytest.mark.asyncio
async def test_quality_failure_uses_diagnostic_guided_repair_and_preserves_successes() -> None:
    generator = RepairingLessonGenerator()
    generation = service(generator)

    progress = await generation.start("request-goal-001", actor())
    completed = await generation.wait_for_plan(progress.plan_ref)
    tasks = await generation._repository.list_tasks(progress.plan_ref)
    diagnostics = await generation._repository.list_lesson_validation_diagnostics(
        "course-authoring-request-001"
    )
    runs = [
        run
        for run in generation._repository.runs.values()
        if run.parent_run_ref == completed.generation_run_ref
    ]

    assert completed.status == "COMPLETED"
    assert generator.calls.count("curriculum-lesson:course-authoring-request-001:001:001") == 2
    assert generator.calls.count("curriculum-lesson:course-authoring-request-001:001:002") == 1
    assert len(diagnostics) == 1
    assert all(task.status is LessonGenerationTaskStatus.SUCCEEDED for task in tasks)
    repair_run = next(run for run in runs if run.generation_mode == "REPAIR")
    assert repair_run.repair_source_diagnostic_ref == diagnostics[0].id
    assert repair_run.prompt_version == "sep-02.2c-v1"
    assert repair_run.unit_type == "LESSON"
    assert sum(run.generation_mode == "REPAIR" for run in runs) == 1


@pytest.mark.asyncio
async def test_assembly_uses_planned_title_as_authoritative() -> None:
    generation = service(FakeLessonGenerator())

    progress = await generation.start("request-goal-001", actor())
    await generation.wait_for_plan(progress.plan_ref)
    plan, context = await generation._load_plan_context(progress.plan_ref, actor())
    tasks = await generation._repository.list_tasks(progress.plan_ref)
    first = tasks[0]
    assert first.generated_lesson is not None
    drifted = first.generated_lesson.model_copy(
        update={
            "lesson": first.generated_lesson.lesson.model_copy(
                update={"title": "Module 1 Assessment and Review"}
            )
        }
    )
    drifted_tasks = [
        task.model_copy(update={"generated_lesson": drifted})
        if task.id == first.id
        else task
        for task in tasks
    ]

    result = await generation._assemble(plan, context, drifted_tasks)

    assert result.generated_course.modules[0].lessons[0].title == plan.lesson_descriptors[0].title


@pytest.mark.asyncio
async def test_failed_repair_stops_at_two_attempts_without_success_artifact() -> None:
    generator = RepairingLessonGenerator(repair_fails=True)
    generation = service(generator)

    progress = await generation.start("request-goal-001", actor())
    terminal = await generation.wait_for_plan(progress.plan_ref)
    tasks = await generation._repository.list_tasks(progress.plan_ref)
    diagnostics = await generation._repository.list_lesson_validation_diagnostics(
        "course-authoring-request-001"
    )

    failed = next(task for task in tasks if task.lesson_order == 1)
    assert terminal.status == "PARTIAL"
    assert failed.status is LessonGenerationTaskStatus.FAILED
    assert failed.attempt_count == 2
    assert len([item for item in diagnostics if item.lesson_ref == failed.lesson_ref]) == 2
    assert failed.generated_lesson is None
    assert generator.calls.count(failed.lesson_ref) == 2


@pytest.mark.asyncio
async def test_repair_rejects_provenance_regression() -> None:
    generator = RepairingLessonGenerator(repair_breaks_objective_refs=True)
    generation = service(generator)

    progress = await generation.start("request-goal-001", actor())
    terminal = await generation.wait_for_plan(progress.plan_ref)
    tasks = await generation._repository.list_tasks(progress.plan_ref)
    diagnostics = await generation._repository.list_lesson_validation_diagnostics(
        "course-authoring-request-001"
    )

    failed = next(task for task in tasks if task.lesson_order == 1)
    repair_diagnostic = next(
        item
        for item in diagnostics
        if item.lesson_ref == failed.lesson_ref and item.attempt == 2
    )
    assert terminal.status == "PARTIAL"
    assert failed.status is LessonGenerationTaskStatus.FAILED
    assert failed.attempt_count == 2
    assert "objective_refs_invalid" in repair_diagnostic.issue_codes
    assert failed.generated_lesson is None


@pytest.mark.asyncio
async def test_progress_includes_ordered_lesson_details() -> None:
    generation = service(FakeLessonGenerator())
    progress = await generation.start("request-goal-001", actor())

    assert [item.lesson_order for item in progress.lessons] == [1, 2]
    assert all(item.status in {"PENDING", "RUNNING", "SUCCEEDED", "FAILED"} for item in progress.lessons)
    await generation.wait_for_plan(progress.plan_ref)


@pytest.mark.asyncio
async def test_fresh_service_resumes_persisted_stale_running_task() -> None:
    repository = InMemoryContentGenerationRepository()
    first = service(FakeLessonGenerator())
    first._repository = repository
    request = await GoalAuthoring().get("request-goal-001", actor())
    context = await CourseGenerationContextBuilder(ReferenceReader()).build(request, actor())
    parent = GenerationRun(
        run_id="parent-run-restart",
        request_ref=request.id,
        unit_type="COURSE",
        unit_ref="plan-restart",
        provider="fake-provider",
        model="fake-model",
        prompt_version="sep-02.2-v1",
        started_at=datetime.now(UTC),
        status=GenerationRunStatus.RUNNING,
    )
    await repository.create_run(parent)
    plan = first._build_plan(request, context, "plan-restart", parent.run_id)
    await repository.create_plan(plan)
    for descriptor in plan.lesson_descriptors:
        await repository.create_task(
            LessonGenerationTask(
                id=f"task:{descriptor.lesson_ref}",
                plan_ref=plan.id,
                lesson_ref=descriptor.lesson_ref,
                module_order=descriptor.module_order,
                lesson_order=descriptor.lesson_order,
                lesson_title=descriptor.title,
                objective_refs=list(descriptor.objective_refs),
                created_at=plan.created_at,
                updated_at=plan.created_at,
            )
        )
    stale = await repository.get_task("task:curriculum-lesson:course-authoring-request-001:001:001")
    assert stale is not None
    stale_run = parent.model_copy(update={
        "run_id": "child-run-stale",
        "parent_run_ref": parent.run_id,
        "unit_type": "LESSON",
        "unit_ref": stale.lesson_ref,
        "started_at": datetime.now(UTC) - timedelta(hours=1),
    })
    await repository.create_run(stale_run)
    await repository.update_task(stale.model_copy(update={
        "status": LessonGenerationTaskStatus.RUNNING,
        "attempt_count": 1,
        "latest_run_ref": stale_run.run_id,
        "updated_at": datetime.now(UTC) - timedelta(hours=1),
    }))

    resumed = HierarchicalCourseGenerationService(
        authoring=GoalAuthoring(),
        context_builder=CourseGenerationContextBuilder(ReferenceReader()),
        generator=FakeLessonGenerator(),
        repository=repository,
        provider="fake-provider",
        model="fake-model",
        max_concurrency=2,
        stale_run_after_seconds=1,
        generation_timeout_seconds=2,
    )
    await resumed.resume_plan(plan.id, actor())
    completed = await resumed.wait_for_plan(plan.id)

    assert completed.status == "COMPLETED"
    assert completed.succeeded_lessons == 2


@pytest.mark.asyncio
async def test_hierarchical_generation_creates_every_task_from_long_curriculum_plan() -> None:
    planning_context = CurriculumPlanningContext(
        authoring_request_ref="course-authoring-request-001",
        mode=CourseAuthoringMode.GOAL_DRIVEN,
        course_title="Python Backend Developer",
        training_goal="Build production-ready backend engineering capability",
        audience_summary={"learner_count": 10, "source": "MANUAL_SELECTION"},
        duration=normalize_training_duration("300 hours"),
    )
    curriculum_plan = DeterministicCurriculumPlanner().plan_goal(planning_context)
    expanded_modules = [
        module.model_copy(update={
            "estimated_hours": module.estimated_hours + (1 if module.order >= 7 else 0),
            "lessons": module.lessons + ([
                module.lessons[-1].model_copy(
                    update={
                        "id": f"{module.lessons[-1].id}:004",
                        "title": f"Integration practice {module.order}",
                        "order": len(module.lessons) + 1,
                    }
                )
            ] if module.order >= 7 else []),
        })
        for module in curriculum_plan.modules
    ]
    curriculum_plan = curriculum_plan.model_copy(update={
        "modules": expanded_modules,
        "estimated_total_learning_hours": 32,
    })
    generator = FakeLessonGenerator(delay=0.0001)
    generation = HierarchicalCourseGenerationService(
        authoring=GoalAuthoring(),
        context_builder=CourseGenerationContextBuilder(ReferenceReader()),
        generator=generator,
        repository=InMemoryContentGenerationRepository(),
        provider="fake-provider",
        model="fake-model",
        max_concurrency=2,
        generation_timeout_seconds=2,
        curriculum_planner=FixedCurriculumPlanner(curriculum_plan),
    )

    progress = await generation.start("request-goal-001", actor())
    completed = await generation.wait_for_plan(progress.plan_ref)

    assert completed.status == "COMPLETED"
    assert completed.total_lessons == 32
    assert len(generator.calls) == 32
    assert generator.max_seen <= 2
