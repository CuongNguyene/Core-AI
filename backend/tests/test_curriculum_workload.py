import pytest

from app.curriculum_planning.duration import normalize_training_duration
from app.curriculum_planning.schemas import (
    CurriculumLessonPlan,
    CurriculumModulePlan,
    CurriculumObjective,
    CurriculumPlan,
)
from app.curriculum_planning.validation import (
    CurriculumPlanValidationError,
    validate_curriculum_plan,
)
from app.curriculum_planning.workload import allocate_curriculum_plan_workload


def _plan_with_varied_workload() -> CurriculumPlan:
    objective = CurriculumObjective(
        id="objective-001",
        statement="Build the target capability",
        measurable_outcome="Deliver a working implementation.",
        sequence=1,
        origin="GOAL_DRIVEN_TRAINING_BRIEF",
    )
    lesson_types = ["foundation", "concept", "applied", "capstone"]
    lessons = [
        CurriculumLessonPlan(
            id=f"lesson-{index}",
            title=f"Lesson {index}",
            order=index,
            objective_refs=[objective.id],
            estimated_minutes=60,
            lesson_type=lesson_type,
        )
        for index, lesson_type in enumerate(lesson_types, start=1)
    ]
    return CurriculumPlan(
        id="plan-workload-001",
        authoring_request_ref="request-workload-001",
        version=1,
        course_title="Workload-aware course",
        course_description="A course with varied instructional workload.",
        normalized_duration=normalize_training_duration("10 hours"),
        learning_objectives=[objective],
        modules=[CurriculumModulePlan(
            id="module-001",
            title="Mixed workload module",
            order=1,
            objective_refs=[objective.id],
            estimated_hours=10,
            lessons=lessons,
        )],
        estimated_total_learning_hours=10,
    )


def test_workload_allocation_is_weighted_rounded_and_total_preserving() -> None:
    allocated = allocate_curriculum_plan_workload(_plan_with_varied_workload())
    lessons = allocated.modules[0].lessons
    durations = [lesson.estimated_total_effort_minutes for lesson in lessons]

    assert all(duration is not None and duration % 15 == 0 for duration in durations)
    assert sum(duration or 0 for duration in durations) == 600
    assert durations[3] > durations[0]
    assert durations[2] >= durations[1]
    assert allocated.modules[0].estimated_hours == 10


def test_workload_allocation_preserves_instruction_practice_semantics() -> None:
    lessons = allocate_curriculum_plan_workload(_plan_with_varied_workload()).modules[0].lessons

    foundation, concept, applied, capstone = lessons
    assert foundation.estimated_instruction_minutes > foundation.estimated_practice_minutes
    assert concept.estimated_instruction_minutes > concept.estimated_practice_minutes
    assert applied.estimated_practice_minutes > applied.estimated_instruction_minutes
    assert capstone.estimated_practice_minutes > capstone.estimated_instruction_minutes
    for lesson in lessons:
        assert (
            lesson.estimated_instruction_minutes + lesson.estimated_practice_minutes
            == lesson.estimated_total_effort_minutes
        )
        assert lesson.estimated_minutes == lesson.estimated_total_effort_minutes


def test_module_duration_is_derived_from_allocated_lessons() -> None:
    plan = _plan_with_varied_workload().model_copy(update={
        "modules": [
            CurriculumModulePlan(
                id="module-001",
                title="First module",
                order=1,
                objective_refs=["objective-001"],
                estimated_hours=1,
                lessons=[_plan_with_varied_workload().modules[0].lessons[0]],
            ),
            CurriculumModulePlan(
                id="module-002",
                title="Second module",
                order=2,
                objective_refs=["objective-001"],
                estimated_hours=9,
                lessons=_plan_with_varied_workload().modules[0].lessons[1:],
            ),
        ],
    })

    allocated = allocate_curriculum_plan_workload(plan)

    for module in allocated.modules:
        assert module.estimated_hours == sum(
            lesson.estimated_total_effort_minutes or 0 for lesson in module.lessons
        ) / 60


def test_legacy_plan_without_workload_fields_remains_readable() -> None:
    legacy = _plan_with_varied_workload().model_dump(mode="json")
    for lesson in legacy["modules"][0]["lessons"]:
        lesson.pop("estimated_instruction_minutes", None)
        lesson.pop("estimated_practice_minutes", None)
        lesson.pop("estimated_total_effort_minutes", None)
        lesson.pop("workload_category", None)

    restored = CurriculumPlan.model_validate(legacy, strict=False)

    assert restored.modules[0].lessons[0].estimated_minutes == 60
    assert restored.modules[0].lessons[0].estimated_total_effort_minutes is None


def test_validator_rejects_unsupported_workload_lesson_type() -> None:
    invalid = _plan_with_varied_workload().model_copy(update={
        "modules": [
            _plan_with_varied_workload().modules[0].model_copy(update={
                "lessons": [
                    _plan_with_varied_workload().modules[0].lessons[0].model_copy(
                        update={"lesson_type": "unknown_type"}
                    ),
                ],
            }),
        ],
    })

    with pytest.raises(CurriculumPlanValidationError, match="unsupported_lesson_type"):
        validate_curriculum_plan(invalid)


def test_twelve_month_shape_preserves_scope_and_gets_non_uniform_workload() -> None:
    objectives = [
        CurriculumObjective(
            id=f"objective-{index}",
            statement=f"Build capability {index}",
            measurable_outcome=f"Deliver outcome {index}.",
            sequence=index,
            origin="GOAL_DRIVEN_TRAINING_BRIEF",
        )
        for index in range(1, 11)
    ]
    type_patterns = [
        ["foundation", "foundation", "concept", "practice"],
        ["concept", "applied", "applied", "practice"],
        ["applied", "practice", "practice", "integration"],
        ["concept", "applied", "practice", "integration"],
        ["applied", "applied", "integration", "assessment"],
        ["practice", "practice", "integration", "capstone"],
        ["concept", "applied", "practice", "practice"],
        ["applied", "integration", "practice", "capstone"],
        ["foundation", "concept", "applied", "practice"],
        ["integration", "practice", "capstone", "assessment"],
    ]
    modules = []
    for module_index, lesson_types in enumerate(type_patterns, start=1):
        objective = objectives[module_index - 1]
        modules.append(
            CurriculumModulePlan(
                id=f"module-{module_index}",
                title=f"Module {module_index}",
                order=module_index,
                objective_refs=[objective.id],
                estimated_hours=1,
                lessons=[
                    CurriculumLessonPlan(
                        id=f"lesson-{module_index}-{lesson_index}",
                        title=f"Lesson {module_index}.{lesson_index}",
                        order=lesson_index,
                        objective_refs=[objective.id],
                        estimated_minutes=60,
                        lesson_type=lesson_type,
                    )
                    for lesson_index, lesson_type in enumerate(lesson_types, start=1)
                ],
            )
        )
    plan = CurriculumPlan(
        id="plan-twelve-months",
        authoring_request_ref="request-twelve-months",
        version=1,
        course_title="Long-form course",
        course_description="A duration-aware course.",
        normalized_duration=normalize_training_duration("12 months"),
        learning_objectives=objectives,
        modules=modules,
        estimated_total_learning_hours=156,
    )

    allocated = allocate_curriculum_plan_workload(plan)
    lessons = [lesson for module in allocated.modules for lesson in module.lessons]
    module_hours = [module.estimated_hours for module in allocated.modules]

    assert len(allocated.modules) == 10
    assert len(lessons) == 40
    assert sum(lesson.estimated_total_effort_minutes or 0 for lesson in lessons) == 9_360
    assert len({lesson.estimated_total_effort_minutes for lesson in lessons}) > 1
    assert len(set(module_hours)) > 1
    assert [lesson.objective_refs for lesson in lessons] == [
        lesson.objective_refs
        for module in plan.modules
        for lesson in module.lessons
    ]
