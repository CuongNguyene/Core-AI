from typing import Protocol

from pydantic import BaseModel, ConfigDict

from app.learning.schemas import LearningObjective
from app.learning_need_profile.schemas import LearningNeedProfile

from .schemas import (
    CourseBlueprint,
    InstructionalBlueprint,
    InstructionalPattern,
    LessonBlueprint,
    LessonType,
    ModuleBlueprint,
)
from .validation import validate_instructional_blueprint


class InstructionalBlueprintInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    learning_need: LearningNeedProfile
    objective: LearningObjective
    learning_constraints: dict[str, object] | None = None


class InstructionalBlueprintGenerator(Protocol):
    async def generate(
        self, objective_context: InstructionalBlueprintInput
    ) -> InstructionalBlueprint: ...


class DeterministicInstructionalBlueprintGenerator:
    """Create a content-free teaching structure from one objective."""

    version = "deterministic-instructional-blueprint-v1"
    default_lesson_minutes = 30

    async def generate(
        self, objective_context: InstructionalBlueprintInput
    ) -> InstructionalBlueprint:
        learning_need = objective_context.learning_need
        objective = objective_context.objective
        if objective.learning_need_ref != learning_need.id:
            raise ValueError("learning_need_reference_mismatch")

        title = objective.statement or objective.measurable_outcome
        lesson_id = f"lesson-blueprint-{objective.id}"
        module_id = f"module-blueprint-{objective.id}"
        course_id = f"course-blueprint-{objective.id}"
        blueprint = InstructionalBlueprint(
            id=f"instructional-blueprint-{objective.id}",
            learning_need_ref=learning_need.id,
            objective_refs=[objective.id],
            course=CourseBlueprint(
                id=course_id,
                title=title,
                objective_refs=[objective.id],
                module_refs=[module_id],
            ),
            modules=[
                ModuleBlueprint(
                    id=module_id,
                    title=title,
                    objective_refs=[objective.id],
                    lesson_refs=[lesson_id],
                    sequence=1,
                )
            ],
            lessons=[
                LessonBlueprint(
                    id=lesson_id,
                    title=title,
                    objective_refs=[objective.id],
                    lesson_type=LessonType.SKILL_PRACTICE,
                    estimated_minutes=self._estimated_minutes(objective_context),
                    instructional_pattern=[
                        InstructionalPattern.CONCEPT_INTRODUCTION,
                        InstructionalPattern.WORKED_EXAMPLE,
                        InstructionalPattern.GUIDED_PRACTICE,
                        InstructionalPattern.INDEPENDENT_PRACTICE,
                    ],
                    assessment_refs=[],
                    sequence=1,
                )
            ],
        )
        validate_instructional_blueprint(
            blueprint,
            objective_ids={objective.id},
            learning_need_ref=learning_need.id,
        )
        return blueprint

    def _estimated_minutes(self, objective_context: InstructionalBlueprintInput) -> int:
        constraints = (
            objective_context.learning_need.learning_constraints
            if objective_context.learning_constraints is None
            else objective_context.learning_constraints
        )
        value = constraints.get("estimated_minutes")
        if type(value) is int and value > 0:
            return value
        return self.default_lesson_minutes
