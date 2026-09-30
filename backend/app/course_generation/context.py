from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.authorization.schemas import ActorContext
from app.content_generation.schemas import GoalDerivedLearningObjective
from app.course_authoring.schemas import CourseAuthoringMode, CourseAuthoringRequest, TrainingBrief
from app.curriculum_planning.duration import (
    NormalizedTrainingDuration,
    normalize_training_duration,
)
from app.learning_authoring.schemas import (
    InstructionalBlueprintProjection,
    LearningObjectiveProjection,
)

from .errors import CourseGenerationArtifactNotFoundError

TProjection = TypeVar("TProjection", bound=BaseModel)


class CourseGenerationReferenceReader(Protocol):
    async def get_learning_need(self, artifact_id: str, actor: ActorContext) -> object: ...

    async def get_learning_objective(self, artifact_id: str, actor: ActorContext) -> object: ...

    async def get_instructional_blueprint(
        self, artifact_id: str, actor: ActorContext
    ) -> object: ...


class AudienceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    learner_count: int = Field(ge=0)
    source: str = Field(min_length=1)


class CourseGenerationContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    authoring_request_ref: str = Field(min_length=1)
    course_title: str = Field(min_length=1)
    training_brief: TrainingBrief
    audience_summary: AudienceSummary
    learning_need_refs: list[str] = Field(default_factory=list)
    learning_objectives: list[LearningObjectiveProjection] = Field(default_factory=list)
    generated_objectives: list[GoalDerivedLearningObjective] = Field(default_factory=list)
    instructional_blueprint: InstructionalBlueprintProjection | None = None
    language: str | None = None
    duration_constraint: str | None = None
    target_completion_context: str | None = None
    normalized_duration: NormalizedTrainingDuration | None = None


class CourseGenerationContextBuilder:
    def __init__(self, references: CourseGenerationReferenceReader) -> None:
        self._references = references

    async def build(
        self,
        request: CourseAuthoringRequest,
        actor: ActorContext,
        *,
        generated_objectives_override: Sequence[GoalDerivedLearningObjective] | None = None,
    ) -> CourseGenerationContext:
        if request.mode is CourseAuthoringMode.GOAL_DRIVEN:
            objectives: list[LearningObjectiveProjection] = []
            generated_objectives = list(
                generated_objectives_override
                or [
                    GoalDerivedLearningObjective(
                        id=f"goal-driven-objective:{request.id}:1",
                        statement=request.training_brief.goal,
                        measurable_outcome=None,
                        sequence=1,
                        origin="GOAL_DRIVEN_TRAINING_BRIEF",
                    )
                ]
            )
            blueprint = None
            learning_need_refs: list[str] = []
        else:
            learning_need_refs = list(request.learning_need_refs)
            generated_objectives = []
            for reference in learning_need_refs:
                await self._read(self._references.get_learning_need, reference, actor)

            blueprint = None
            if request.instructional_blueprint_ref is not None:
                blueprint = await self._read_blueprint(request.instructional_blueprint_ref, actor)
                if not learning_need_refs:
                    learning_need_refs = [blueprint.learning_need_ref]

            objective_refs = list(request.objective_refs)
            if not objective_refs and blueprint is not None:
                objective_refs = list(blueprint.objective_refs)
            if not objective_refs:
                # GAP_DRIVEN requests may carry only the canonical learning-need
                # refs. The learning-authoring projection owns the deterministic
                # objective identity for each need; keep planning compatible with
                # that bounded request contract instead of producing an empty plan.
                objective_refs = [f"objective-{reference}" for reference in learning_need_refs]
            objectives = [
                await self._read_objective(reference, actor) for reference in objective_refs
            ]

        brief = request.training_brief
        weekly_effort: float | None = None
        weekly_effort_raw = request.constraints.get("weekly_effort_hours")
        if weekly_effort_raw:
            try:
                weekly_effort = float(weekly_effort_raw)
                if weekly_effort <= 0:
                    weekly_effort = None
            except ValueError:
                weekly_effort = None
        return CourseGenerationContext(
            authoring_request_ref=request.id,
            course_title=request.title,
            training_brief=brief,
            audience_summary=AudienceSummary(
                learner_count=request.audience_snapshot.learner_count,
                source=request.audience_snapshot.source,
            ),
            learning_need_refs=learning_need_refs,
            learning_objectives=objectives,
            generated_objectives=generated_objectives,
            instructional_blueprint=blueprint,
            language=brief.language,
            duration_constraint=brief.duration_constraint,
            target_completion_context=brief.target_completion_context,
            normalized_duration=normalize_training_duration(
                brief.duration_constraint,
                weekly_effort_hours=weekly_effort,
            ),
        )

    async def _read_blueprint(
        self, reference: str, actor: ActorContext
    ) -> InstructionalBlueprintProjection:
        value = await self._read(self._references.get_instructional_blueprint, reference, actor)
        return self._as_projection(value, InstructionalBlueprintProjection, reference)

    async def _read_objective(
        self, reference: str, actor: ActorContext
    ) -> LearningObjectiveProjection:
        value = await self._read(self._references.get_learning_objective, reference, actor)
        return self._as_projection(value, LearningObjectiveProjection, reference)

    async def _read(
        self,
        reader: Callable[[str, ActorContext], Awaitable[object]],
        reference: str,
        actor: ActorContext,
    ) -> object:
        try:
            return await reader(reference, actor)
        except Exception as exc:
            raise CourseGenerationArtifactNotFoundError(
                f"course_generation_artifact_not_found:{reference}"
            ) from exc

    @staticmethod
    def _as_projection(value: object, schema: type[TProjection], reference: str) -> TProjection:
        if isinstance(value, schema):
            return value
        try:
            if isinstance(value, BaseModel):
                return schema.model_validate(value.model_dump())
            return schema.model_validate(value)
        except Exception as exc:
            raise CourseGenerationArtifactNotFoundError(
                f"course_generation_artifact_invalid:{reference}"
            ) from exc
