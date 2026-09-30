import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Protocol
from uuid import uuid4

import structlog

from app.authorization.schemas import ActorContext
from app.content_generation.prompts import (
    LESSON_GENERATION_PROMPT_VERSION,
    LESSON_REPAIR_PROMPT_VERSION,
)
from app.content_generation.repository import ContentGenerationRepository
from app.content_generation.schemas import (
    ContentGenerationResult,
    ContentGenerationStatus,
    GeneratedCourse,
    GeneratedCourseDraft,
    GeneratedCourseLesson,
    GeneratedCourseModule,
    GeneratedLessonDraft,
    GenerationMetadata,
    GenerationRun,
    GenerationRunStatus,
    LessonAssessmentDraft,
    LessonValidationDiagnostic,
    LessonValidationReport,
)
from app.course_authoring.schemas import CourseAuthoringRequest
from app.curriculum_planning.planner import CurriculumPlanner, DeterministicCurriculumPlanner
from app.curriculum_planning.revision import CURRICULUM_REVIEW_WORKFLOW_VERSION
from app.curriculum_planning.schemas import CurriculumPlan, CurriculumPlanStatus
from app.curriculum_planning.service import (
    CurriculumPlanningService,
    planning_context_from_generation_context,
)

from .context import CourseGenerationContext, CourseGenerationContextBuilder
from .dispatch import CourseGenerationDispatch, SqlAlchemyCourseGenerationDispatchRepository
from .dispatcher import CourseGenerationDispatcher
from .errors import (
    CourseGenerationAlreadyInProgressError,
    CourseGenerationArtifactNotFoundError,
    CourseGenerationOutputInvalidError,
)
from .lesson_validation import (
    replay_lesson_validation_diagnostic,
    validate_generated_lesson_report,
)
from .plan_schemas import (
    CourseGenerationPlan,
    CourseGenerationPlanStatus,
    CourseLessonPlan,
    CourseModulePlan,
    LessonGenerationTask,
    LessonGenerationTaskStatus,
)
from .repair import (
    LessonRepairContext,
    build_lesson_repair_context,
    is_repairable_lesson_report,
)
from .schemas import CourseGenerationProgress, CourseGenerationProgressLesson

logger = structlog.get_logger(__name__)
MAX_LESSON_ATTEMPTS = 2


def require_confirmed_curriculum_for_generation(
    plan: CurriculumPlan, *, required: bool = False
) -> None:
    if (
        required or plan.planning_metadata.get("curriculum_review_workflow_version") == "sep-08d-v1"
    ) and plan.status is not CurriculumPlanStatus.CONFIRMED:
        raise CourseGenerationArtifactNotFoundError("curriculum_plan_not_confirmed")


class CourseAuthoringRequestReader(Protocol):
    async def get(self, request_id: str, actor: ActorContext) -> CourseAuthoringRequest: ...


class LessonContentGenerator(Protocol):
    @property
    def model_audits(self) -> Sequence[object]: ...

    async def generate(
        self,
        lesson_plan: CourseLessonPlan,
        context: CourseGenerationContext,
        prior_learning_summary: Sequence[dict[str, object]],
        *,
        repair_context: LessonRepairContext | None = None,
    ) -> GeneratedLessonDraft: ...


class HierarchicalCourseGenerationService:
    """Resumable lesson-level generation with deterministic course assembly."""

    def __init__(
        self,
        *,
        authoring: CourseAuthoringRequestReader,
        context_builder: CourseGenerationContextBuilder,
        generator: LessonContentGenerator,
        repository: ContentGenerationRepository,
        provider: str,
        model: str,
        max_concurrency: int = 2,
        stale_run_after_seconds: float = 360.0,
        generation_timeout_seconds: float = 120.0,
        enforce_content_quality: bool = True,
        curriculum_planner: CurriculumPlanner | None = None,
        dispatcher: CourseGenerationDispatcher | None = None,
        dispatches: SqlAlchemyCourseGenerationDispatchRepository | None = None,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency_must_be_positive")
        self._authoring = authoring
        self._context_builder = context_builder
        self._generator = generator
        self._repository = repository
        self._provider = provider
        self._model = model
        self._max_concurrency = max_concurrency
        self._stale_run_after_seconds = stale_run_after_seconds
        self._generation_timeout_seconds = generation_timeout_seconds
        self._enforce_content_quality = enforce_content_quality
        self._curriculum_planner = curriculum_planner or DeterministicCurriculumPlanner()
        self._dispatcher = dispatcher
        self._dispatches = dispatches
        self._jobs: dict[str, asyncio.Task[None]] = {}

    async def start(self, request_id: str, actor: ActorContext) -> CourseGenerationProgress:
        request = await self._authoring.get(request_id, actor)
        context = await self._context_builder.build(request, actor)
        self._require_context(request, context)
        curriculum_plan = await self._create_curriculum_plan(request, context)
        require_confirmed_curriculum_for_generation(
            curriculum_plan, required=request.mode.value == "GAP_DRIVEN"
        )
        if request.mode.value == "GOAL_DRIVEN":
            context = await self._context_builder.build(
                request,
                actor,
                generated_objectives_override=CurriculumPlanningService.goal_objectives_for_context(
                    curriculum_plan
                ),
            )
        return await self._start_execution(
            request=request,
            context=context,
            curriculum_plan=curriculum_plan,
            actor=actor,
            plan_prefix="course-generation-plan",
            run_unit_type="COURSE",
            assemble_result=True,
        )

    async def start_module_smoke(
        self,
        request_id: str,
        actor: ActorContext,
        *,
        curriculum_plan_ref: str,
        module_order: int,
    ) -> CourseGenerationProgress:
        """Run one persisted curriculum module without creating a course result.

        This is an internal developer smoke boundary. The normal ``start`` path
        remains full-curriculum generation and assembles a ContentGenerationResult.
        """
        request = await self._authoring.get(request_id, actor)
        curriculum_plan = await self._repository.get_curriculum_plan(curriculum_plan_ref)
        if curriculum_plan is None or curriculum_plan.authoring_request_ref != request.id:
            raise CourseGenerationArtifactNotFoundError("curriculum_plan_not_found")
        selected_module = next(
            (module for module in curriculum_plan.modules if module.order == module_order),
            None,
        )
        if selected_module is None:
            raise CourseGenerationArtifactNotFoundError("curriculum_module_not_found")
        context = await self._context_builder.build(request, actor)
        self._require_context(request, context)
        if request.mode.value == "GOAL_DRIVEN":
            context = await self._context_builder.build(
                request,
                actor,
                generated_objectives_override=CurriculumPlanningService.goal_objectives_for_context(
                    curriculum_plan
                ),
            )
        scoped_plan = curriculum_plan.model_copy(update={"modules": [selected_module]})
        return await self._start_execution(
            request=request,
            context=context,
            curriculum_plan=scoped_plan,
            actor=actor,
            plan_prefix="module-smoke-course-generation-plan",
            run_unit_type="MODULE_SMOKE",
            assemble_result=False,
        )

    async def retry_module_smoke(
        self, plan_id: str, actor: ActorContext
    ) -> CourseGenerationProgress:
        plan, context = await self._load_plan_context(plan_id, actor)
        parent = await self._repository.get_run(plan.parent_run_ref)
        if parent is None or parent.unit_type != "MODULE_SMOKE":
            raise CourseGenerationArtifactNotFoundError("module_smoke_plan_not_found")
        await self._recover_stale_parent(plan.authoring_request_ref)
        await self._recover_stale_tasks(plan)
        failed = [
            task
            for task in await self._repository.list_tasks(plan.id)
            if task.status is LessonGenerationTaskStatus.FAILED
            and task.attempt_count < MAX_LESSON_ATTEMPTS
        ]
        if not failed:
            return await self.get_progress(plan.id)
        await self._repository.update_plan(
            plan.model_copy(update={"status": CourseGenerationPlanStatus.RUNNING})
        )
        await self._schedule(
            plan.id,
            context,
            actor,
            {LessonGenerationTaskStatus.FAILED},
            assemble_result=False,
        )
        return await self.get_progress(plan.id)

    async def _start_execution(
        self,
        *,
        request: CourseAuthoringRequest,
        context: CourseGenerationContext,
        curriculum_plan: CurriculumPlan,
        actor: ActorContext,
        plan_prefix: str,
        run_unit_type: str,
        assemble_result: bool,
    ) -> CourseGenerationProgress:
        await self._recover_stale_parent(request.id)
        if await self._repository.get_active_run(request.id) is not None:
            raise CourseGenerationAlreadyInProgressError("generation_already_in_progress")
        plan_id = f"{plan_prefix}-{uuid4().hex}"
        parent_run = GenerationRun(
            run_id=f"generation-run-{uuid4().hex}",
            request_ref=request.id,
            unit_type=run_unit_type,
            unit_ref=plan_id,
            provider=self._provider,
            model=self._model,
            prompt_version=LESSON_GENERATION_PROMPT_VERSION,
            started_at=datetime.now(UTC),
            status=GenerationRunStatus.RUNNING,
        )
        await self._repository.create_run(parent_run)
        plan = self._build_plan(
            request, context, plan_id, parent_run.run_id, curriculum_plan=curriculum_plan
        )
        await self._repository.create_plan(plan)
        for descriptor in plan.lesson_descriptors:
            await self._repository.create_task(
                LessonGenerationTask(
                    id=self._task_id(plan.id, descriptor.lesson_ref),
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
        running = plan.model_copy(update={"status": CourseGenerationPlanStatus.RUNNING})
        await self._repository.update_plan(running)
        if self._dispatches is not None:
            await self._dispatches.create(
                CourseGenerationDispatch(
                    plan_ref=plan.id,
                    actor_id=actor.actor_id,
                    task_statuses=(LessonGenerationTaskStatus.PENDING.value,),
                    assemble_result=assemble_result,
                    queued_at=datetime.now(UTC),
                )
            )
        await self._schedule(
            plan.id,
            context,
            actor,
            {LessonGenerationTaskStatus.PENDING},
            assemble_result=assemble_result,
        )
        return await self.get_progress(plan.id)

    @staticmethod
    def _task_id(plan_id: str, lesson_ref: str) -> str:
        digest = sha256(f"{plan_id}:{lesson_ref}".encode()).hexdigest()
        return f"lesson-generation-task:{digest}"

    async def retry_failed(self, plan_id: str, actor: ActorContext) -> CourseGenerationProgress:
        plan, context = await self._load_plan_context(plan_id, actor)
        await self._recover_stale_parent(plan.authoring_request_ref)
        if await self._repository.get_active_run(plan.authoring_request_ref) is not None:
            raise CourseGenerationAlreadyInProgressError("generation_already_in_progress")
        await self._recover_stale_tasks(plan)
        failed = await self._repository.list_tasks(plan.id)
        if not any(
            task.status is LessonGenerationTaskStatus.FAILED
            and task.attempt_count < MAX_LESSON_ATTEMPTS
            for task in failed
        ):
            return await self.get_progress(plan.id)
        await self._repository.update_plan(
            plan.model_copy(update={"status": CourseGenerationPlanStatus.RUNNING})
        )
        await self._schedule(plan.id, context, actor, {LessonGenerationTaskStatus.FAILED})
        return await self.get_progress(plan.id)

    async def resume_plan(self, plan_id: str, actor: ActorContext) -> CourseGenerationProgress:
        plan, context = await self._load_plan_context(plan_id, actor)
        await self._recover_stale_parent(plan.authoring_request_ref)
        local_job = self._jobs.get(plan_id)
        if local_job is not None and not local_job.done():
            raise CourseGenerationAlreadyInProgressError("generation_already_in_progress")
        await self._recover_stale_tasks(plan)
        tasks = await self._repository.list_tasks(plan.id)
        if not any(task.status is LessonGenerationTaskStatus.PENDING for task in tasks):
            return await self.get_progress(plan.id)
        await self._repository.update_plan(
            plan.model_copy(update={"status": CourseGenerationPlanStatus.RUNNING})
        )
        await self._schedule(plan.id, context, actor, {LessonGenerationTaskStatus.PENDING})
        return await self.get_progress(plan.id)

    async def wait_for_plan(self, plan_id: str) -> CourseGenerationProgress:
        job = self._jobs.get(plan_id)
        if job is not None:
            await job
        return await self.get_progress(plan_id)

    async def get_progress(self, plan_id: str) -> CourseGenerationProgress:
        plan = await self._repository.get_plan(plan_id)
        if plan is None:
            raise CourseGenerationArtifactNotFoundError("course_generation_plan_not_found")
        tasks = await self._repository.list_tasks(plan.id)
        succeeded = sum(task.status is LessonGenerationTaskStatus.SUCCEEDED for task in tasks)
        failed = sum(task.status is LessonGenerationTaskStatus.FAILED for task in tasks)
        pending = sum(task.status is LessonGenerationTaskStatus.PENDING for task in tasks)
        return CourseGenerationProgress(
            plan_ref=plan.id,
            request_ref=plan.authoring_request_ref,
            generation_run_ref=plan.parent_run_ref,
            status=plan.status.value,
            total_lessons=len(tasks),
            succeeded_lessons=succeeded,
            failed_lessons=failed,
            pending_lessons=pending,
            lessons=[
                CourseGenerationProgressLesson(
                    task_ref=task.id,
                    lesson_ref=task.lesson_ref,
                    title=task.lesson_title,
                    module_order=task.module_order,
                    lesson_order=task.lesson_order,
                    status=task.status.value,
                    attempt_count=task.attempt_count,
                    error_code=task.error_code,
                )
                for task in tasks
            ],
            result_ref=await self._result_ref_for_plan(plan),
        )

    async def get_latest_progress(self, request_ref: str) -> CourseGenerationProgress:
        plans = await self._repository.list_plans(request_ref)
        if not plans:
            raise CourseGenerationArtifactNotFoundError("course_generation_plan_not_found")
        return await self.get_progress(plans[0].id)

    async def get_result(self, result_id: str) -> ContentGenerationResult | None:
        return await self._repository.get_result(result_id)

    async def run_dispatched_plan(
        self,
        plan_id: str,
        actor: ActorContext,
        *,
        task_statuses: tuple[str, ...],
        assemble_result: bool,
    ) -> None:
        """Worker-only execution path after a durable dispatch lease is claimed."""
        plan, context = await self._load_plan_context(plan_id, actor)
        await self._run_plan(
            plan.id,
            context,
            actor,
            {LessonGenerationTaskStatus(status) for status in task_statuses},
            assemble_result=assemble_result,
        )

    async def replay_validation_diagnostic(
        self, diagnostic_id: str, actor: ActorContext
    ) -> LessonValidationReport:
        diagnostic = await self._repository.get_lesson_validation_diagnostic(diagnostic_id)
        if diagnostic is None:
            raise CourseGenerationArtifactNotFoundError("lesson_validation_diagnostic_not_found")
        plan, context = await self._load_plan_context(diagnostic.plan_ref, actor)
        descriptor = next(
            (item for item in plan.lesson_descriptors if item.lesson_ref == diagnostic.lesson_ref),
            None,
        )
        if descriptor is None:
            raise CourseGenerationArtifactNotFoundError("lesson_generation_task_not_found")
        return replay_lesson_validation_diagnostic(
            diagnostic,
            expected_lesson_ref=descriptor.lesson_ref,
            expected_lesson_title=descriptor.title,
            expected_objective_refs=descriptor.objective_refs,
            allowed_objective_refs={objective.id for objective in context.learning_objectives}
            | {objective.id for objective in context.generated_objectives},
            duration_constraint=plan.duration_constraint,
            enforce_content_quality=self._enforce_content_quality,
        )

    async def _schedule(
        self,
        plan_id: str,
        context: CourseGenerationContext,
        actor: ActorContext,
        statuses: set[LessonGenerationTaskStatus],
        *,
        assemble_result: bool = True,
    ) -> None:
        if self._dispatcher is not None:
            if self._dispatches is not None:
                await self._dispatches.requeue(
                    plan_id,
                    task_statuses=tuple(status.value for status in statuses),
                    assemble_result=assemble_result,
                )
            await self._dispatcher.enqueue(plan_id)
            return
        job = asyncio.create_task(
            self._run_plan(plan_id, context, actor, statuses, assemble_result=assemble_result)
        )
        self._jobs[plan_id] = job

        def forget(completed: asyncio.Task[None]) -> None:
            if self._jobs.get(plan_id) is completed:
                self._jobs.pop(plan_id, None)

        job.add_done_callback(forget)

    async def _run_plan(
        self,
        plan_id: str,
        context: CourseGenerationContext,
        actor: ActorContext,
        statuses: set[LessonGenerationTaskStatus],
        *,
        assemble_result: bool,
    ) -> None:
        del actor
        semaphore = asyncio.Semaphore(self._max_concurrency)
        tasks = [
            task
            for task in await self._repository.list_tasks(plan_id)
            if task.status in statuses and task.attempt_count < MAX_LESSON_ATTEMPTS
        ]
        await asyncio.gather(
            *(self._run_task(task, plan_id, context, semaphore) for task in tasks),
            return_exceptions=True,
        )
        plan = await self._repository.get_plan(plan_id)
        if plan is None:
            return
        current_tasks = await self._repository.list_tasks(plan_id)
        if all(task.status is LessonGenerationTaskStatus.SUCCEEDED for task in current_tasks):
            if not assemble_result:
                await self._repository.update_plan(
                    plan.model_copy(update={"status": CourseGenerationPlanStatus.COMPLETED})
                )
                parent = await self._repository.get_run(plan.parent_run_ref)
                if parent is not None:
                    await self._repository.update_run(
                        parent.model_copy(
                            update={
                                "status": GenerationRunStatus.SUCCEEDED,
                                "finished_at": datetime.now(UTC),
                            }
                        )
                    )
                return
            try:
                result = await self._assemble(plan, context, current_tasks)
                await self._repository.update_plan(
                    plan.model_copy(update={"status": CourseGenerationPlanStatus.COMPLETED})
                )
                parent = await self._repository.get_run(plan.parent_run_ref)
                if parent is not None:
                    await self._repository.update_run(
                        parent.model_copy(
                            update={
                                "status": GenerationRunStatus.SUCCEEDED,
                                "finished_at": datetime.now(UTC),
                            }
                        )
                    )
                del result
                return
            except Exception:
                await self._mark_plan_failed(plan, "course_assembly_invalid")
                return
        succeeded = any(
            task.status is LessonGenerationTaskStatus.SUCCEEDED for task in current_tasks
        )
        status = (
            CourseGenerationPlanStatus.PARTIAL if succeeded else CourseGenerationPlanStatus.FAILED
        )
        await self._repository.update_plan(plan.model_copy(update={"status": status}))
        parent = await self._repository.get_run(plan.parent_run_ref)
        if parent is not None:
            await self._repository.update_run(
                parent.model_copy(
                    update={
                        "status": GenerationRunStatus.FAILED,
                        "finished_at": datetime.now(UTC),
                        "error_code": "lesson_generation_partial"
                        if succeeded
                        else "lesson_generation_failed",
                    }
                )
            )

    async def _run_task(
        self,
        task: LessonGenerationTask,
        plan_id: str,
        context: CourseGenerationContext,
        semaphore: asyncio.Semaphore,
    ) -> None:
        async with semaphore:
            task_state = task
            repair_context: LessonRepairContext | None = None
            repair_source_diagnostic_ref: str | None = None
            while task_state.attempt_count < MAX_LESSON_ATTEMPTS:
                now = datetime.now(UTC)
                plan = await self._repository.get_plan(plan_id)
                if plan is None:
                    return
                descriptor = next(
                    item for item in plan.lesson_descriptors if item.lesson_ref == task.lesson_ref
                )
                is_repair = repair_context is not None
                child_run = GenerationRun(
                    run_id=f"generation-run-{uuid4().hex}",
                    request_ref=context.authoring_request_ref,
                    parent_run_ref=plan.parent_run_ref,
                    unit_type="LESSON",
                    unit_ref=task.lesson_ref,
                    generation_mode="REPAIR" if is_repair else "INITIAL",
                    repair_source_diagnostic_ref=repair_source_diagnostic_ref,
                    provider=self._provider,
                    model=self._model,
                    prompt_version=(
                        LESSON_REPAIR_PROMPT_VERSION
                        if is_repair
                        else LESSON_GENERATION_PROMPT_VERSION
                    ),
                    started_at=now,
                    status=GenerationRunStatus.RUNNING,
                )
                running = task_state.model_copy(
                    update={
                        "status": LessonGenerationTaskStatus.RUNNING,
                        "attempt_count": task_state.attempt_count + 1,
                        "latest_run_ref": child_run.run_id,
                        "updated_at": now,
                        "error_code": None,
                    }
                )
                await self._repository.update_task(running)
                await self._repository.create_run(child_run)
                try:
                    prior = await self._prior_learning_summary(
                        plan_id, task.module_order, task.lesson_order
                    )
                    if repair_context is None:
                        generated = await asyncio.wait_for(
                            self._generator.generate(descriptor, context, prior),
                            timeout=self._generation_timeout_seconds,
                        )
                    else:
                        generated = await asyncio.wait_for(
                            self._generator.generate(
                                descriptor,
                                context,
                                prior,
                                repair_context=repair_context,
                            ),
                            timeout=self._generation_timeout_seconds,
                        )
                    validation_report = validate_generated_lesson_report(
                        generated,
                        expected_lesson_ref=descriptor.lesson_ref,
                        expected_lesson_title=descriptor.title,
                        expected_objective_refs=descriptor.objective_refs,
                        allowed_objective_refs={
                            objective.id for objective in context.learning_objectives
                        }
                        | {objective.id for objective in context.generated_objectives},
                        duration_constraint=context.duration_constraint,
                        enforce_content_quality=self._enforce_content_quality,
                    )
                    if not validation_report.valid:
                        diagnostic = LessonValidationDiagnostic(
                            id=f"lesson-validation-diagnostic:{uuid4().hex}",
                            authoring_request_ref=context.authoring_request_ref,
                            plan_ref=plan.id,
                            task_ref=running.id,
                            lesson_ref=descriptor.lesson_ref,
                            attempt=running.attempt_count,
                            generation_run_ref=child_run.run_id,
                            provider=self._provider,
                            model=self._model,
                            prompt_version=child_run.prompt_version
                            or LESSON_GENERATION_PROMPT_VERSION,
                            created_at=datetime.now(UTC),
                            sanitized_parsed_draft=generated.model_dump(mode="json"),
                            validation_issues=validation_report.issues,
                            section_metrics=validation_report.section_metrics,
                            assessment_summary=validation_report.assessment_summary,
                        )
                        await self._repository.create_lesson_validation_diagnostic(diagnostic)
                        finished = datetime.now(UTC)
                        await self._repository.update_run(
                            child_run.model_copy(
                                update={
                                    "status": GenerationRunStatus.FAILED,
                                    "finished_at": finished,
                                    "error_code": "generation_output_invalid",
                                }
                            )
                        )
                        if (
                            not is_repair
                            and running.attempt_count < MAX_LESSON_ATTEMPTS
                            and is_repairable_lesson_report(validation_report)
                        ):
                            repair_context = build_lesson_repair_context(
                                validation_report, diagnostic
                            )
                            repair_source_diagnostic_ref = diagnostic.id
                            logger.info(
                                "lesson_generation_repair_started",
                                task_ref=running.id,
                                lesson_ref=descriptor.lesson_ref,
                                source_diagnostic_ref=diagnostic.id,
                                deficient_sections=[
                                    item.section_type for item in repair_context.deficient_sections
                                ],
                                deficits=[
                                    item.deficit_words for item in repair_context.deficient_sections
                                ],
                            )
                            task_state = running
                            continue
                        await self._fail_task(running, child_run, "generation_output_invalid")
                        if is_repair:
                            logger.info(
                                "lesson_generation_repair_completed",
                                task_ref=running.id,
                                lesson_ref=descriptor.lesson_ref,
                                validation_result="FAILED",
                                remaining_issue_codes=validation_report.issue_codes,
                            )
                        return
                    finished = datetime.now(UTC)
                    await self._repository.update_task(
                        running.model_copy(
                            update={
                                "status": LessonGenerationTaskStatus.SUCCEEDED,
                                "generated_lesson": generated,
                                "updated_at": finished,
                            }
                        )
                    )
                    await self._repository.update_run(
                        child_run.model_copy(
                            update={
                                "status": GenerationRunStatus.SUCCEEDED,
                                "finished_at": finished,
                            }
                        )
                    )
                    if is_repair:
                        logger.info(
                            "lesson_generation_repair_completed",
                            task_ref=running.id,
                            lesson_ref=descriptor.lesson_ref,
                            validation_result="SUCCEEDED",
                            remaining_issue_codes=[],
                        )
                    return
                except asyncio.CancelledError:
                    await self._fail_task(running, child_run, "generation_cancelled")
                    raise
                except TimeoutError:
                    await self._fail_task(running, child_run, "generation_timeout")
                    return
                except CourseGenerationOutputInvalidError:
                    await self._fail_task(running, child_run, "generation_output_invalid")
                    return
                except Exception:
                    await self._fail_task(running, child_run, "gateway_failure")
                    return

    async def _fail_task(
        self, task: LessonGenerationTask, run: GenerationRun, error_code: str
    ) -> None:
        now = datetime.now(UTC)
        await self._repository.update_task(
            task.model_copy(
                update={
                    "status": LessonGenerationTaskStatus.FAILED,
                    "error_code": error_code,
                    "updated_at": now,
                }
            )
        )
        await self._repository.update_run(
            run.model_copy(
                update={
                    "status": GenerationRunStatus.FAILED,
                    "finished_at": now,
                    "error_code": error_code,
                }
            )
        )

    async def _assemble(
        self,
        plan: CourseGenerationPlan,
        context: CourseGenerationContext,
        tasks: list[LessonGenerationTask],
    ) -> ContentGenerationResult:
        by_ref = {task.lesson_ref: task.generated_lesson for task in tasks}
        descriptors_by_ref = {
            descriptor.lesson_ref: descriptor for descriptor in plan.lesson_descriptors
        }
        modules: list[GeneratedCourseModule] = []
        assessments: list[LessonAssessmentDraft] = []
        for module in plan.module_plans:
            lessons: list[GeneratedCourseLesson] = []
            for lesson_ref in module.lesson_refs:
                generated = by_ref.get(lesson_ref)
                if generated is None:
                    raise CourseGenerationOutputInvalidError("lesson_artifact_missing")
                descriptor = descriptors_by_ref.get(lesson_ref)
                if descriptor is None:
                    raise CourseGenerationOutputInvalidError("lesson_descriptor_missing")
                lessons.append(
                    generated.lesson.model_copy(
                        update={"lesson_ref": descriptor.lesson_ref, "title": descriptor.title}
                    )
                )
                if generated.assessment is not None:
                    assessments.append(
                        LessonAssessmentDraft(
                            lesson_ref=generated.lesson_ref,
                            assessment=generated.assessment,
                        )
                    )
            modules.append(
                GeneratedCourseModule(title=module.title, order=module.order, lessons=lessons)
            )
        now = datetime.now(UTC)
        parent = await self._repository.get_run(plan.parent_run_ref)
        latest = await self._repository.get_latest_result(plan.authoring_request_ref)
        curriculum_plan = (
            await self._repository.get_curriculum_plan(plan.curriculum_plan_ref)
            if plan.curriculum_plan_ref
            else None
        )
        result = ContentGenerationResult(
            id=f"content-generation-result-{uuid4().hex}",
            request_ref=plan.authoring_request_ref,
            objective_refs=[item.id for item in context.learning_objectives]
            + [item.id for item in context.generated_objectives],
            generated_objectives=list(context.generated_objectives),
            learning_need_refs=list(context.learning_need_refs),
            version=latest.version + 1 if latest is not None else 1,
            supersedes_result_ref=latest.id if latest is not None else None,
            status=ContentGenerationStatus.DRAFT,
            generation_metadata=GenerationMetadata(
                prompt_version=LESSON_GENERATION_PROMPT_VERSION,
                model=self._model,
                provider=self._provider,
                created_at=now,
                generation_run_id=plan.parent_run_ref,
                curriculum_plan_ref=plan.curriculum_plan_ref,
                curriculum_plan_version=curriculum_plan.version if curriculum_plan else None,
            ),
            generation_run=parent,
            source_blueprint_ref=(
                context.instructional_blueprint.id
                if context.instructional_blueprint is not None
                else None
            ),
            course_authoring_request_ref=plan.authoring_request_ref,
            generated_course=GeneratedCourseDraft(
                course=GeneratedCourse(
                    title=plan.course_title,
                    description=plan.course_description_context,
                ),
                modules=modules,
                lesson_assessments=assessments,
            ),
            created_at=now,
        )
        return await self._repository.create_result(result)

    async def _load_plan_context(
        self, plan_id: str, actor: ActorContext
    ) -> tuple[CourseGenerationPlan, CourseGenerationContext]:
        plan = await self._repository.get_plan(plan_id)
        if plan is None:
            raise CourseGenerationArtifactNotFoundError("course_generation_plan_not_found")
        request = await self._authoring.get(plan.authoring_request_ref, actor)
        context = await self._context_builder.build(request, actor)
        self._require_context(request, context)
        curriculum_plan = (
            await self._repository.get_curriculum_plan(plan.curriculum_plan_ref)
            if plan.curriculum_plan_ref
            else None
        )
        if curriculum_plan is None:
            planning_context = planning_context_from_generation_context(request, context)
            fallback = DeterministicCurriculumPlanner()
            curriculum_plan = (
                fallback.plan_goal(planning_context)
                if request.mode.value == "GOAL_DRIVEN"
                else fallback.plan_gap(planning_context)
            )
        require_confirmed_curriculum_for_generation(
            curriculum_plan, required=request.mode.value == "GAP_DRIVEN"
        )
        if request.mode.value == "GOAL_DRIVEN":
            context = await self._context_builder.build(
                request,
                actor,
                generated_objectives_override=CurriculumPlanningService.goal_objectives_for_context(
                    curriculum_plan
                ),
            )
        return plan, context

    async def _recover_stale_parent(self, request_ref: str) -> None:
        active = await self._repository.get_active_run(request_ref)
        if active is None or active.started_at is None:
            return
        if datetime.now(UTC) - active.started_at <= timedelta(
            seconds=self._stale_run_after_seconds
        ):
            return
        await self._repository.update_run(
            active.model_copy(
                update={
                    "status": GenerationRunStatus.FAILED,
                    "finished_at": datetime.now(UTC),
                    "error_code": "stale_run_recovered",
                }
            )
        )

    async def _recover_stale_tasks(self, plan: CourseGenerationPlan) -> None:
        now = datetime.now(UTC)
        for task in await self._repository.list_tasks(plan.id):
            if task.status is not LessonGenerationTaskStatus.RUNNING:
                continue
            if now - task.updated_at <= timedelta(seconds=self._stale_run_after_seconds):
                continue
            if task.latest_run_ref:
                run = await self._repository.get_run(task.latest_run_ref)
                if run is not None and run.status is GenerationRunStatus.RUNNING:
                    await self._repository.update_run(
                        run.model_copy(
                            update={
                                "status": GenerationRunStatus.FAILED,
                                "finished_at": now,
                                "error_code": "stale_run_recovered",
                            }
                        )
                    )
            await self._repository.update_task(
                task.model_copy(
                    update={
                        "status": LessonGenerationTaskStatus.PENDING,
                        "error_code": "stale_task_recovered",
                        "updated_at": now,
                    }
                )
            )

    async def _prior_learning_summary(
        self, plan_id: str, current_module_order: int, current_lesson_order: int
    ) -> list[dict[str, object]]:
        tasks = await self._repository.list_tasks(plan_id)
        return [
            {
                "title": task.generated_lesson.lesson.title,
                "objective_refs": list(task.generated_lesson.lesson.objective_refs),
                "summary": next(
                    section.content
                    for section in task.generated_lesson.lesson.sections
                    if section.type.value == "summary"
                ),
            }
            for task in tasks
            if task.status is LessonGenerationTaskStatus.SUCCEEDED
            and (task.module_order, task.lesson_order)
            < (current_module_order, current_lesson_order)
            and task.generated_lesson is not None
        ]

    async def _result_ref_for_plan(self, plan: CourseGenerationPlan) -> str | None:
        results = await self._repository.list_results(plan.authoring_request_ref)
        for result in results:
            if (
                result.generation_run is not None
                and result.generation_run.run_id == plan.parent_run_ref
            ):
                return result.id
        return None

    async def _mark_plan_failed(self, plan: CourseGenerationPlan, error_code: str) -> None:
        await self._repository.update_plan(
            plan.model_copy(update={"status": CourseGenerationPlanStatus.FAILED})
        )
        parent = await self._repository.get_run(plan.parent_run_ref)
        if parent is not None:
            await self._repository.update_run(
                parent.model_copy(
                    update={
                        "status": GenerationRunStatus.FAILED,
                        "finished_at": datetime.now(UTC),
                        "error_code": error_code,
                    }
                )
            )

    async def _create_curriculum_plan(
        self,
        request: CourseAuthoringRequest,
        context: CourseGenerationContext,
    ) -> CurriculumPlan:
        existing = await self._repository.list_curriculum_plans(request.id)
        if existing:
            return existing[0]
        planning_context = planning_context_from_generation_context(request, context)
        plan = await self._curriculum_planner.plan(planning_context)
        plan = plan.model_copy(
            update={
                "id": f"curriculum-plan:{uuid4().hex}",
                "version": 1,
                "supersedes_plan_ref": None,
                "planning_metadata": {
                    **plan.planning_metadata,
                    **(
                        {
                            "curriculum_review_workflow_version": CURRICULUM_REVIEW_WORKFLOW_VERSION,
                            "review_status": "READY_FOR_REVIEW",
                        }
                        if request.mode.value == "GAP_DRIVEN"
                        or request.authoring_workflow_version == "sep-08a-v1"
                        else {}
                    ),
                },
                "status": (
                    CurriculumPlanStatus.READY_FOR_REVIEW
                    if request.mode.value == "GAP_DRIVEN"
                    or request.authoring_workflow_version == "sep-08a-v1"
                    else plan.status
                ),
            }
        )
        return await self._repository.create_curriculum_plan(plan)

    @staticmethod
    def _require_context(request: CourseAuthoringRequest, context: CourseGenerationContext) -> None:
        if request.mode.value == "GAP_DRIVEN" and not context.learning_objectives:
            raise CourseGenerationArtifactNotFoundError(
                "course_generation_objective_context_required"
            )

    @staticmethod
    def _build_plan(
        request: CourseAuthoringRequest,
        context: CourseGenerationContext,
        plan_id: str,
        parent_run_ref: str,
        curriculum_plan: CurriculumPlan | None = None,
    ) -> CourseGenerationPlan:
        modules: list[CourseModulePlan]
        descriptors: list[CourseLessonPlan]
        if curriculum_plan is not None:
            modules = []
            descriptors = []
            for curriculum_module in curriculum_plan.modules:
                module_descriptors = []
                for curriculum_lesson in curriculum_module.lessons:
                    descriptor = CourseLessonPlan(
                        lesson_ref=curriculum_lesson.id,
                        module_order=curriculum_module.order,
                        lesson_order=curriculum_lesson.order,
                        title=curriculum_lesson.title,
                        objective_refs=list(curriculum_lesson.objective_refs),
                        estimated_minutes=curriculum_lesson.estimated_minutes,
                        lesson_type=curriculum_lesson.lesson_type,
                        workload_category=curriculum_lesson.workload_category,
                        estimated_instruction_minutes=curriculum_lesson.estimated_instruction_minutes,
                        estimated_practice_minutes=curriculum_lesson.estimated_practice_minutes,
                        estimated_total_effort_minutes=curriculum_lesson.estimated_total_effort_minutes,
                    )
                    descriptors.append(descriptor)
                    module_descriptors.append(descriptor.lesson_ref)
                modules.append(
                    CourseModulePlan(
                        title=curriculum_module.title,
                        order=curriculum_module.order,
                        lesson_refs=module_descriptors,
                        estimated_hours=curriculum_module.estimated_hours,
                    )
                )
        elif context.instructional_blueprint is not None:
            modules = []
            descriptors = []
            lessons = sorted(
                context.instructional_blueprint.lessons,
                key=lambda item: getattr(item, "sequence", getattr(item, "order", 1)),
            )
            for blueprint_module in sorted(
                context.instructional_blueprint.modules,
                key=lambda item: getattr(item, "sequence", getattr(item, "order", 1)),
            ):
                module_order = getattr(
                    blueprint_module, "sequence", getattr(blueprint_module, "order", 1)
                )
                module_lesson_refs = list(getattr(blueprint_module, "lesson_refs", []))
                selected = [item for item in lessons if item.id in module_lesson_refs]
                module_descriptors = []
                for lesson_order, blueprint_lesson in enumerate(selected, start=1):
                    descriptor = CourseLessonPlan(
                        lesson_ref=blueprint_lesson.id,
                        module_order=module_order,
                        lesson_order=lesson_order,
                        title=blueprint_lesson.title,
                        objective_refs=list(blueprint_lesson.objective_refs),
                    )
                    descriptors.append(descriptor)
                    module_descriptors.append(descriptor.lesson_ref)
                if module_descriptors:
                    modules.append(
                        CourseModulePlan(
                            title=blueprint_module.title,
                            order=module_order,
                            lesson_refs=module_descriptors,
                        )
                    )
        else:
            fallback_context = planning_context_from_generation_context(request, context)
            fallback = DeterministicCurriculumPlanner()
            fallback_plan = (
                fallback.plan_goal(fallback_context)
                if request.mode.value == "GOAL_DRIVEN"
                else fallback.plan_gap(fallback_context)
            )
            return HierarchicalCourseGenerationService._build_plan(
                request,
                context,
                plan_id,
                parent_run_ref,
                curriculum_plan=fallback_plan,
            )
        return CourseGenerationPlan(
            id=plan_id,
            authoring_request_ref=request.id,
            parent_run_ref=parent_run_ref,
            course_title=context.course_title,
            course_description_context=context.training_brief.goal,
            module_plans=modules,
            lesson_descriptors=descriptors,
            language=context.language,
            duration_constraint=context.duration_constraint,
            prompt_version=LESSON_GENERATION_PROMPT_VERSION,
            quality_policy_version="sep-02.1-v1",
            curriculum_plan_ref=curriculum_plan.id if curriculum_plan is not None else None,
            created_at=datetime.now(UTC),
        )
