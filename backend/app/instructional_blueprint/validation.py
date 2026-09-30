from collections.abc import Collection

from .schemas import InstructionalBlueprint


def _ensure_unique(values: Collection[str], *, code: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(code)


def _ensure_contiguous_sequences(sequences: list[int], *, code: str) -> None:
    if sorted(sequences) != list(range(1, len(sequences) + 1)):
        raise ValueError(code)


def validate_instructional_blueprint(
    blueprint: InstructionalBlueprint,
    *,
    objective_ids: Collection[str],
    learning_need_ref: str,
) -> None:
    if blueprint.learning_need_ref != learning_need_ref:
        raise ValueError("learning_need_reference_mismatch")

    expected_objective_ids = set(objective_ids)
    blueprint_objective_ids = set(blueprint.objective_refs)
    _ensure_unique(blueprint.objective_refs, code="duplicate_objective_reference")
    unknown_objectives = blueprint_objective_ids - expected_objective_ids
    if unknown_objectives:
        raise ValueError("objective_reference_not_found")
    if expected_objective_ids - blueprint_objective_ids:
        raise ValueError("orphan_objective")

    module_ids = [module.id for module in blueprint.modules]
    lesson_ids = [lesson.id for lesson in blueprint.lessons]
    _ensure_unique(module_ids, code="duplicate_module_reference")
    _ensure_unique(lesson_ids, code="duplicate_lesson_reference")
    _ensure_unique(
        blueprint.course.objective_refs,
        code="duplicate_objective_reference",
    )
    _ensure_unique(
        blueprint.course.module_refs,
        code="duplicate_module_reference",
    )
    _ensure_contiguous_sequences(
        [module.sequence for module in blueprint.modules],
        code="invalid_module_sequence",
    )
    _ensure_contiguous_sequences(
        [lesson.sequence for lesson in blueprint.lessons],
        code="invalid_lesson_sequence",
    )

    if set(blueprint.course.objective_refs) != blueprint_objective_ids:
        raise ValueError("course_objective_references_inconsistent")
    if blueprint.course.module_refs != module_ids:
        raise ValueError("course_module_references_inconsistent")

    referenced_objectives: set[str] = set()
    referenced_lessons: set[str] = set()
    for lesson in blueprint.lessons:
        if lesson.estimated_minutes <= 0:
            raise ValueError("invalid_lesson_duration")
        if lesson.assessment_refs:
            raise ValueError("assessment_reference_not_supported")
        _ensure_unique(lesson.objective_refs, code="duplicate_objective_reference")
        if set(lesson.objective_refs) - expected_objective_ids:
            raise ValueError("objective_reference_not_found")
        referenced_objectives.update(lesson.objective_refs)

    if referenced_objectives != expected_objective_ids:
        raise ValueError("orphan_objective")

    for module in blueprint.modules:
        if set(module.lesson_refs) - set(lesson_ids):
            raise ValueError("lesson_reference_not_found")
        _ensure_unique(module.lesson_refs, code="duplicate_lesson_reference")
        _ensure_unique(module.objective_refs, code="duplicate_objective_reference")
        module_objectives = set(module.objective_refs)
        if module_objectives - expected_objective_ids:
            raise ValueError("objective_reference_not_found")
        module_lessons = [
            lesson
            for lesson in blueprint.lessons
            if lesson.id in set(module.lesson_refs)
        ]
        lesson_objectives = {
            objective_ref
            for lesson in module_lessons
            for objective_ref in lesson.objective_refs
        }
        if module_objectives != lesson_objectives:
            raise ValueError("module_objective_references_inconsistent")
        referenced_lessons.update(module.lesson_refs)

    if referenced_lessons != set(lesson_ids):
        raise ValueError("orphan_lesson")
