from typing import Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class IntegrationEnvelopeV1[T](BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["v1"]
    data: T


class CourseBlueprintObjective(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective_ref: str = Field(min_length=1)
    title: str = Field(min_length=1)
    sequence: int = Field(ge=1)


class CourseBlueprintLesson(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lesson_ref: str = Field(min_length=1)
    title: str = Field(min_length=1)
    order: int = Field(ge=1)
    delivery_type: str = Field(min_length=1)
    estimated_duration_minutes: int | None = Field(default=None, gt=0)
    objective_refs: list[str]
    content_reference: str | None = None


class CourseBlueprintModule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_ref: str = Field(min_length=1)
    title: str = Field(min_length=1)
    order: int = Field(ge=1)
    lessons: list[CourseBlueprintLesson]


class AssessmentBlueprintReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_id: str = Field(min_length=1)
    version: str = Field(min_length=1)


class CourseBlueprintV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blueprint_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    title: str = Field(min_length=1)
    summary: str | None = None
    estimated_duration_minutes: int | None = Field(default=None, gt=0)
    objectives: list[CourseBlueprintObjective]
    modules: list[CourseBlueprintModule]
    assessment_references: list[AssessmentBlueprintReference]


class LearnerReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_user_id: str = Field(min_length=1)
    source_system: Literal["LMS"]


class CourseReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: str = Field(min_length=1)


class ActivityReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_id: str = Field(min_length=1)
    activity_type: Literal["COURSE_COMPLETION", "LESSON_COMPLETION", "ASSESSMENT_COMPLETION"]


class AssessmentSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float


class LearningResultRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_id: str = Field(min_length=1)
    learner_reference: LearnerReference
    course_reference: CourseReference
    activity_reference: ActivityReference
    completion_status: Literal["COMPLETED"]
    assessment_summary: AssessmentSummary | None = None


class LearningResultAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ACCEPTED"]
    evaluation_reference: str = Field(min_length=1)


class CompetencyResultReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["PENDING", "ACCEPTED"]
    evaluation_reference: str = Field(min_length=1)
