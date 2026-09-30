from pydantic import BaseModel, ConfigDict, Field


class CourseGenerationAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    request_ref: str = Field(min_length=1)
    generation_run_ref: str = Field(min_length=1)
    result_ref: str = Field(min_length=1)
    status: str = Field(min_length=1)
    version: int = Field(ge=1)


class CourseGenerationProgressLesson(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    task_ref: str = Field(min_length=1)
    lesson_ref: str = Field(min_length=1)
    title: str = Field(min_length=1)
    module_order: int = Field(ge=1)
    lesson_order: int = Field(ge=1)
    status: str = Field(min_length=1)
    attempt_count: int = Field(ge=0)
    error_code: str | None = None


class CourseGenerationProgress(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    plan_ref: str = Field(min_length=1)
    request_ref: str = Field(min_length=1)
    generation_run_ref: str = Field(min_length=1)
    status: str = Field(min_length=1)
    total_lessons: int = Field(ge=0)
    succeeded_lessons: int = Field(ge=0)
    failed_lessons: int = Field(ge=0)
    pending_lessons: int = Field(ge=0)
    lessons: list[CourseGenerationProgressLesson]
    result_ref: str | None = None
