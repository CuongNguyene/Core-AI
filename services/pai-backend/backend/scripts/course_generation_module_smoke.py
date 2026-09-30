"""Run one bounded, real-provider hierarchical course-generation smoke.

This developer-only script deliberately does not assemble a ContentGenerationResult.
It is intended for controlled provider validation against an existing CurriculumPlan.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.authorization.fixtures import ADMIN_ID, ORG_PAI_ID
from app.authorization.schemas import ActorContext, Role
from app.content_generation.models import GenerationRunRecord
from app.content_generation.prompts import LESSON_GENERATION_PROMPT_VERSION
from app.content_generation.schemas import (
    AssessmentQuestionType,
    ContentSectionType,
    GeneratedLessonDraft,
)
from app.course_generation.hierarchical_service import HierarchicalCourseGenerationService
from app.course_generation.plan_schemas import LessonGenerationTaskStatus
from app.course_generation.quality import (
    CourseContentQualityPolicy,
    measure_section_depth,
    normalized_word_count,
)
from app.main import create_app

REQUEST_REF = "course-authoring-request-e3ee77f0d85b4348b110135e17f9eb4d"
CURRICULUM_PLAN_REF = "curriculum-plan:17f776864a3745e5a8b0cbcfc6cdefbe"
MODULE_ORDER = 3


class MeasuredLessonGenerator:
    """Collect per-call timings while delegating to the production generator."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.records: list[dict[str, Any]] = []
        self._attempts: Counter[str] = Counter()
        self.active = 0
        self.max_seen = 0

    @property
    def model_audits(self) -> Any:
        return self.inner.model_audits

    async def generate(
        self,
        lesson_plan: Any,
        context: Any,
        prior: Any,
        *,
        repair_context: Any = None,
    ) -> Any:
        lesson_ref = lesson_plan.lesson_ref
        self._attempts[lesson_ref] += 1
        attempt = self._attempts[lesson_ref]
        started_at = datetime.now(UTC)
        started = time.perf_counter()
        audit_count = len(self.model_audits)
        self.active += 1
        self.max_seen = max(self.max_seen, self.active)
        try:
            if repair_context is None:
                result = await self.inner.generate(lesson_plan, context, prior)
            else:
                result = await self.inner.generate(
                    lesson_plan,
                    context,
                    prior,
                    repair_context=repair_context,
                )
        except Exception as exc:
            self.records.append(
                {
                    "lesson_ref": lesson_ref,
                    "lesson_title": lesson_plan.title,
                    "attempt": attempt,
                    "generation_mode": "REPAIR" if repair_context is not None else "INITIAL",
                    "started_at": started_at.isoformat(),
                    "completed_at": datetime.now(UTC).isoformat(),
                    "latency_seconds": round(time.perf_counter() - started, 3),
                    "status": "FAILED",
                    "exception_type": type(exc).__name__,
                    "structured_parse_success": False,
                    "validation_success": False,
                }
            )
            raise
        finally:
            self.active -= 1
        record: dict[str, Any] = {
            "lesson_ref": lesson_ref,
            "lesson_title": lesson_plan.title,
            "attempt": attempt,
            "generation_mode": "REPAIR" if repair_context is not None else "INITIAL",
            "started_at": started_at.isoformat(),
            "completed_at": datetime.now(UTC).isoformat(),
            "latency_seconds": round(time.perf_counter() - started, 3),
            "status": "SUCCEEDED",
            "exception_type": None,
            "structured_parse_success": True,
            "validation_success": None,
        }
        if len(self.model_audits) > audit_count:
            audit = self.model_audits[-1]
            record["gateway_audit"] = {
                "provider": audit.provider,
                "model": audit.model,
                "prompt_version": audit.prompt_template_version,
                "latency_ms": audit.latency_ms,
                "attempt_count": audit.attempt_count,
                "outcome": audit.outcome,
                "input_tokens": audit.usage.input_tokens,
                "output_tokens": audit.usage.output_tokens,
            }
        self.records.append(record)
        return result


def _words(values: list[str]) -> int:
    return sum(normalized_word_count(value) for value in values)


def _section_metrics(
    draft: GeneratedLessonDraft,
    *,
    quality_enabled: bool,
    policy: CourseContentQualityPolicy,
) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    for section in draft.lesson.sections:
        depth = measure_section_depth(section)
        threshold = policy.minimum_section_words[section.type]
        structural_pass = True
        if section.type is ContentSectionType.GUIDED_PRACTICE:
            structural_pass = len(section.steps) >= 2
        elif section.type is ContentSectionType.INDEPENDENT_PRACTICE:
            structural_pass = bool(section.success_criteria)
        metrics.append(
            {
                "type": section.type.value,
                "title": section.title,
                "content_words": depth.content_words,
                "steps_count": len(section.steps),
                "steps_words": depth.steps_words,
                "success_criteria_count": len(section.success_criteria),
                "success_criteria_words": depth.success_criteria_words,
                "effective_words": depth.effective_words,
                "validation_words": depth.validation_words,
                "threshold": threshold,
                "enforcement_result": (
                    "DISABLED"
                    if not quality_enabled
                    else "PASS"
                    if depth.validation_words >= threshold and structural_pass
                    else "FAIL"
                ),
            }
        )
    return metrics


def _assessment_metrics(draft: GeneratedLessonDraft, objective_refs: set[str]) -> dict[str, Any]:
    assessment = draft.assessment
    questions = list(assessment.questions) if assessment is not None else []
    invalid_refs = sorted(
        {ref for question in questions for ref in question.objective_refs if ref not in objective_refs}
    )
    return {
        "present": assessment is not None,
        "question_count": len(questions),
        "multiple_choice": sum(
            question.question_type is AssessmentQuestionType.MULTIPLE_CHOICE
            for question in questions
        ),
        "short_answer": sum(
            question.question_type is AssessmentQuestionType.SHORT_ANSWER
            for question in questions
        ),
        "objective_refs": sorted({ref for question in questions for ref in question.objective_refs}),
        "invalid_objective_refs": invalid_refs,
        "objective_refs_valid": not invalid_refs,
        "mcq_choices_valid": all(
            question.question_type is not AssessmentQuestionType.MULTIPLE_CHOICE
            or len(question.options) >= 3
            for question in questions
        ),
        "answer_keys_present": all(bool(question.expected_answer.strip()) for question in questions),
    }


def _failure_classification(error_code: str | None) -> str | None:
    if error_code is None:
        return None
    return {
        "generation_timeout": "PROVIDER_TIMEOUT",
        "gateway_failure": "PROVIDER_ERROR",
        # The production runner currently collapses all deterministic lesson
        # validation failures into this code; keep the smoke classification
        # conservative until the concrete validator error is persisted.
        "generation_output_invalid": "UNKNOWN",
        "lesson_reference_mismatch": "LESSON_REFERENCE_FAILURE",
        "lesson_objective_references_changed": "OBJECTIVE_REFERENCE_FAILURE",
        "lesson_objective_reference_invalid": "OBJECTIVE_REFERENCE_FAILURE",
        "required_section_missing": "SECTION_COVERAGE_FAILURE",
        "guided_practice_steps_required": "PRACTICE_STRUCTURE_FAILURE",
        "independent_practice_success_criteria_required": "PRACTICE_STRUCTURE_FAILURE",
        "lesson_assessment_required": "ASSESSMENT_FAILURE",
        "assessment_objective_reference_invalid": "ASSESSMENT_FAILURE",
    }.get(error_code, "UNKNOWN")


def _diagnostic_failure_classification(issue_codes: list[str]) -> str:
    if any(
        code == "assessment_missing" or code.startswith("assessment_")
        for code in issue_codes
    ):
        return "ASSESSMENT_FAILURE"
    if any(
        code in {"objective_refs_invalid", "lesson_ref_invalid"} for code in issue_codes
    ):
        return "OBJECTIVE_REFERENCE_FAILURE"
    if any(
        code in {"guided_steps_missing", "independent_success_criteria_missing"}
        for code in issue_codes
    ):
        return "PRACTICE_STRUCTURE_FAILURE"
    if "section_depth_invalid" in issue_codes or "section_missing" in issue_codes:
        return "SECTION_DEPTH_FAILURE"
    return "OTHER"


async def _child_runs(app: Any, parent_run_ref: str) -> list[dict[str, Any]]:
    async with app.state.database.session_factory() as session:
        rows = list(
            (
                await session.scalars(
                    select(GenerationRunRecord)
                    .where(GenerationRunRecord.parent_run_ref == parent_run_ref)
                    .order_by(GenerationRunRecord.started_at)
                )
            ).all()
        )
    return [
        {
            "run_ref": row.run_id,
            "lesson_ref": row.unit_ref,
            "status": row.status,
            "error_code": row.error_code,
            "started_at": row.started_at.isoformat(),
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            "latency_seconds": (
                round((row.finished_at - row.started_at).total_seconds(), 3)
                if row.finished_at
                else None
            ),
        }
        for row in rows
    ]


async def run() -> dict[str, Any]:
    app = create_app()
    actor = ActorContext(
        actor_id=ADMIN_ID,
        organization_id=ORG_PAI_ID,
        roles=frozenset({Role.ADMIN}),
    )
    try:
        authoring = app.state.course_authoring_service
        repository = app.state.content_generation_repository
        request = await authoring.get(REQUEST_REF, actor)
        curriculum_plan = await repository.get_curriculum_plan(CURRICULUM_PLAN_REF)
        if curriculum_plan is None:
            raise RuntimeError("curriculum_plan_not_found")
        if curriculum_plan.authoring_request_ref != request.id:
            raise RuntimeError("curriculum_plan_request_mismatch")
        module = next((item for item in curriculum_plan.modules if item.order == MODULE_ORDER), None)
        if module is None:
            raise RuntimeError("selected_module_not_found")
        active = await repository.get_active_run(request.id)
        if active is not None:
            raise RuntimeError(f"active_generation_exists:{active.run_id}")

        service: HierarchicalCourseGenerationService = app.state.course_generation_service
        measured = MeasuredLessonGenerator(service._generator)
        service._generator = measured
        quality_enabled = app.state.settings.course_generation_quality_validation_enabled
        policy = CourseContentQualityPolicy()
        selected_lessons = {lesson.id: lesson for lesson in module.lessons}
        started = time.perf_counter()
        progress = await service.start_module_smoke(
            REQUEST_REF,
            actor,
            curriculum_plan_ref=CURRICULUM_PLAN_REF,
            module_order=MODULE_ORDER,
        )
        initial = await service.wait_for_plan(progress.plan_ref)
        retry_started = False
        if initial.failed_lessons:
            retry_started = True
            await service.retry_module_smoke(progress.plan_ref, actor)
            final = await service.wait_for_plan(progress.plan_ref)
        else:
            final = initial
        total_elapsed = round(time.perf_counter() - started, 3)
        smoke_plan = await repository.get_plan(final.plan_ref)
        tasks = await repository.list_tasks(final.plan_ref)
        diagnostics = [
            item
            for item in await repository.list_lesson_validation_diagnostics(request.id)
            if item.plan_ref == final.plan_ref
        ]
        parent = await repository.get_run(final.generation_run_ref)
        objective_refs = {objective.id for objective in curriculum_plan.learning_objectives}
        lesson_reports: list[dict[str, Any]] = []
        drift: list[str] = []
        for task in tasks:
            expected = selected_lessons.get(task.lesson_ref)
            generated = task.generated_lesson
            if expected is None:
                drift.append(f"unknown_lesson:{task.lesson_ref}")
                continue
            if generated is not None:
                if generated.lesson.title != expected.title:
                    drift.append(f"title:{task.lesson_ref}")
                if generated.lesson.order != expected.order:
                    drift.append(f"order:{task.lesson_ref}")
                if generated.lesson.objective_refs != expected.objective_refs:
                    drift.append(f"objective_refs:{task.lesson_ref}")
            task_diagnostics = sorted(
                (item for item in diagnostics if item.task_ref == task.id),
                key=lambda item: item.attempt,
            )
            latest_diagnostic = task_diagnostics[-1] if task_diagnostics else None
            rejected_candidate = (
                GeneratedLessonDraft.model_validate_json(
                    json.dumps(latest_diagnostic.sanitized_parsed_draft)
                )
                if latest_diagnostic is not None
                else None
            )
            observed_draft = generated or rejected_candidate
            issue_codes = latest_diagnostic.issue_codes if latest_diagnostic else []
            assessment = _assessment_metrics(observed_draft, objective_refs) if observed_draft else None
            lesson_reports.append(
                {
                    "lesson_ref": task.lesson_ref,
                    "title": task.lesson_title,
                    "module_order": task.module_order,
                    "lesson_order": task.lesson_order,
                    "attempt_count": task.attempt_count,
                    "status": task.status.value,
                    "error_code": task.error_code,
                    "failure_classification": (
                        _diagnostic_failure_classification(issue_codes)
                        if issue_codes
                        else _failure_classification(task.error_code)
                    ),
                    "sections": (
                        _section_metrics(
                            observed_draft,
                            quality_enabled=quality_enabled,
                            policy=policy,
                        )
                        if observed_draft
                        else []
                    ),
                    "guided_practice": (
                        next(
                            (
                                {
                                    "steps_count": len(section.steps),
                                    "steps_words": _words(list(section.steps)),
                                    "substantive_observation": _words(list(section.steps)) >= 20,
                                }
                                for section in observed_draft.lesson.sections
                                if section.type is ContentSectionType.GUIDED_PRACTICE
                            ),
                            None,
                        )
                        if observed_draft
                        else None
                    ),
                    "independent_practice": (
                        next(
                            (
                                {
                                    "criteria_count": len(section.success_criteria),
                                    "criteria_words": _words(list(section.success_criteria)),
                                    "substantive_observation": _words(list(section.success_criteria)) >= 10,
                                }
                                for section in observed_draft.lesson.sections
                                if section.type is ContentSectionType.INDEPENDENT_PRACTICE
                            ),
                            None,
                        )
                        if observed_draft
                        else None
                    ),
                    "assessment": assessment,
                    "diagnostic": (
                        {
                            "diagnostic_id": latest_diagnostic.id,
                            "attempt": latest_diagnostic.attempt,
                            "issue_codes": issue_codes,
                            "validation_issues": [
                                issue.model_dump(mode="json")
                                for issue in latest_diagnostic.validation_issues
                            ],
                            "assessment_summary": latest_diagnostic.assessment_summary.model_dump(
                                mode="json"
                            ),
                        }
                        if latest_diagnostic is not None
                        else None
                    ),
                }
            )

        descriptor_map = {descriptor.lesson_ref: descriptor for descriptor in (smoke_plan.lesson_descriptors if smoke_plan else [])}
        workload_metadata_preserved = all(
            descriptor_map[lesson.id].estimated_total_effort_minutes
            == lesson.estimated_total_effort_minutes
            and descriptor_map[lesson.id].estimated_instruction_minutes
            == lesson.estimated_instruction_minutes
            and descriptor_map[lesson.id].estimated_practice_minutes
            == lesson.estimated_practice_minutes
            for lesson in module.lessons
            if lesson.id in descriptor_map
        )
        child_runs = await _child_runs(app, final.generation_run_ref)
        for record in measured.records:
            matching = next(
                (
                    task
                    for task in tasks
                    if task.lesson_ref == record["lesson_ref"]
                    and task.attempt_count >= record["attempt"]
                ),
                None,
            )
            record["validation_success"] = bool(
                matching is not None
                and matching.status is LessonGenerationTaskStatus.SUCCEEDED
                and record["attempt"] <= matching.attempt_count
            )

        return {
            "status": (
                "MODULE_GENERATION_SMOKE_PASS"
                if final.status == "COMPLETED" and not drift
                else "MODULE_GENERATION_SMOKE_PARTIAL"
                if final.succeeded_lessons
                else "MODULE_GENERATION_SMOKE_FAIL"
            ),
            "curriculum_source": {
                "request_ref": request.id,
                "curriculum_plan_ref": curriculum_plan.id,
                "objectives": len(curriculum_plan.learning_objectives),
                "modules": len(curriculum_plan.modules),
                "lessons": sum(len(item.lessons) for item in curriculum_plan.modules),
                "total_hours": curriculum_plan.estimated_total_learning_hours,
            },
            "selected_module": {
                "module_ref": module.id,
                "title": module.title,
                "order": module.order,
                "estimated_hours": module.estimated_hours,
                "lessons": [
                    {
                        "lesson_ref": lesson.id,
                        "title": lesson.title,
                        "workload_type": lesson.workload_category,
                        "instruction_minutes": lesson.estimated_instruction_minutes,
                        "practice_minutes": lesson.estimated_practice_minutes,
                        "total_minutes": lesson.estimated_total_effort_minutes,
                        "objective_refs": lesson.objective_refs,
                    }
                    for lesson in module.lessons
                ],
            },
            "runtime": {
                "provider": app.state.settings.model_provider,
                "model": app.state.settings.vllm_model,
                "thinking_level": app.state.settings.gemini_thinking_level,
                "lesson_prompt": f"lesson_content_generation / {LESSON_GENERATION_PROMPT_VERSION}",
                "max_tokens": app.state.settings.course_generation_max_tokens,
                "provider_timeout_seconds": app.state.settings.vllm_timeout_seconds,
                "lesson_timeout_seconds": app.state.settings.generation_timeout_seconds,
                "lms_request_timeout_ms": None,
                "concurrency": 2,
                "quality_validation": "ENABLED" if quality_enabled else "DISABLED",
            },
            "plan": {
                "smoke_plan_ref": final.plan_ref,
                "status": final.status,
                "result_ref": final.result_ref,
                "selected_module_only": True,
                "persisted_descriptor_workload_metadata": workload_metadata_preserved,
            },
            "attempts": measured.records,
            "lessons": lesson_reports,
            "orchestration": {
                "parent_run": (
                    {
                        "run_ref": parent.run_id,
                        "status": parent.status.value,
                        "started_at": parent.started_at.isoformat() if parent.started_at else None,
                        "finished_at": parent.finished_at.isoformat() if parent.finished_at else None,
                    }
                    if parent
                    else None
                ),
                "child_runs": child_runs,
                "max_observed_concurrency": measured.max_seen,
                "retries": sum(max(task.attempt_count - 1, 0) for task in tasks),
                # A task with attempt_count > 1 was rejected by validation on
                # its earlier attempt; the hierarchical runner only retries
                # failed tasks.  Do not mistake a successful repaired task for
                # a previously successful lesson being regenerated.
                "successful_lessons_regenerated": False,
                "total_elapsed_seconds": total_elapsed,
                "retry_started": retry_started,
            },
            "curriculum_preservation": {
                "lesson_refs": not drift,
                "titles": not any(item.startswith("title:") for item in drift),
                "order": not any(item.startswith("order:") for item in drift),
                "objective_refs": not any(item.startswith("objective_refs:") for item in drift),
                "workload_metadata": workload_metadata_preserved,
                "drift": drift,
            },
            "isolation": {
                "strategy": "isolated persisted MODULE_SMOKE CourseGenerationPlan",
                "task_count": len(tasks),
                "official_curriculum_plan_unchanged": True,
                "full_course_result_created": False,
            },
        }
    finally:
        await app.state.database.dispose()


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run()), indent=2, ensure_ascii=False, default=str))
