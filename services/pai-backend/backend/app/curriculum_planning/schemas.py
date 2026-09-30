from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.course_authoring.schemas import CourseAuthoringMode
from app.learning_authoring.schemas import InstructionalBlueprintProjection

from .duration import NormalizedTrainingDuration


class CurriculumPlanStatus(StrEnum):
    PLANNED = "PLANNED"
    VALIDATED = "VALIDATED"
    SUPERSEDED = "SUPERSEDED"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    NEEDS_REVISION = "NEEDS_REVISION"
    READY_FOR_CONFIRMATION = "READY_FOR_CONFIRMATION"
    CONFIRMED = "CONFIRMED"


class LessonWorkloadCategory(StrEnum):
    FOUNDATION = "FOUNDATION"
    CONCEPT = "CONCEPT"
    APPLIED = "APPLIED"
    PRACTICE = "PRACTICE"
    INTEGRATION = "INTEGRATION"
    ASSESSMENT = "ASSESSMENT"
    CAPSTONE = "CAPSTONE"


class CurriculumObjective(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    measurable_outcome: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    origin: str = Field(min_length=1)


class CurriculumLessonPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    order: int = Field(ge=1)
    objective_refs: list[str] = Field(min_length=1)
    estimated_minutes: int = Field(gt=0)
    lesson_type: str = Field(min_length=1)
    workload_category: LessonWorkloadCategory | None = None
    estimated_instruction_minutes: int | None = Field(default=None, ge=0)
    estimated_practice_minutes: int | None = Field(default=None, ge=0)
    estimated_total_effort_minutes: int | None = Field(default=None, gt=0)


class CurriculumModulePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    order: int = Field(ge=1)
    objective_refs: list[str] = Field(min_length=1)
    estimated_hours: float = Field(gt=0)
    lessons: list[CurriculumLessonPlan] = Field(min_length=1)


class CurriculumPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    authoring_request_ref: str = Field(min_length=1)
    version: int = Field(ge=1)
    supersedes_plan_ref: str | None = Field(default=None, min_length=1)
    course_title: str = Field(min_length=1)
    course_description: str = Field(min_length=1)
    normalized_duration: NormalizedTrainingDuration
    learning_objectives: list[CurriculumObjective] = Field(min_length=1)
    modules: list[CurriculumModulePlan] = Field(min_length=1)
    estimated_total_learning_hours: float = Field(gt=0)
    planning_metadata: dict[str, str] = Field(default_factory=dict)
    status: CurriculumPlanStatus = CurriculumPlanStatus.PLANNED


class CurriculumPlanningContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    authoring_request_ref: str = Field(min_length=1)
    mode: CourseAuthoringMode
    course_title: str = Field(min_length=1)
    training_goal: str = Field(min_length=1)
    language: str | None = Field(default=None, min_length=1)
    audience_summary: dict[str, object]
    duration: NormalizedTrainingDuration
    target_completion_context: str | None = Field(default=None, min_length=1)
    existing_learning_objectives: list[CurriculumObjective] = Field(default_factory=list)
    learning_need_refs: list[str] = Field(default_factory=list)
    instructional_blueprint_ref: str | None = Field(default=None, min_length=1)
    instructional_blueprint: InstructionalBlueprintProjection | None = None
    learning_horizon: str | None = Field(default=None, min_length=1)
    expected_learning_effort: str | None = Field(default=None, min_length=1)
    planning_strategy: str = "legacy"


class CurriculumPlanProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    plan_ref: str = Field(min_length=1)
    status: CurriculumPlanStatus
    duration: NormalizedTrainingDuration
    objective_count: int = Field(ge=0)
    module_count: int = Field(ge=0)
    lesson_count: int = Field(ge=0)
    objectives: list[CurriculumObjective]
    modules: list[CurriculumModulePlan]
    planning_metadata: dict[str, str] = Field(default_factory=dict)


class CurriculumObjectiveDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    statement: str = Field(min_length=1)
    measurable_outcome: str = Field(min_length=1)
    sequence: int = Field(ge=1)


class CurriculumLessonDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    title: str = Field(min_length=1)
    order: int = Field(ge=1)
    objective_refs: list[str] = Field(min_length=1)
    estimated_minutes: int = Field(gt=0)
    lesson_type: str = Field(min_length=1)


class CurriculumModuleDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    title: str = Field(min_length=1)
    order: int = Field(ge=1)
    objective_refs: list[str] = Field(min_length=1)
    estimated_hours: float = Field(gt=0)
    lessons: list[CurriculumLessonDraft] = Field(min_length=1)


class CurriculumPlanningOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    objectives: list[CurriculumObjectiveDraft] = Field(min_length=1)
    modules: list[CurriculumModuleDraft] = Field(min_length=1)
    estimated_total_learning_hours: float = Field(gt=0)


class CurriculumPlanValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    path: str = Field(min_length=1)
    actual: Any = None
    expected: Any = None
    objective_ref: str | None = None
    module_ref: str | None = None
    lesson_ref: str | None = None


class CurriculumPlanValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    valid: bool
    issues: list[CurriculumPlanValidationIssue]
    objective_count: int = Field(ge=0)
    module_count: int = Field(ge=0)
    lesson_count: int = Field(ge=0)
    estimated_total_hours: float | None = Field(default=None, ge=0)
    covered_objective_count: int = Field(ge=0)
    uncovered_objective_refs: list[str]
    unknown_objective_refs: list[str]

    @property
    def issue_codes(self) -> list[str]:
        return list(dict.fromkeys(issue.code for issue in self.issues))
