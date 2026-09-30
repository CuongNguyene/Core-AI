import re
from collections import Counter

from app.content_generation.schemas import CurriculumPlanningAttempt

from .duration import NormalizedTrainingDuration
from .microlearning import (
    EFFORT_TOLERANCE_PERCENT,
    MICROLEARNING_EFFORT_RANGES,
    MICROLEARNING_POLICY_VERSION,
    effort_fit,
    parse_expected_learning_effort_hours,
)
from .policy import CurriculumScopePolicy
from .schemas import CurriculumPlan, CurriculumPlanValidationIssue, CurriculumPlanValidationReport
from .workload import UnsupportedLessonTypeError, workload_profile_for


class CurriculumPlanValidationError(ValueError):
    def __init__(self, message: str, *, report: CurriculumPlanValidationReport) -> None:
        super().__init__(message)
        self.report = report


def collect_curriculum_plan_validation(
    plan: CurriculumPlan,
    *,
    policy: CurriculumScopePolicy | None = None,
) -> CurriculumPlanValidationReport:
    issues: list[CurriculumPlanValidationIssue] = []

    def add(
        code: str,
        message: str,
        path: str,
        *,
        actual: object = None,
        expected: object = None,
        objective_ref: str | None = None,
        module_ref: str | None = None,
        lesson_ref: str | None = None,
    ) -> None:
        issues.append(
            CurriculumPlanValidationIssue(
                code=code,
                message=message,
                path=path,
                actual=actual,
                expected=expected,
                objective_ref=objective_ref,
                module_ref=module_ref,
                lesson_ref=lesson_ref,
            )
        )

    objective_ids = [objective.id for objective in plan.learning_objectives]
    duplicate_objective_ids = [
        item for item, count in Counter(objective_ids).items() if count > 1
    ]
    for objective_id in duplicate_objective_ids:
        add(
            "duplicate_objective_id",
            "Objective IDs must be unique.",
            "learning_objectives",
            actual=objective_id,
            expected="unique",
            objective_ref=objective_id,
        )

    normalized_statements: dict[str, str] = {}
    for index, objective in enumerate(plan.learning_objectives):
        normalized = re.sub(r"\s+", " ", objective.statement.strip().lower())
        if not objective.statement.strip():
            add("invalid_title", "Objective statement must not be empty.", f"learning_objectives[{index}].statement")
        if not objective.measurable_outcome.strip():
            add(
                "invalid_measurable_outcome",
                "Objective measurable outcome must not be empty.",
                f"learning_objectives[{index}].measurable_outcome",
                objective_ref=objective.id,
            )
        if normalized in normalized_statements:
            add(
                "duplicate_objective_statement",
                "Objective statements must be distinct.",
                f"learning_objectives[{index}].statement",
                actual=objective.statement,
                expected="unique normalized statement",
                objective_ref=objective.id,
            )
        else:
            normalized_statements[normalized] = objective.id

    expected_objective_sequence = list(range(1, len(plan.learning_objectives) + 1))
    actual_objective_sequence = [objective.sequence for objective in plan.learning_objectives]
    if actual_objective_sequence != expected_objective_sequence:
        add(
            "invalid_sequence",
            "Objective sequences must be contiguous and ordered.",
            "learning_objectives.sequence",
            actual=actual_objective_sequence,
            expected=expected_objective_sequence,
        )

    module_ids = [module.id for module in plan.modules]
    for module_id, count in Counter(module_ids).items():
        if count > 1:
            add(
                "duplicate_module_id",
                "Module IDs must be unique.",
                "modules",
                actual=module_id,
                expected="unique",
                module_ref=module_id,
            )
    module_orders = [module.order for module in plan.modules]
    for order, count in Counter(module_orders).items():
        if count > 1:
            add(
                "duplicate_module_order",
                "Module orders must be unique.",
                "modules.order",
                actual=order,
                expected="unique",
            )
    if module_orders != list(range(1, len(module_orders) + 1)):
        add(
            "invalid_sequence",
            "Module orders must be contiguous and ordered.",
            "modules.order",
            actual=module_orders,
            expected=list(range(1, len(module_orders) + 1)),
        )

    lesson_ids: list[str] = []
    covered: set[str] = set()
    unknown_refs: set[str] = set()
    objective_id_set = set(objective_ids)
    for module_index, module in enumerate(plan.modules):
        if not module.title.strip():
            add("invalid_title", "Module title must not be empty.", f"modules[{module_index}].title", module_ref=module.id)
        for reference in module.objective_refs:
            if reference not in objective_id_set:
                unknown_refs.add(reference)
                add(
                    "unknown_objective_ref",
                    "Module references an unknown objective.",
                    f"modules[{module_index}].objective_refs",
                    actual=reference,
                    expected=objective_ids,
                    objective_ref=reference,
                    module_ref=module.id,
                )
        if module.estimated_hours <= 0:
            add(
                "invalid_module_duration",
                "Module duration must be positive.",
                f"modules[{module_index}].estimated_hours",
                actual=module.estimated_hours,
                expected="> 0",
                module_ref=module.id,
            )

        lesson_orders = [lesson.order for lesson in module.lessons]
        for order, count in Counter(lesson_orders).items():
            if count > 1:
                add(
                    "duplicate_lesson_order",
                    "Lesson orders must be unique within a module.",
                    f"modules[{module_index}].lessons.order",
                    actual=order,
                    expected="unique",
                    module_ref=module.id,
                )
        if lesson_orders != list(range(1, len(lesson_orders) + 1)):
            add(
                "invalid_sequence",
                "Lesson orders must be contiguous and ordered within a module.",
                f"modules[{module_index}].lessons.order",
                actual=lesson_orders,
                expected=list(range(1, len(lesson_orders) + 1)),
                module_ref=module.id,
            )
        lesson_hours = 0.0
        for lesson_index, lesson in enumerate(module.lessons):
            lesson_ids.append(lesson.id)
            try:
                profile = workload_profile_for(lesson.lesson_type)
            except UnsupportedLessonTypeError:
                profile = None
                add(
                    "unsupported_lesson_type",
                    "Lesson type is not supported by the workload policy.",
                    f"modules[{module_index}].lessons[{lesson_index}].lesson_type",
                    actual=lesson.lesson_type,
                    expected="supported workload lesson type",
                    module_ref=module.id,
                    lesson_ref=lesson.id,
                )
            if profile is not None and lesson.workload_category is not None and lesson.workload_category != profile.category:
                add(
                    "invalid_workload_category",
                    "Workload category does not match the lesson type.",
                    f"modules[{module_index}].lessons[{lesson_index}].workload_category",
                    actual=lesson.workload_category.value,
                    expected=profile.category.value,
                    module_ref=module.id,
                    lesson_ref=lesson.id,
                )
            if not lesson.title.strip():
                add(
                    "invalid_title",
                    "Lesson title must not be empty.",
                    f"modules[{module_index}].lessons[{lesson_index}].title",
                    module_ref=module.id,
                    lesson_ref=lesson.id,
                )
            if lesson.estimated_minutes <= 0:
                add(
                    "invalid_lesson_duration",
                    "Lesson duration must be positive.",
                    f"modules[{module_index}].lessons[{lesson_index}].estimated_minutes",
                    actual=lesson.estimated_minutes,
                    expected="> 0",
                    module_ref=module.id,
                    lesson_ref=lesson.id,
                )
            if not lesson.objective_refs:
                add(
                    "lesson_without_objective_ref",
                    "Every lesson must reference an objective.",
                    f"modules[{module_index}].lessons[{lesson_index}].objective_refs",
                    expected="at least one objective",
                    module_ref=module.id,
                    lesson_ref=lesson.id,
                )
            for reference in lesson.objective_refs:
                if reference not in objective_id_set:
                    unknown_refs.add(reference)
                    add(
                        "unknown_objective_ref",
                        "Lesson references an unknown objective.",
                        f"modules[{module_index}].lessons[{lesson_index}].objective_refs",
                        actual=reference,
                        expected=objective_ids,
                        objective_ref=reference,
                        module_ref=module.id,
                        lesson_ref=lesson.id,
                    )
                else:
                    covered.add(reference)
            if any(
                value is not None
                for value in (
                    lesson.estimated_instruction_minutes,
                    lesson.estimated_practice_minutes,
                    lesson.estimated_total_effort_minutes,
                )
            ):
                if lesson.estimated_total_effort_minutes is None:
                    add(
                        "invalid_total_effort_duration",
                        "Workload fields require a total effort duration.",
                        f"modules[{module_index}].lessons[{lesson_index}].estimated_total_effort_minutes",
                        expected="> 0",
                        module_ref=module.id,
                        lesson_ref=lesson.id,
                    )
                if lesson.estimated_instruction_minutes is None:
                    add(
                        "invalid_instruction_duration",
                        "Workload fields require instruction minutes.",
                        f"modules[{module_index}].lessons[{lesson_index}].estimated_instruction_minutes",
                        expected=">= 0",
                        module_ref=module.id,
                        lesson_ref=lesson.id,
                    )
                if lesson.estimated_practice_minutes is None:
                    add(
                        "invalid_practice_duration",
                        "Workload fields require practice minutes.",
                        f"modules[{module_index}].lessons[{lesson_index}].estimated_practice_minutes",
                        expected=">= 0",
                        module_ref=module.id,
                        lesson_ref=lesson.id,
                    )
                if (
                    lesson.estimated_instruction_minutes is not None
                    and lesson.estimated_practice_minutes is not None
                    and lesson.estimated_total_effort_minutes is not None
                    and lesson.estimated_instruction_minutes + lesson.estimated_practice_minutes
                    != lesson.estimated_total_effort_minutes
                ):
                    add(
                        "duration_split_incoherent",
                        "Instruction and practice minutes must sum to total effort.",
                        f"modules[{module_index}].lessons[{lesson_index}]",
                        actual=(
                            lesson.estimated_instruction_minutes,
                            lesson.estimated_practice_minutes,
                            lesson.estimated_total_effort_minutes,
                        ),
                        expected="instruction + practice = total effort",
                        module_ref=module.id,
                        lesson_ref=lesson.id,
                    )
                if (
                    lesson.estimated_total_effort_minutes is not None
                    and lesson.estimated_total_effort_minutes != lesson.estimated_minutes
                ):
                    add(
                        "duration_split_incoherent",
                        "Legacy estimated_minutes must equal total effort minutes.",
                        f"modules[{module_index}].lessons[{lesson_index}].estimated_minutes",
                        actual=lesson.estimated_minutes,
                        expected=lesson.estimated_total_effort_minutes,
                        module_ref=module.id,
                        lesson_ref=lesson.id,
                    )
            lesson_hours += (
                (lesson.estimated_total_effort_minutes or lesson.estimated_minutes) / 60
            )
            if plan.planning_metadata.get("planning_strategy") == MICROLEARNING_POLICY_VERSION:
                category = lesson.workload_category or (
                    profile.category if profile is not None else None
                )
                if category is not None and lesson.estimated_minutes > 0:
                    effort_range = MICROLEARNING_EFFORT_RANGES[category]
                    if not (
                        effort_range.minimum_minutes
                        <= lesson.estimated_minutes
                        <= effort_range.maximum_minutes
                    ):
                        add(
                            "unit_effort_out_of_range",
                            "Microlearning unit effort is outside its category range.",
                            f"modules[{module_index}].lessons[{lesson_index}].estimated_minutes",
                            actual=lesson.estimated_minutes,
                            expected=(effort_range.minimum_minutes, effort_range.maximum_minutes),
                            module_ref=module.id,
                            lesson_ref=lesson.id,
                        )

        tolerance = module.estimated_hours * 0.2
        if abs(lesson_hours - module.estimated_hours) > tolerance:
            add(
                "duration_allocation_invalid",
                "Module hours must be within 20% of its lesson allocation.",
                f"modules[{module_index}].estimated_hours",
                actual=lesson_hours,
                expected=module.estimated_hours,
                module_ref=module.id,
            )

    for lesson_id, count in Counter(lesson_ids).items():
        if count > 1:
            add(
                "duplicate_lesson_id",
                "Lesson IDs must be unique.",
                "modules.lessons",
                actual=lesson_id,
                expected="unique",
                lesson_ref=lesson_id,
            )

    uncovered = [objective_id for objective_id in objective_ids if objective_id not in covered]
    for objective_id in uncovered:
        add(
            "objective_not_covered",
            "Every objective must be covered by at least one lesson.",
            "modules.lessons.objective_refs",
            actual=objective_id,
            expected="covered",
            objective_ref=objective_id,
        )

    total_hours = sum(module.estimated_hours for module in plan.modules)
    if plan.estimated_total_learning_hours <= 0:
        add(
            "duration_allocation_invalid",
            "Estimated total learning hours must be positive.",
            "estimated_total_learning_hours",
            actual=plan.estimated_total_learning_hours,
            expected="> 0",
        )
    elif abs(total_hours - plan.estimated_total_learning_hours) > plan.estimated_total_learning_hours * 0.2:
        add(
            "duration_allocation_invalid",
            "Total module hours must be within 20% of the plan estimate.",
            "estimated_total_learning_hours",
            actual=total_hours,
            expected=plan.estimated_total_learning_hours,
        )

    if policy is not None and plan.planning_metadata.get("planning_strategy") != MICROLEARNING_POLICY_VERSION:
        bounds = policy.bounds_for(plan.normalized_duration)
        if len(plan.modules) < bounds.minimum_modules or len(plan.modules) > bounds.maximum_modules:
            add(
                "module_count_out_of_bounds",
                "Module count is outside the duration policy bounds.",
                "modules",
                actual=len(plan.modules),
                expected=f"{bounds.minimum_modules}-{bounds.maximum_modules}",
            )
        if len(lesson_ids) < bounds.minimum_lessons or len(lesson_ids) > bounds.maximum_lessons:
            add(
                "lesson_count_out_of_bounds",
                "Lesson count is outside the duration policy bounds.",
                "modules.lessons",
                actual=len(lesson_ids),
                expected=f"{bounds.minimum_lessons}-{bounds.maximum_lessons}",
            )

    if plan.planning_metadata.get("planning_strategy") == MICROLEARNING_POLICY_VERSION:
        target_hours = parse_expected_learning_effort_hours(
            plan.planning_metadata.get("target_learning_effort_hours")
        )
        if target_hours is not None:
            fit = effort_fit(target_hours, total_hours)
            if fit != "WITHIN_TARGET":
                add(
                    "course_effort_under_target" if fit == "UNDER_TARGET" else "scope_exceeds_effort_budget",
                    "Estimated active effort is outside the confirmed target tolerance.",
                    "estimated_total_learning_hours",
                    actual=total_hours,
                    expected=f"{target_hours}h +/- {EFFORT_TOLERANCE_PERCENT}%",
                )

    return CurriculumPlanValidationReport(
        valid=not issues,
        issues=issues,
        objective_count=len(objective_ids),
        module_count=len(plan.modules),
        lesson_count=len(lesson_ids),
        estimated_total_hours=plan.estimated_total_learning_hours,
        covered_objective_count=len(covered & objective_id_set),
        uncovered_objective_refs=uncovered,
        unknown_objective_refs=sorted(unknown_refs),
    )


def validate_curriculum_plan(
    plan: CurriculumPlan,
    *,
    policy: CurriculumScopePolicy | None = None,
) -> CurriculumPlan:
    report = collect_curriculum_plan_validation(plan, policy=policy)
    if not report.valid:
        first_code = report.issues[0].code
        compatibility_code = {
            "module_count_out_of_bounds": "under_scoped",
            "lesson_count_out_of_bounds": "under_scoped",
            "unknown_objective_ref": "unknown_objective_reference",
            "duration_allocation_invalid": "total_duration_incoherent",
        }.get(first_code, first_code)
        raise CurriculumPlanValidationError(
            f"{compatibility_code}; issues={','.join(report.issue_codes)}",
            report=report,
        )
    return plan


def replay_curriculum_planning_attempt(
    attempt: CurriculumPlanningAttempt,
    *,
    policy: CurriculumScopePolicy | None = None,
) -> CurriculumPlanValidationReport:
    candidate = CurriculumPlan.model_validate(
        attempt.sanitized_parsed_candidate,
        strict=False,
    )
    normalized_duration: NormalizedTrainingDuration = attempt.normalized_duration
    if candidate.normalized_duration != normalized_duration:
        candidate = candidate.model_copy(update={"normalized_duration": normalized_duration})
    return collect_curriculum_plan_validation(candidate, policy=policy)
