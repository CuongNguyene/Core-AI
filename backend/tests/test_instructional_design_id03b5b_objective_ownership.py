import pytest

from app.instructional_design.experiment_runners import (
    build_module_objective_scope,
    validate_lesson_objective_scope,
)
from app.instructional_design.fixtures import research_fixture_bundles


def test_valid_objective_inheritance_builds_module_scopes() -> None:
    course = next(iter(research_fixture_bundles().values())).course_outline

    scope = build_module_objective_scope(
        course,
        objective_ids=course.objective_ids,
    )

    assert scope == {
        module.id: tuple(module.objective_ids) for module in course.modules
    }


def test_module_objective_outside_course_fails_closed_without_repair() -> None:
    course = next(iter(research_fixture_bundles().values())).course_outline
    invalid_module = course.modules[0].model_copy(
        update={"objective_ids": ["objective-outside-course"]}
    )
    invalid_course = course.model_copy(
        update={"modules": [invalid_module, *course.modules[1:]]}
    )

    with pytest.raises(ValueError, match="module objective outside course"):
        build_module_objective_scope(invalid_course, objective_ids=course.objective_ids)

    assert invalid_course.modules[0].objective_ids == ["objective-outside-course"]


def test_lesson_objective_outside_parent_module_fails_closed_without_repair() -> None:
    with pytest.raises(ValueError, match="lesson objective outside module"):
        validate_lesson_objective_scope(
            module_objective_ids=["objective-a"],
            lesson_objective_ids=["objective-b"],
        )
