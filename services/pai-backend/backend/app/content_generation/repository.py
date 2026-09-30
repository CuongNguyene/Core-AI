import json
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.course_generation.plan_schemas import (
    CourseGenerationPlan,
    CourseGenerationPlanStatus,
    LessonGenerationTask,
    LessonGenerationTaskStatus,
)
from app.curriculum_planning.schemas import CurriculumPlan

from .models import (
    ContentGenerationResultRecord,
    CourseGenerationPlanRecord,
    CurriculumPlanningAttemptRecord,
    CurriculumPlanRecord,
    GenerationRunRecord,
    LessonGenerationTaskRecord,
    LessonValidationDiagnosticRecord,
)
from .schemas import (
    ContentGenerationResult,
    ContentGenerationStatus,
    CurriculumPlanningAttempt,
    GeneratedLessonDraft,
    GenerationRun,
    GenerationRunStatus,
    LessonValidationDiagnostic,
    LessonValidationDiagnosticStatus,
)


class ContentGenerationRepository(Protocol):
    async def create_curriculum_plan(self, plan: CurriculumPlan) -> CurriculumPlan: ...

    async def get_curriculum_plan(self, plan_id: str) -> CurriculumPlan | None: ...

    async def update_curriculum_plan(self, plan: CurriculumPlan) -> CurriculumPlan: ...

    async def list_curriculum_plans(self, request_ref: str) -> list[CurriculumPlan]: ...

    async def create_curriculum_planning_attempt(
        self, attempt: CurriculumPlanningAttempt
    ) -> CurriculumPlanningAttempt: ...

    async def get_curriculum_planning_attempt(
        self, attempt_id: str
    ) -> CurriculumPlanningAttempt | None: ...

    async def list_curriculum_planning_attempts(
        self, request_ref: str
    ) -> list[CurriculumPlanningAttempt]: ...

    async def create_lesson_validation_diagnostic(
        self, diagnostic: LessonValidationDiagnostic
    ) -> LessonValidationDiagnostic: ...

    async def get_lesson_validation_diagnostic(
        self, diagnostic_id: str
    ) -> LessonValidationDiagnostic | None: ...

    async def list_lesson_validation_diagnostics(
        self, request_ref: str
    ) -> list[LessonValidationDiagnostic]: ...

    async def create_run(self, run: GenerationRun) -> GenerationRun: ...

    async def get_run(self, run_id: str) -> GenerationRun | None: ...

    async def update_run(self, run: GenerationRun) -> GenerationRun: ...

    async def create_plan(self, plan: CourseGenerationPlan) -> CourseGenerationPlan: ...

    async def get_plan(self, plan_id: str) -> CourseGenerationPlan | None: ...

    async def update_plan(self, plan: CourseGenerationPlan) -> CourseGenerationPlan: ...

    async def list_plans(self, request_ref: str) -> list[CourseGenerationPlan]: ...

    async def create_task(self, task: LessonGenerationTask) -> LessonGenerationTask: ...

    async def get_task(self, task_id: str) -> LessonGenerationTask | None: ...

    async def update_task(self, task: LessonGenerationTask) -> LessonGenerationTask: ...

    async def list_tasks(self, plan_ref: str) -> list[LessonGenerationTask]: ...

    async def get_active_run(self, request_ref: str) -> GenerationRun | None: ...

    async def create_result(self, result: ContentGenerationResult) -> ContentGenerationResult: ...

    async def get_result(self, result_id: str) -> ContentGenerationResult | None: ...

    async def get_latest_result(self, request_ref: str) -> ContentGenerationResult | None: ...

    async def list_results(self, request_ref: str) -> list[ContentGenerationResult]: ...

    async def update_result_status(
        self, result_id: str, status: ContentGenerationStatus
    ) -> ContentGenerationResult: ...

    async def update_result(self, result: ContentGenerationResult) -> ContentGenerationResult: ...


class InMemoryContentGenerationRepository:
    def __init__(self) -> None:
        self.runs: dict[str, GenerationRun] = {}
        self.results: dict[tuple[str, int], ContentGenerationResult] = {}
        self.plans: dict[str, CourseGenerationPlan] = {}
        self.tasks: dict[str, LessonGenerationTask] = {}
        self.curriculum_plans: dict[str, CurriculumPlan] = {}
        self.curriculum_planning_attempts: dict[str, CurriculumPlanningAttempt] = {}
        self.lesson_validation_diagnostics: dict[str, LessonValidationDiagnostic] = {}

    async def create_curriculum_plan(self, plan: CurriculumPlan) -> CurriculumPlan:
        if plan.id in self.curriculum_plans:
            raise ValueError("curriculum_plan_immutable")
        self.curriculum_plans[plan.id] = plan.model_copy(deep=True)
        return plan.model_copy(deep=True)

    async def get_curriculum_plan(self, plan_id: str) -> CurriculumPlan | None:
        plan = self.curriculum_plans.get(plan_id)
        return plan.model_copy(deep=True) if plan is not None else None

    async def update_curriculum_plan(self, plan: CurriculumPlan) -> CurriculumPlan:
        if plan.id not in self.curriculum_plans:
            raise KeyError(plan.id)
        self.curriculum_plans[plan.id] = plan.model_copy(deep=True)
        return plan.model_copy(deep=True)

    async def list_curriculum_plans(self, request_ref: str) -> list[CurriculumPlan]:
        return [
            plan.model_copy(deep=True)
            for plan in sorted(
                (item for item in self.curriculum_plans.values() if item.authoring_request_ref == request_ref),
                key=lambda item: item.version,
                reverse=True,
            )
        ]

    async def create_curriculum_planning_attempt(
        self, attempt: CurriculumPlanningAttempt
    ) -> CurriculumPlanningAttempt:
        if attempt.id in self.curriculum_planning_attempts:
            raise ValueError("curriculum_planning_attempt_immutable")
        self.curriculum_planning_attempts[attempt.id] = attempt.model_copy(deep=True)
        return attempt.model_copy(deep=True)

    async def get_curriculum_planning_attempt(
        self, attempt_id: str
    ) -> CurriculumPlanningAttempt | None:
        attempt = self.curriculum_planning_attempts.get(attempt_id)
        return attempt.model_copy(deep=True) if attempt is not None else None

    async def list_curriculum_planning_attempts(
        self, request_ref: str
    ) -> list[CurriculumPlanningAttempt]:
        return [
            attempt.model_copy(deep=True)
            for attempt in sorted(
                (
                    item
                    for item in self.curriculum_planning_attempts.values()
                    if item.authoring_request_ref == request_ref
                ),
                key=lambda item: item.created_at,
                reverse=True,
            )
        ]

    async def create_lesson_validation_diagnostic(
        self, diagnostic: LessonValidationDiagnostic
    ) -> LessonValidationDiagnostic:
        if diagnostic.id in self.lesson_validation_diagnostics:
            raise ValueError("lesson_validation_diagnostic_immutable")
        self.lesson_validation_diagnostics[diagnostic.id] = diagnostic.model_copy(deep=True)
        return diagnostic.model_copy(deep=True)

    async def get_lesson_validation_diagnostic(
        self, diagnostic_id: str
    ) -> LessonValidationDiagnostic | None:
        diagnostic = self.lesson_validation_diagnostics.get(diagnostic_id)
        return diagnostic.model_copy(deep=True) if diagnostic is not None else None

    async def list_lesson_validation_diagnostics(
        self, request_ref: str
    ) -> list[LessonValidationDiagnostic]:
        return [
            diagnostic.model_copy(deep=True)
            for diagnostic in sorted(
                (
                    item
                    for item in self.lesson_validation_diagnostics.values()
                    if item.authoring_request_ref == request_ref
                ),
                key=lambda item: item.created_at,
                reverse=True,
            )
        ]

    async def create_run(self, run: GenerationRun) -> GenerationRun:
        if run.parent_run_ref is None and await self.get_active_run(run.request_ref) is not None:
            raise ValueError("generation_already_in_progress")
        self.runs[run.run_id] = run.model_copy(deep=True)
        return run.model_copy(deep=True)

    async def get_run(self, run_id: str) -> GenerationRun | None:
        run = self.runs.get(run_id)
        return run.model_copy(deep=True) if run is not None else None

    async def update_run(self, run: GenerationRun) -> GenerationRun:
        if run.run_id not in self.runs:
            raise KeyError(run.run_id)
        self.runs[run.run_id] = run.model_copy(deep=True)
        return run.model_copy(deep=True)

    async def create_plan(self, plan: CourseGenerationPlan) -> CourseGenerationPlan:
        if plan.id in self.plans:
            raise ValueError("course_generation_plan_immutable")
        self.plans[plan.id] = plan.model_copy(deep=True)
        return plan.model_copy(deep=True)

    async def get_plan(self, plan_id: str) -> CourseGenerationPlan | None:
        plan = self.plans.get(plan_id)
        return plan.model_copy(deep=True) if plan is not None else None

    async def update_plan(self, plan: CourseGenerationPlan) -> CourseGenerationPlan:
        if plan.id not in self.plans:
            raise KeyError(plan.id)
        self.plans[plan.id] = plan.model_copy(deep=True)
        return plan.model_copy(deep=True)

    async def list_plans(self, request_ref: str) -> list[CourseGenerationPlan]:
        return [
            plan.model_copy(deep=True)
            for plan in sorted(
                (item for item in self.plans.values() if item.authoring_request_ref == request_ref),
                key=lambda item: item.created_at,
                reverse=True,
            )
        ]

    async def create_task(self, task: LessonGenerationTask) -> LessonGenerationTask:
        if task.id in self.tasks:
            raise ValueError("lesson_generation_task_immutable")
        self.tasks[task.id] = task.model_copy(deep=True)
        return task.model_copy(deep=True)

    async def get_task(self, task_id: str) -> LessonGenerationTask | None:
        task = self.tasks.get(task_id)
        return task.model_copy(deep=True) if task is not None else None

    async def update_task(self, task: LessonGenerationTask) -> LessonGenerationTask:
        if task.id not in self.tasks:
            raise KeyError(task.id)
        self.tasks[task.id] = task.model_copy(deep=True)
        return task.model_copy(deep=True)

    async def list_tasks(self, plan_ref: str) -> list[LessonGenerationTask]:
        return [
            task.model_copy(deep=True)
            for task in sorted(
                (item for item in self.tasks.values() if item.plan_ref == plan_ref),
                key=lambda item: (item.module_order, item.lesson_order),
            )
        ]

    async def get_active_run(self, request_ref: str) -> GenerationRun | None:
        for run in self.runs.values():
            if run.request_ref == request_ref and run.status is GenerationRunStatus.RUNNING:
                return run.model_copy(deep=True)
        return None

    async def create_result(self, result: ContentGenerationResult) -> ContentGenerationResult:
        key = (result.request_ref, result.version)
        if key in self.results:
            raise ValueError("content_generation_result_version_immutable")
        self.results[key] = result.model_copy(deep=True)
        return result.model_copy(deep=True)

    async def get_result(self, result_id: str) -> ContentGenerationResult | None:
        for result in self.results.values():
            if result.id == result_id:
                return result.model_copy(deep=True)
        return None

    async def get_latest_result(self, request_ref: str) -> ContentGenerationResult | None:
        candidates = [result for result in self.results.values() if result.request_ref == request_ref]
        if not candidates:
            return None
        return max(candidates, key=lambda result: result.version).model_copy(deep=True)

    async def list_results(self, request_ref: str) -> list[ContentGenerationResult]:
        return [
            result.model_copy(deep=True)
            for result in sorted(
                (item for item in self.results.values() if item.request_ref == request_ref),
                key=lambda item: item.version,
                reverse=True,
            )
        ]

    async def update_result_status(
        self, result_id: str, status: ContentGenerationStatus
    ) -> ContentGenerationResult:
        result = await self.get_result(result_id)
        if result is None:
            raise KeyError(result_id)
        updated = result.model_copy(update={"status": status})
        self.results[(updated.request_ref, updated.version)] = updated
        return updated.model_copy(deep=True)

    async def update_result(self, result: ContentGenerationResult) -> ContentGenerationResult:
        key = (result.request_ref, result.version)
        if key not in self.results:
            raise KeyError(result.id)
        self.results[key] = result.model_copy(deep=True)
        return result.model_copy(deep=True)


class SqlAlchemyContentGenerationRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_curriculum_plan(self, plan: CurriculumPlan) -> CurriculumPlan:
        async with self._session_factory() as session, session.begin():
            if await session.get(CurriculumPlanRecord, plan.id) is not None:
                raise ValueError("curriculum_plan_immutable")
            session.add(self._curriculum_plan_record(plan))
        return plan.model_copy(deep=True)

    async def get_curriculum_plan(self, plan_id: str) -> CurriculumPlan | None:
        async with self._session_factory() as session:
            record = await session.get(CurriculumPlanRecord, plan_id)
            return self._curriculum_plan_from_record(record) if record is not None else None

    async def update_curriculum_plan(self, plan: CurriculumPlan) -> CurriculumPlan:
        async with self._session_factory() as session, session.begin():
            record = await session.get(CurriculumPlanRecord, plan.id, with_for_update=True)
            if record is None:
                raise KeyError(plan.id)
            record.status = plan.status.value
            record.planning_metadata = dict(plan.planning_metadata)
        return plan.model_copy(deep=True)

    async def list_curriculum_plans(self, request_ref: str) -> list[CurriculumPlan]:
        async with self._session_factory() as session:
            records = list((await session.scalars(
                select(CurriculumPlanRecord)
                .where(CurriculumPlanRecord.authoring_request_ref == request_ref)
                .order_by(CurriculumPlanRecord.version.desc())
            )).all())
            return [self._curriculum_plan_from_record(record) for record in records]

    async def create_curriculum_planning_attempt(
        self, attempt: CurriculumPlanningAttempt
    ) -> CurriculumPlanningAttempt:
        async with self._session_factory() as session, session.begin():
            if await session.get(CurriculumPlanningAttemptRecord, attempt.id) is not None:
                raise ValueError("curriculum_planning_attempt_immutable")
            session.add(self._curriculum_planning_attempt_record(attempt))
        return attempt.model_copy(deep=True)

    async def get_curriculum_planning_attempt(
        self, attempt_id: str
    ) -> CurriculumPlanningAttempt | None:
        async with self._session_factory() as session:
            record = await session.get(CurriculumPlanningAttemptRecord, attempt_id)
            return (
                self._curriculum_planning_attempt_from_record(record)
                if record is not None
                else None
            )

    async def list_curriculum_planning_attempts(
        self, request_ref: str
    ) -> list[CurriculumPlanningAttempt]:
        async with self._session_factory() as session:
            records = list(
                (
                    await session.scalars(
                        select(CurriculumPlanningAttemptRecord)
                        .where(
                            CurriculumPlanningAttemptRecord.authoring_request_ref
                            == request_ref
                        )
                        .order_by(CurriculumPlanningAttemptRecord.created_at.desc())
                    )
                ).all()
            )
            return [self._curriculum_planning_attempt_from_record(record) for record in records]

    async def create_lesson_validation_diagnostic(
        self, diagnostic: LessonValidationDiagnostic
    ) -> LessonValidationDiagnostic:
        async with self._session_factory() as session, session.begin():
            if await session.get(LessonValidationDiagnosticRecord, diagnostic.id) is not None:
                raise ValueError("lesson_validation_diagnostic_immutable")
            session.add(self._lesson_validation_diagnostic_record(diagnostic))
        return diagnostic.model_copy(deep=True)

    async def get_lesson_validation_diagnostic(
        self, diagnostic_id: str
    ) -> LessonValidationDiagnostic | None:
        async with self._session_factory() as session:
            record = await session.get(LessonValidationDiagnosticRecord, diagnostic_id)
            return (
                self._lesson_validation_diagnostic_from_record(record)
                if record is not None
                else None
            )

    async def list_lesson_validation_diagnostics(
        self, request_ref: str
    ) -> list[LessonValidationDiagnostic]:
        async with self._session_factory() as session:
            records = list(
                (
                    await session.scalars(
                        select(LessonValidationDiagnosticRecord)
                        .where(
                            LessonValidationDiagnosticRecord.authoring_request_ref == request_ref
                        )
                        .order_by(LessonValidationDiagnosticRecord.created_at.desc())
                    )
                ).all()
            )
            return [self._lesson_validation_diagnostic_from_record(record) for record in records]

    async def create_run(self, run: GenerationRun) -> GenerationRun:
        async with self._session_factory() as session, session.begin():
            if run.parent_run_ref is None:
                active = await session.scalar(
                    select(GenerationRunRecord)
                    .where(
                        GenerationRunRecord.request_ref == run.request_ref,
                        GenerationRunRecord.parent_run_ref.is_(None),
                        GenerationRunRecord.status == GenerationRunStatus.RUNNING.value,
                    )
                    .with_for_update()
                )
            else:
                active = None
            if active is not None:
                raise ValueError("generation_already_in_progress")
            session.add(
                GenerationRunRecord(
                    run_id=run.run_id,
                    request_ref=run.request_ref,
                    parent_run_ref=run.parent_run_ref,
                    unit_type=run.unit_type,
                    unit_ref=run.unit_ref,
                    generation_mode=run.generation_mode,
                    repair_source_diagnostic_ref=run.repair_source_diagnostic_ref,
                    provider=run.provider or "unknown",
                    model=run.model or "unknown",
                    prompt_version=run.prompt_version or "unknown",
                    started_at=run.started_at,
                    finished_at=run.finished_at,
                    status=run.status.value,
                    error_code=run.error_code,
                )
            )
        return run.model_copy(deep=True)

    async def get_run(self, run_id: str) -> GenerationRun | None:
        async with self._session_factory() as session:
            record = await session.get(GenerationRunRecord, run_id)
            return self._run_from_record(record) if record is not None else None

    async def create_plan(self, plan: CourseGenerationPlan) -> CourseGenerationPlan:
        async with self._session_factory() as session, session.begin():
            if await session.get(CourseGenerationPlanRecord, plan.id) is not None:
                raise ValueError("course_generation_plan_immutable")
            session.add(self._plan_record(plan))
        return plan.model_copy(deep=True)

    async def get_plan(self, plan_id: str) -> CourseGenerationPlan | None:
        async with self._session_factory() as session:
            record = await session.get(CourseGenerationPlanRecord, plan_id)
            return self._plan_from_record(record) if record is not None else None

    async def update_plan(self, plan: CourseGenerationPlan) -> CourseGenerationPlan:
        async with self._session_factory() as session, session.begin():
            record = await session.get(CourseGenerationPlanRecord, plan.id, with_for_update=True)
            if record is None:
                raise KeyError(plan.id)
            record.status = plan.status.value
        return plan.model_copy(deep=True)

    async def list_plans(self, request_ref: str) -> list[CourseGenerationPlan]:
        async with self._session_factory() as session:
            records = list((await session.scalars(
                select(CourseGenerationPlanRecord)
                .where(CourseGenerationPlanRecord.authoring_request_ref == request_ref)
                .order_by(CourseGenerationPlanRecord.created_at.desc())
            )).all())
            return [self._plan_from_record(record) for record in records]

    async def create_task(self, task: LessonGenerationTask) -> LessonGenerationTask:
        async with self._session_factory() as session, session.begin():
            if await session.get(LessonGenerationTaskRecord, task.id) is not None:
                raise ValueError("lesson_generation_task_immutable")
            session.add(self._task_record(task))
        return task.model_copy(deep=True)

    async def get_task(self, task_id: str) -> LessonGenerationTask | None:
        async with self._session_factory() as session:
            record = await session.get(LessonGenerationTaskRecord, task_id)
            return self._task_from_record(record) if record is not None else None

    async def update_task(self, task: LessonGenerationTask) -> LessonGenerationTask:
        async with self._session_factory() as session, session.begin():
            record = await session.get(LessonGenerationTaskRecord, task.id, with_for_update=True)
            if record is None:
                raise KeyError(task.id)
            record.status = task.status.value
            record.attempt_count = task.attempt_count
            record.latest_run_ref = task.latest_run_ref
            record.generated_lesson = task.generated_lesson.model_dump(mode="json") if task.generated_lesson else None
            record.error_code = task.error_code
            record.updated_at = task.updated_at
        return task.model_copy(deep=True)

    async def list_tasks(self, plan_ref: str) -> list[LessonGenerationTask]:
        async with self._session_factory() as session:
            records = list((await session.scalars(
                select(LessonGenerationTaskRecord)
                .where(LessonGenerationTaskRecord.plan_ref == plan_ref)
                .order_by(LessonGenerationTaskRecord.module_order, LessonGenerationTaskRecord.lesson_order)
            )).all())
            return [self._task_from_record(record) for record in records]

    async def update_run(self, run: GenerationRun) -> GenerationRun:
        async with self._session_factory() as session, session.begin():
            record = await session.get(GenerationRunRecord, run.run_id, with_for_update=True)
            if record is None:
                raise KeyError(run.run_id)
            record.finished_at = run.finished_at
            record.status = run.status.value
            record.error_code = run.error_code
        return run.model_copy(deep=True)

    async def get_active_run(self, request_ref: str) -> GenerationRun | None:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(GenerationRunRecord)
                .where(
                    GenerationRunRecord.request_ref == request_ref,
                    GenerationRunRecord.parent_run_ref.is_(None),
                    GenerationRunRecord.status == GenerationRunStatus.RUNNING.value,
                )
                .order_by(desc(GenerationRunRecord.started_at))
            )
            return self._run_from_record(record) if record is not None else None

    async def create_result(self, result: ContentGenerationResult) -> ContentGenerationResult:
        async with self._session_factory() as session, session.begin():
            existing = await session.scalar(
                select(ContentGenerationResultRecord).where(
                    ContentGenerationResultRecord.request_ref == result.request_ref,
                    ContentGenerationResultRecord.version == result.version,
                )
            )
            if existing is not None:
                raise ValueError("content_generation_result_version_immutable")
            session.add(self._result_record(result))
        return result.model_copy(deep=True)

    async def get_result(self, result_id: str) -> ContentGenerationResult | None:
        async with self._session_factory() as session:
            record = await session.get(ContentGenerationResultRecord, result_id)
            return self._result_from_record(record) if record is not None else None

    async def get_latest_result(self, request_ref: str) -> ContentGenerationResult | None:
        async with self._session_factory() as session:
            record = await session.scalar(
                select(ContentGenerationResultRecord)
                .where(ContentGenerationResultRecord.request_ref == request_ref)
                .order_by(ContentGenerationResultRecord.version.desc())
                .limit(1)
            )
            return self._result_from_record(record) if record is not None else None

    async def list_results(self, request_ref: str) -> list[ContentGenerationResult]:
        async with self._session_factory() as session:
            records = list(
                (
                    await session.scalars(
                        select(ContentGenerationResultRecord)
                        .where(ContentGenerationResultRecord.request_ref == request_ref)
                        .order_by(ContentGenerationResultRecord.version.desc())
                    )
                ).all()
            )
            return [self._result_from_record(record) for record in records]

    async def update_result_status(
        self, result_id: str, status: ContentGenerationStatus
    ) -> ContentGenerationResult:
        async with self._session_factory() as session, session.begin():
            record = await session.get(ContentGenerationResultRecord, result_id, with_for_update=True)
            if record is None:
                raise KeyError(result_id)
            record.status = status.value
            result = self._result_from_record(record)
        return result

    async def update_result(self, result: ContentGenerationResult) -> ContentGenerationResult:
        async with self._session_factory() as session, session.begin():
            record = await session.get(ContentGenerationResultRecord, result.id, with_for_update=True)
            if record is None:
                raise KeyError(result.id)
            updated = self._result_record(result)
            record.status = updated.status
            record.revision_metadata = updated.revision_metadata
        return result

    @staticmethod
    def _run_from_record(record: GenerationRunRecord) -> GenerationRun:
        return GenerationRun(
            run_id=record.run_id,
            request_ref=record.request_ref,
            parent_run_ref=record.parent_run_ref,
            unit_type=record.unit_type,
            unit_ref=record.unit_ref,
            generation_mode=record.generation_mode,
            repair_source_diagnostic_ref=record.repair_source_diagnostic_ref,
            provider=record.provider,
            model=record.model,
            prompt_version=record.prompt_version,
            started_at=record.started_at,
            finished_at=record.finished_at,
            status=GenerationRunStatus(record.status),
            error_code=record.error_code,
        )

    @staticmethod
    def _plan_record(plan: CourseGenerationPlan) -> CourseGenerationPlanRecord:
        return CourseGenerationPlanRecord(
            id=plan.id,
            authoring_request_ref=plan.authoring_request_ref,
            parent_run_ref=plan.parent_run_ref,
            course_title=plan.course_title,
            course_description_context=plan.course_description_context,
            module_plans=[item.model_dump(mode="json") for item in plan.module_plans],
            lesson_descriptors=[item.model_dump(mode="json") for item in plan.lesson_descriptors],
            language=plan.language,
            duration_constraint=plan.duration_constraint,
            prompt_version=plan.prompt_version,
            quality_policy_version=plan.quality_policy_version,
            curriculum_plan_ref=plan.curriculum_plan_ref,
            status=plan.status.value,
            created_at=plan.created_at,
        )

    @staticmethod
    def _plan_from_record(record: CourseGenerationPlanRecord) -> CourseGenerationPlan:
        return CourseGenerationPlan.model_validate({
            "id": record.id,
            "authoring_request_ref": record.authoring_request_ref,
            "parent_run_ref": record.parent_run_ref,
            "course_title": record.course_title,
            "course_description_context": record.course_description_context,
            "module_plans": record.module_plans,
            "lesson_descriptors": record.lesson_descriptors,
            "language": record.language,
            "duration_constraint": record.duration_constraint,
            "prompt_version": record.prompt_version,
            "quality_policy_version": record.quality_policy_version,
            "curriculum_plan_ref": record.curriculum_plan_ref,
            "status": CourseGenerationPlanStatus(record.status),
            "created_at": record.created_at,
        })

    @staticmethod
    def _curriculum_plan_record(plan: CurriculumPlan) -> CurriculumPlanRecord:
        return CurriculumPlanRecord(
            id=plan.id,
            authoring_request_ref=plan.authoring_request_ref,
            version=plan.version,
            supersedes_plan_ref=plan.supersedes_plan_ref,
            course_title=plan.course_title,
            course_description=plan.course_description,
            normalized_duration=plan.normalized_duration.model_dump(mode="json"),
            learning_objectives=[item.model_dump(mode="json") for item in plan.learning_objectives],
            modules=[item.model_dump(mode="json") for item in plan.modules],
            estimated_total_learning_hours=plan.estimated_total_learning_hours,
            planning_metadata=dict(plan.planning_metadata),
            status=plan.status.value,
            created_at=datetime.now(UTC),
        )

    @staticmethod
    def _curriculum_plan_from_record(record: CurriculumPlanRecord) -> CurriculumPlan:
        return CurriculumPlan.model_validate({
            "id": record.id,
            "authoring_request_ref": record.authoring_request_ref,
            "version": record.version,
            "supersedes_plan_ref": record.supersedes_plan_ref,
            "course_title": record.course_title,
            "course_description": record.course_description,
            "normalized_duration": record.normalized_duration,
            "learning_objectives": record.learning_objectives,
            "modules": record.modules,
            "estimated_total_learning_hours": record.estimated_total_learning_hours,
            "planning_metadata": record.planning_metadata,
            "status": record.status,
        }, strict=False)

    @staticmethod
    def _curriculum_planning_attempt_record(
        attempt: CurriculumPlanningAttempt,
    ) -> CurriculumPlanningAttemptRecord:
        return CurriculumPlanningAttemptRecord(
            id=attempt.id,
            authoring_request_ref=attempt.authoring_request_ref,
            correlation_id=attempt.correlation_id,
            provider=attempt.provider,
            model=attempt.model,
            prompt_id=attempt.prompt_id,
            prompt_version=attempt.prompt_version,
            created_at=attempt.created_at,
            completed_at=attempt.completed_at,
            status=attempt.status.value,
            original_duration_constraint=attempt.original_duration_constraint,
            normalized_duration=attempt.normalized_duration.model_dump(mode="json"),
            weekly_effort_hours=attempt.weekly_effort_hours,
            weekly_effort_source=attempt.weekly_effort_source.value,
            estimated_total_learning_hours=attempt.estimated_total_learning_hours,
            min_modules=attempt.min_modules,
            max_modules=attempt.max_modules,
            min_lessons=attempt.min_lessons,
            max_lessons=attempt.max_lessons,
            objective_count=attempt.objective_count,
            module_count=attempt.module_count,
            lesson_count=attempt.lesson_count,
            estimated_candidate_hours=attempt.estimated_candidate_hours,
            covered_objective_count=attempt.covered_objective_count,
            validation_issues=[item.model_dump(mode="json") for item in attempt.validation_issues],
            uncovered_objective_refs=attempt.uncovered_objective_refs,
            unknown_objective_refs=attempt.unknown_objective_refs,
            sanitized_parsed_candidate=attempt.sanitized_parsed_candidate,
        )

    @staticmethod
    def _curriculum_planning_attempt_from_record(
        record: CurriculumPlanningAttemptRecord,
    ) -> CurriculumPlanningAttempt:
        return CurriculumPlanningAttempt.model_validate({
            "id": record.id,
            "authoring_request_ref": record.authoring_request_ref,
            "correlation_id": record.correlation_id,
            "provider": record.provider,
            "model": record.model,
            "prompt_id": record.prompt_id,
            "prompt_version": record.prompt_version,
            "created_at": record.created_at,
            "completed_at": record.completed_at,
            "status": record.status,
            "original_duration_constraint": record.original_duration_constraint,
            "normalized_duration": record.normalized_duration,
            "weekly_effort_hours": record.weekly_effort_hours,
            "weekly_effort_source": record.weekly_effort_source,
            "estimated_total_learning_hours": record.estimated_total_learning_hours,
            "min_modules": record.min_modules,
            "max_modules": record.max_modules,
            "min_lessons": record.min_lessons,
            "max_lessons": record.max_lessons,
            "objective_count": record.objective_count,
            "module_count": record.module_count,
            "lesson_count": record.lesson_count,
            "estimated_candidate_hours": record.estimated_candidate_hours,
            "covered_objective_count": record.covered_objective_count,
            "validation_issues": record.validation_issues,
            "uncovered_objective_refs": record.uncovered_objective_refs,
            "unknown_objective_refs": record.unknown_objective_refs,
            "sanitized_parsed_candidate": record.sanitized_parsed_candidate,
        }, strict=False)

    @staticmethod
    def _lesson_validation_diagnostic_record(
        diagnostic: LessonValidationDiagnostic,
    ) -> LessonValidationDiagnosticRecord:
        return LessonValidationDiagnosticRecord(
            id=diagnostic.id,
            authoring_request_ref=diagnostic.authoring_request_ref,
            plan_ref=diagnostic.plan_ref,
            task_ref=diagnostic.task_ref,
            lesson_ref=diagnostic.lesson_ref,
            attempt=diagnostic.attempt,
            generation_run_ref=diagnostic.generation_run_ref,
            provider=diagnostic.provider,
            model=diagnostic.model,
            prompt_version=diagnostic.prompt_version,
            created_at=diagnostic.created_at,
            status=diagnostic.status.value,
            sanitized_parsed_draft=diagnostic.sanitized_parsed_draft,
            validation_issues=[item.model_dump(mode="json") for item in diagnostic.validation_issues],
            section_metrics=[item.model_dump(mode="json") for item in diagnostic.section_metrics],
            assessment_summary=diagnostic.assessment_summary.model_dump(mode="json"),
        )

    @staticmethod
    def _lesson_validation_diagnostic_from_record(
        record: LessonValidationDiagnosticRecord,
    ) -> LessonValidationDiagnostic:
        return LessonValidationDiagnostic.model_validate(
            {
                "id": record.id,
                "authoring_request_ref": record.authoring_request_ref,
                "plan_ref": record.plan_ref,
                "task_ref": record.task_ref,
                "lesson_ref": record.lesson_ref,
                "attempt": record.attempt,
                "generation_run_ref": record.generation_run_ref,
                "provider": record.provider,
                "model": record.model,
                "prompt_version": record.prompt_version,
                "created_at": record.created_at,
                "status": LessonValidationDiagnosticStatus(record.status),
                "sanitized_parsed_draft": record.sanitized_parsed_draft,
                "validation_issues": record.validation_issues,
                "section_metrics": record.section_metrics,
                "assessment_summary": record.assessment_summary,
            },
            strict=False,
        )

    @staticmethod
    def _task_record(task: LessonGenerationTask) -> LessonGenerationTaskRecord:
        return LessonGenerationTaskRecord(
            id=task.id,
            plan_ref=task.plan_ref,
            lesson_ref=task.lesson_ref,
            module_order=task.module_order,
            lesson_order=task.lesson_order,
            lesson_title=task.lesson_title,
            objective_refs=list(task.objective_refs),
            status=task.status.value,
            attempt_count=task.attempt_count,
            latest_run_ref=task.latest_run_ref,
            generated_lesson=task.generated_lesson.model_dump(mode="json") if task.generated_lesson else None,
            error_code=task.error_code,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    @staticmethod
    def _task_from_record(record: LessonGenerationTaskRecord) -> LessonGenerationTask:
        generated_lesson = (
            GeneratedLessonDraft.model_validate_json(json.dumps(record.generated_lesson))
            if record.generated_lesson is not None
            else None
        )
        return LessonGenerationTask.model_validate({
            "id": record.id,
            "plan_ref": record.plan_ref,
            "lesson_ref": record.lesson_ref,
            "module_order": record.module_order,
            "lesson_order": record.lesson_order,
            "lesson_title": record.lesson_title,
            "objective_refs": record.objective_refs,
            "status": LessonGenerationTaskStatus(record.status),
            "attempt_count": record.attempt_count,
            "latest_run_ref": record.latest_run_ref,
            "generated_lesson": generated_lesson,
            "error_code": record.error_code,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        })

    @staticmethod
    def _result_record(result: ContentGenerationResult) -> ContentGenerationResultRecord:
        return ContentGenerationResultRecord(
            id=result.id,
            request_ref=result.request_ref,
            version=result.version,
            supersedes_result_ref=result.supersedes_result_ref,
            status=result.status.value,
            lesson_ref=result.lesson_ref,
            objective_refs=list(result.objective_refs),
            generated_objectives=[
                item.model_dump(mode="json") for item in result.generated_objectives
            ],
            learning_need_refs=list(result.learning_need_refs),
            sections=[section.model_dump(mode="json") for section in result.sections],
            generation_metadata=result.generation_metadata.model_dump(mode="json"),
            generation_run=result.generation_run.model_dump(mode="json") if result.generation_run else None,
            source_blueprint_ref=result.source_blueprint_ref,
            course_authoring_request_ref=result.course_authoring_request_ref,
            generated_course=result.generated_course.model_dump(mode="json") if result.generated_course else None,
            revision_metadata=(
                result.revision_metadata.model_dump(mode="json")
                if result.revision_metadata
                else None
            ),
            created_at=result.created_at or result.generation_metadata.created_at,
        )

    @staticmethod
    def _result_from_record(record: ContentGenerationResultRecord) -> ContentGenerationResult:
        return ContentGenerationResult.model_validate_json(json.dumps({
            "id": record.id,
            "request_ref": record.request_ref,
            "lesson_ref": record.lesson_ref,
            "objective_refs": list(record.objective_refs),
            "generated_objectives": record.generated_objectives or [],
            "learning_need_refs": list(record.learning_need_refs),
            "version": record.version,
            "supersedes_result_ref": record.supersedes_result_ref,
            "status": record.status,
            "sections": record.sections,
            "generation_metadata": record.generation_metadata,
            "generation_run": record.generation_run,
            "source_blueprint_ref": record.source_blueprint_ref,
            "course_authoring_request_ref": record.course_authoring_request_ref,
            "generated_course": record.generated_course,
            "revision_metadata": record.revision_metadata,
            "created_at": record.created_at,
        }, default=lambda value: value.isoformat() if isinstance(value, datetime) else str(value)))
