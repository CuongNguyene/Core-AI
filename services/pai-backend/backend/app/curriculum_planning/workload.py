from dataclasses import dataclass
from math import ceil, floor

from .microlearning import (
    MICROLEARNING_EFFORT_RANGES,
    MICROLEARNING_POLICY_VERSION,
    effort_fit,
    parse_expected_learning_effort_hours,
)
from .schemas import (
    CurriculumLessonPlan,
    CurriculumPlan,
    LessonWorkloadCategory,
)

ROUNDING_INCREMENT_MINUTES = 15
MIN_LESSON_TOTAL_MINUTES = 60
TARGET_MAX_LESSON_TOTAL_MINUTES = 180
WORKLOAD_POLICY_VERSION = "sep-02.3b-v1"


class UnsupportedLessonTypeError(ValueError):
    pass


@dataclass(frozen=True)
class LessonWorkloadProfile:
    lesson_type: str
    category: LessonWorkloadCategory
    complexity_weight: float
    instruction_ratio: float
    practice_ratio: float
    estimated_instruction_minutes: int | None = None
    estimated_practice_minutes: int | None = None
    estimated_total_effort_minutes: int | None = None


@dataclass(frozen=True)
class WorkloadCategoryPolicy:
    category: LessonWorkloadCategory
    complexity_weight: float
    instruction_ratio: float
    practice_ratio: float
    target_max_minutes: int


@dataclass(frozen=True)
class RepresentableEffortRange:
    minimum_minutes: int
    maximum_minutes: int


WORKLOAD_POLICIES: dict[LessonWorkloadCategory, WorkloadCategoryPolicy] = {
    LessonWorkloadCategory.FOUNDATION: WorkloadCategoryPolicy(
        LessonWorkloadCategory.FOUNDATION, 0.8, 0.60, 0.40, 180
    ),
    LessonWorkloadCategory.CONCEPT: WorkloadCategoryPolicy(
        LessonWorkloadCategory.CONCEPT, 1.0, 0.65, 0.35, 180
    ),
    LessonWorkloadCategory.APPLIED: WorkloadCategoryPolicy(
        LessonWorkloadCategory.APPLIED, 1.1, 0.40, 0.60, 240
    ),
    LessonWorkloadCategory.PRACTICE: WorkloadCategoryPolicy(
        LessonWorkloadCategory.PRACTICE, 1.2, 0.25, 0.75, 240
    ),
    LessonWorkloadCategory.INTEGRATION: WorkloadCategoryPolicy(
        LessonWorkloadCategory.INTEGRATION, 1.4, 0.30, 0.70, 300
    ),
    LessonWorkloadCategory.ASSESSMENT: WorkloadCategoryPolicy(
        LessonWorkloadCategory.ASSESSMENT, 1.0, 0.10, 0.90, 180
    ),
    LessonWorkloadCategory.CAPSTONE: WorkloadCategoryPolicy(
        LessonWorkloadCategory.CAPSTONE, 1.8, 0.15, 0.85, 480
    ),
}


LESSON_TYPE_TO_CATEGORY: dict[str, LessonWorkloadCategory] = {
    "foundation": LessonWorkloadCategory.FOUNDATION,
    "foundation_lesson": LessonWorkloadCategory.FOUNDATION,
    "orientation": LessonWorkloadCategory.FOUNDATION,
    "concept": LessonWorkloadCategory.CONCEPT,
    "conceptual": LessonWorkloadCategory.CONCEPT,
    "concept_lecture": LessonWorkloadCategory.CONCEPT,
    "lecture": LessonWorkloadCategory.CONCEPT,
    "applied": LessonWorkloadCategory.APPLIED,
    "practical": LessonWorkloadCategory.APPLIED,
    "implementation": LessonWorkloadCategory.APPLIED,
    "applied_practice": LessonWorkloadCategory.APPLIED,
    "practice": LessonWorkloadCategory.PRACTICE,
    "skill_practice": LessonWorkloadCategory.PRACTICE,
    "code_lab": LessonWorkloadCategory.PRACTICE,
    "lab": LessonWorkloadCategory.PRACTICE,
    "integration": LessonWorkloadCategory.INTEGRATION,
    "integration_project": LessonWorkloadCategory.INTEGRATION,
    "assessment": LessonWorkloadCategory.ASSESSMENT,
    "assessment_review": LessonWorkloadCategory.ASSESSMENT,
    "capstone": LessonWorkloadCategory.CAPSTONE,
    "capstone_project": LessonWorkloadCategory.CAPSTONE,
}


def workload_profile_for(lesson_type: str) -> LessonWorkloadProfile:
    key = lesson_type.strip().lower()
    category = LESSON_TYPE_TO_CATEGORY.get(key)
    if category is None:
        try:
            category = LessonWorkloadCategory(key.upper())
        except ValueError as exc:
            raise UnsupportedLessonTypeError(lesson_type) from exc
    policy = WORKLOAD_POLICIES[category]
    return LessonWorkloadProfile(
        lesson_type=lesson_type,
        category=category,
        complexity_weight=policy.complexity_weight,
        instruction_ratio=policy.instruction_ratio,
        practice_ratio=policy.practice_ratio,
    )


def representable_effort_range(plan: CurriculumPlan) -> RepresentableEffortRange:
    """Return the effort envelope available to the current microlearning shape.

    The allocator works in rounded increments, so the envelope uses the same
    ceil/floor rules as allocation. This makes an impossible target visible
    before allocation can silently stop at category maxima.
    """
    lessons = [lesson for module in plan.modules for lesson in module.lessons]
    if not lessons:
        return RepresentableEffortRange(minimum_minutes=0, maximum_minutes=0)
    ranges = [
        MICROLEARNING_EFFORT_RANGES[workload_profile_for(lesson.lesson_type).category]
        for lesson in lessons
    ]
    minimum_minutes = sum(
        ceil(item.minimum_minutes / ROUNDING_INCREMENT_MINUTES) * ROUNDING_INCREMENT_MINUTES
        for item in ranges
    )
    maximum_minutes = sum(
        (item.maximum_minutes // ROUNDING_INCREMENT_MINUTES) * ROUNDING_INCREMENT_MINUTES
        for item in ranges
    )
    return RepresentableEffortRange(
        minimum_minutes=minimum_minutes,
        maximum_minutes=maximum_minutes,
    )


def _rounded_weighted_units(weights: list[float], total_units: int) -> list[int]:
    if not weights or total_units <= 0:
        return [0 for _ in weights]
    total_weight = sum(weights)
    exact = [total_units * weight / total_weight for weight in weights]
    units = [floor(value) for value in exact]
    remaining = total_units - sum(units)
    ranking = sorted(
        range(len(weights)),
        key=lambda index: (exact[index] - units[index], -index),
        reverse=True,
    )
    for index in ranking[:remaining]:
        units[index] += 1
    return units


def _allocate_total_minutes(lessons: list[CurriculumLessonPlan], total_minutes: int) -> list[int]:
    total_units = max(1, round(total_minutes / ROUNDING_INCREMENT_MINUTES))
    weights = [workload_profile_for(lesson.lesson_type).complexity_weight for lesson in lessons]
    minimum_units = MIN_LESSON_TOTAL_MINUTES // ROUNDING_INCREMENT_MINUTES
    if total_units >= minimum_units * len(lessons):
        remaining_units = total_units - minimum_units * len(lessons)
        return [
            minimum_units + units
            for units in _rounded_weighted_units(weights, remaining_units)
        ]
    return _rounded_weighted_units(weights, total_units)


def _allocate_microlearning_minutes(
    lessons: list[CurriculumLessonPlan], total_minutes: int
) -> list[int]:
    if not lessons:
        return []
    ranges = [
        MICROLEARNING_EFFORT_RANGES[workload_profile_for(lesson.lesson_type).category]
        for lesson in lessons
    ]
    weights = [workload_profile_for(lesson.lesson_type).complexity_weight for lesson in lessons]
    minimums = [ceil(item.minimum_minutes / ROUNDING_INCREMENT_MINUTES) for item in ranges]
    maximums = [item.maximum_minutes // ROUNDING_INCREMENT_MINUTES for item in ranges]
    values = minimums[:]
    remaining = max(0, round(total_minutes / ROUNDING_INCREMENT_MINUTES) - sum(values))
    while remaining >= 1:
        candidates = [
            index for index, value in enumerate(values)
            if value + 1 <= maximums[index]
        ]
        if not candidates:
            break
        index = max(candidates, key=lambda item: (weights[item], -item))
        values[index] += 1
        remaining -= 1
    return values


def allocate_curriculum_plan_workload(plan: CurriculumPlan) -> CurriculumPlan:
    lessons = [lesson for module in plan.modules for lesson in module.lessons]
    if not lessons:
        return plan
    total_minutes = round(plan.estimated_total_learning_hours * 60)
    allocated_units = (
        _allocate_microlearning_minutes(lessons, total_minutes)
        if plan.planning_metadata.get("planning_strategy") == MICROLEARNING_POLICY_VERSION
        else _allocate_total_minutes(lessons, total_minutes)
    )
    updated_by_id: dict[str, CurriculumLessonPlan] = {}
    for lesson, units in zip(lessons, allocated_units, strict=True):
        total_effort = units * ROUNDING_INCREMENT_MINUTES
        profile = workload_profile_for(lesson.lesson_type)
        instruction = round(total_effort * profile.instruction_ratio)
        updated_by_id[lesson.id] = lesson.model_copy(update={
            "workload_category": profile.category,
            "estimated_minutes": total_effort,
            "estimated_instruction_minutes": instruction,
            "estimated_practice_minutes": total_effort - instruction,
            "estimated_total_effort_minutes": total_effort,
        })

    updated_modules = []
    for module in plan.modules:
        updated_lessons = [updated_by_id[lesson.id] for lesson in module.lessons]
        module_minutes = sum(lesson.estimated_total_effort_minutes or 0 for lesson in updated_lessons)
        updated_modules.append(module.model_copy(update={
            "estimated_hours": module_minutes / 60,
            "lessons": updated_lessons,
        }))
    metadata = dict(plan.planning_metadata)
    metadata["workload_policy_version"] = WORKLOAD_POLICY_VERSION
    estimated_minutes = sum(lesson.estimated_minutes for lesson in updated_by_id.values())
    metadata["estimated_learning_effort_minutes"] = str(estimated_minutes)
    target_hours = parse_expected_learning_effort_hours(
        metadata.get("target_learning_effort_hours")
    )
    if plan.planning_metadata.get("planning_strategy") == MICROLEARNING_POLICY_VERSION:
        metadata["effort_fit"] = effort_fit(target_hours, estimated_minutes / 60)
    return plan.model_copy(update={
        "modules": updated_modules,
        "planning_metadata": metadata,
    })
