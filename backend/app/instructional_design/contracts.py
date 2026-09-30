"""Trusted, versioned structured-output contracts for staged research proposals."""

from collections.abc import Mapping, Sequence
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.instructional_design.schemas import (
    AssessmentDependencyCandidate as AssessmentDependencyCandidate,
)
from app.instructional_design.schemas import (
    AssessmentSpec,
    CourseOutline,
    LearningObjectiveSpec,
    LessonSpec,
    PrerequisiteClassification,
    PrerequisiteSpec,
    PrerequisiteStatus,
    PrerequisiteStructuralReviewStatus,
    ResearchLearningBrief,
)
from app.instructional_design.workload import WorkloadBudgetContext
from app.model_gateway.prompts import PromptTemplateRegistry
from app.model_gateway.schema_registry import OutputSchemaRegistry

INSTRUCTIONAL_DESIGN_SCHEMA_VERSION = "0.1"
INSTRUCTIONAL_DESIGN_STAGE_VERSION = "0.2"
INSTRUCTIONAL_DESIGN_STAGE_VERSION_V03 = "0.3"
INSTRUCTIONAL_DESIGN_STAGE_VERSION_V031 = "0.3.1"
INSTRUCTIONAL_DESIGN_STAGE_VERSION_V032 = "0.3.2"
INSTRUCTIONAL_DESIGN_STAGE_VERSION_V033 = "0.3.3"
INSTRUCTIONAL_DESIGN_STAGE_VERSION_V034 = "0.3.4"
OBJECTIVE_DESIGN_SCHEMA_ID = "instructional_objective_design"
ASSESSMENT_DESIGN_SCHEMA_ID = "instructional_assessment_design"
PREREQUISITE_PROPOSAL_SCHEMA_ID = "instructional_prerequisite_proposal"
COURSE_PLANNING_SCHEMA_ID = "instructional_course_planning"
LESSON_PLANNING_SCHEMA_ID = "instructional_lesson_planning"
ONE_SHOT_BASELINE_SCHEMA_ID = "instructional_design_one_shot_baseline"
ONE_SHOT_BASELINE_SCHEMA_VERSION = "0.1"


class LearningObjectiveDesignOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    brief_id: str = Field(min_length=1)
    objectives: list[LearningObjectiveSpec] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def objectives_must_preserve_brief_id(self) -> "LearningObjectiveDesignOutput":
        if any(objective.brief_id != self.brief_id for objective in self.objectives):
            raise ValueError("objective proposals must preserve brief_id")
        return self


class AssessmentDesignOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    objective_ids: list[str] = Field(default_factory=list)
    assessments: list[AssessmentSpec] = Field(default_factory=list)
    dependency_candidates: list["AssessmentDependencyCandidate"] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def assessments_must_preserve_objective_ids(self) -> "AssessmentDesignOutput":
        allowed = set(self.objective_ids)
        if any(
            not set(assessment.objective_ids).issubset(allowed) for assessment in self.assessments
        ):
            raise ValueError("assessment proposals must preserve supplied objective_ids")
        return self


class PrerequisiteProposalOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    brief_id: str = Field(min_length=1)
    prerequisites: list[PrerequisiteSpec] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class PrerequisiteStructuralReview(BaseModel):
    """Deterministic review only; it never confirms or rejects a candidate."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    prerequisite_id: str = Field(min_length=1)
    status: PrerequisiteStructuralReviewStatus


def review_prerequisite_structural_minimality(
    prerequisite: PrerequisiteSpec,
    *,
    allowed_requirement_refs: set[str],
) -> PrerequisiteStructuralReview:
    """Check traceability mechanics without judging pedagogical truth."""

    if (
        prerequisite.status is not PrerequisiteStatus.CANDIDATE
        or prerequisite.classification is not PrerequisiteClassification.REQUIRED_PREREQUISITE
    ):
        status = PrerequisiteStructuralReviewStatus.NOT_APPLICABLE
    elif not prerequisite.required_for_refs or not set(prerequisite.required_for_refs).issubset(
        allowed_requirement_refs
    ):
        status = PrerequisiteStructuralReviewStatus.UNRESOLVED_REFERENCE
    else:
        rationale = " ".join((prerequisite.rationale or "").casefold().split())
        if not rationale or rationale in {"helpful", "foundational", "useful", "related"}:
            status = PrerequisiteStructuralReviewStatus.INSUFFICIENT_RATIONALE
        else:
            status = PrerequisiteStructuralReviewStatus.STRUCTURALLY_SUPPORTED
    return PrerequisiteStructuralReview(prerequisite_id=prerequisite.id, status=status)


def validate_v03_prerequisite_proposals(output: PrerequisiteProposalOutput) -> None:
    """Enforce v0.3 rationale/minimality at the versioned adapter boundary."""

    for item in output.prerequisites:
        if item.classification.value != "required_prerequisite":
            continue
        if item.basis.value == "model_proposed" and (
            not item.rationale or not item.required_for_refs
        ):
            raise ValueError(
                "v0.3 model-proposed required prerequisites need rationale and required_for_refs"
            )


class CoursePlanningOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    brief_id: str = Field(min_length=1)
    course_outline: CourseOutline
    assumptions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def course_must_preserve_brief_id(self) -> "CoursePlanningOutput":
        if self.course_outline.brief_id != self.brief_id:
            raise ValueError("course proposal must preserve brief_id")
        return self


class LessonPlanningOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    course_id: str = Field(min_length=1)
    lessons: list[LessonSpec] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class OneShotInstructionalDesignOutput(BaseModel):
    """Canonical aggregate emitted by the baseline without staged prompting."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    brief_id: str = Field(min_length=1)
    objectives: list[LearningObjectiveSpec] = Field(default_factory=list)
    assessments: list[AssessmentSpec] = Field(default_factory=list)
    prerequisites: list[PrerequisiteSpec] = Field(default_factory=list)
    course_outline: CourseOutline | None = None
    lessons: list[LessonSpec] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def aggregate_must_preserve_brief_id(self) -> "OneShotInstructionalDesignOutput":
        if any(objective.brief_id != self.brief_id for objective in self.objectives):
            raise ValueError("one-shot objectives must preserve brief_id")
        if self.course_outline is not None and self.course_outline.brief_id != self.brief_id:
            raise ValueError("one-shot course outline must preserve brief_id")
        return self


class ObjectiveDesigner(Protocol):
    async def propose(self, brief: ResearchLearningBrief) -> LearningObjectiveDesignOutput: ...


class AssessmentDesigner(Protocol):
    async def propose(
        self, brief: ResearchLearningBrief, objectives: Sequence[LearningObjectiveSpec]
    ) -> AssessmentDesignOutput: ...


class PrerequisiteProposer(Protocol):
    async def propose(
        self,
        brief: ResearchLearningBrief,
        objectives: Sequence[LearningObjectiveSpec],
        assessments: Sequence[AssessmentSpec],
        dependency_candidates: Sequence[AssessmentDependencyCandidate] = (),
    ) -> PrerequisiteProposalOutput: ...


class CoursePlanner(Protocol):
    async def propose(
        self,
        brief: ResearchLearningBrief,
        objectives: Sequence[LearningObjectiveSpec],
        assessments: Sequence[AssessmentSpec],
        prerequisites: Sequence[PrerequisiteSpec],
        dependency_candidates: Sequence[AssessmentDependencyCandidate] = (),
        workload_context: WorkloadBudgetContext | None = None,
    ) -> CoursePlanningOutput: ...


class LessonPlanner(Protocol):
    async def propose(
        self,
        brief: ResearchLearningBrief,
        objectives: Sequence[LearningObjectiveSpec],
        assessments: Sequence[AssessmentSpec],
        prerequisites: Sequence[PrerequisiteSpec],
        course_outline: CourseOutline,
        dependency_candidates: Sequence[AssessmentDependencyCandidate] = (),
        module_objective_scope: Mapping[str, Sequence[str]] | None = None,
        workload_context: WorkloadBudgetContext | None = None,
    ) -> LessonPlanningOutput: ...


def register_instructional_design_contracts(
    prompts: PromptTemplateRegistry, schemas: OutputSchemaRegistry
) -> None:
    """Register exact v0.1 prompt/schema pairs without invoking a provider."""

    from app.instructional_design.prompts import instructional_design_prompt_templates

    schema_by_id: dict[str, type[BaseModel]] = {
        OBJECTIVE_DESIGN_SCHEMA_ID: LearningObjectiveDesignOutput,
        ASSESSMENT_DESIGN_SCHEMA_ID: AssessmentDesignOutput,
        PREREQUISITE_PROPOSAL_SCHEMA_ID: PrerequisiteProposalOutput,
        COURSE_PLANNING_SCHEMA_ID: CoursePlanningOutput,
        LESSON_PLANNING_SCHEMA_ID: LessonPlanningOutput,
    }
    for schema_id, schema in schema_by_id.items():
        schemas.register(schema_id, INSTRUCTIONAL_DESIGN_SCHEMA_VERSION, schema)
    for prompt in instructional_design_prompt_templates():
        prompts.register(prompt)


def register_instructional_design_experiment_contracts(
    prompts: PromptTemplateRegistry, schemas: OutputSchemaRegistry
) -> None:
    """Register ID-02's isolated v0.2 staged contracts and v0.1 baseline."""

    from app.instructional_design.prompts import instructional_design_experiment_prompt_templates

    structured_schema_by_id: dict[str, type[BaseModel]] = {
        OBJECTIVE_DESIGN_SCHEMA_ID: LearningObjectiveDesignOutput,
        ASSESSMENT_DESIGN_SCHEMA_ID: AssessmentDesignOutput,
        PREREQUISITE_PROPOSAL_SCHEMA_ID: PrerequisiteProposalOutput,
        COURSE_PLANNING_SCHEMA_ID: CoursePlanningOutput,
        LESSON_PLANNING_SCHEMA_ID: LessonPlanningOutput,
    }
    for version in (
        INSTRUCTIONAL_DESIGN_STAGE_VERSION,
        INSTRUCTIONAL_DESIGN_STAGE_VERSION_V03,
        INSTRUCTIONAL_DESIGN_STAGE_VERSION_V031,
        INSTRUCTIONAL_DESIGN_STAGE_VERSION_V032,
        INSTRUCTIONAL_DESIGN_STAGE_VERSION_V033,
        INSTRUCTIONAL_DESIGN_STAGE_VERSION_V034,
    ):
        for schema_id, schema in structured_schema_by_id.items():
            schemas.register(schema_id, version, schema)
    schemas.register(
        ONE_SHOT_BASELINE_SCHEMA_ID,
        ONE_SHOT_BASELINE_SCHEMA_VERSION,
        OneShotInstructionalDesignOutput,
    )
    for prompt in instructional_design_experiment_prompt_templates(
        version=INSTRUCTIONAL_DESIGN_STAGE_VERSION
    ):
        prompts.register(prompt)
    for prompt in instructional_design_experiment_prompt_templates(
        version=INSTRUCTIONAL_DESIGN_STAGE_VERSION_V03
    ):
        if prompt.template_id != ONE_SHOT_BASELINE_SCHEMA_ID:
            prompts.register(prompt)
    for prompt in instructional_design_experiment_prompt_templates(
        version=INSTRUCTIONAL_DESIGN_STAGE_VERSION_V031
    ):
        if prompt.template_id != ONE_SHOT_BASELINE_SCHEMA_ID:
            prompts.register(prompt)
    for prompt in instructional_design_experiment_prompt_templates(
        version=INSTRUCTIONAL_DESIGN_STAGE_VERSION_V032
    ):
        if prompt.template_id != ONE_SHOT_BASELINE_SCHEMA_ID:
            prompts.register(prompt)
    for prompt in instructional_design_experiment_prompt_templates(
        version=INSTRUCTIONAL_DESIGN_STAGE_VERSION_V033
    ):
        if prompt.template_id != ONE_SHOT_BASELINE_SCHEMA_ID:
            prompts.register(prompt)
    for prompt in instructional_design_experiment_prompt_templates(
        version=INSTRUCTIONAL_DESIGN_STAGE_VERSION_V034
    ):
        if prompt.template_id != ONE_SHOT_BASELINE_SCHEMA_ID:
            prompts.register(prompt)
