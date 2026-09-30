from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.content_generation.schemas import GeneratedLessonDraft
from app.curriculum_planning.schemas import CurriculumPlan


class CourseGenerationPlanStatus(StrEnum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    PARTIAL = "PARTIAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class LessonGenerationTaskStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class CourseModulePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    title: str = Field(min_length=1)
    order: int = Field(ge=1)
    lesson_refs: list[str] = Field(min_length=1)
    estimated_hours: float | None = Field(default=None, gt=0)


class CourseLessonPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    lesson_ref: str = Field(min_length=1)
    module_order: int = Field(ge=1)
    lesson_order: int = Field(ge=1)
    title: str = Field(min_length=1)
    objective_refs: list[str] = Field(default_factory=list)
    estimated_minutes: int | None = Field(default=None, gt=0)
    lesson_type: str | None = Field(default=None, min_length=1)
    workload_category: str | None = Field(default=None, min_length=1)
    estimated_instruction_minutes: int | None = Field(default=None, ge=0)
    estimated_practice_minutes: int | None = Field(default=None, ge=0)
    estimated_total_effort_minutes: int | None = Field(default=None, gt=0)


class LessonGenerationTask(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    plan_ref: str = Field(min_length=1)
    lesson_ref: str = Field(min_length=1)
    module_order: int = Field(ge=1)
    lesson_order: int = Field(ge=1)
    lesson_title: str = Field(min_length=1)
    objective_refs: list[str] = Field(default_factory=list)
    status: LessonGenerationTaskStatus = LessonGenerationTaskStatus.PENDING
    attempt_count: int = Field(default=0, ge=0)
    latest_run_ref: str | None = Field(default=None, min_length=1)
    generated_lesson: GeneratedLessonDraft | None = None
    error_code: str | None = Field(default=None, min_length=1)
    created_at: datetime
    updated_at: datetime


class CourseGenerationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    authoring_request_ref: str = Field(min_length=1)
    parent_run_ref: str = Field(min_length=1)
    course_title: str = Field(min_length=1)
    course_description_context: str = Field(min_length=1)
    module_plans: list[CourseModulePlan] = Field(min_length=1)
    lesson_descriptors: list[CourseLessonPlan] = Field(min_length=1)
    language: str | None = Field(default=None, min_length=1)
    duration_constraint: str | None = Field(default=None, min_length=1)
    prompt_version: str = Field(min_length=1)
    quality_policy_version: str = Field(min_length=1)
    curriculum_plan_ref: str | None = Field(default=None, min_length=1)
    curriculum_plan: CurriculumPlan | None = None
    status: CourseGenerationPlanStatus = CourseGenerationPlanStatus.PLANNED
    created_at: datetime
