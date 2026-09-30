from pydantic import BaseModel, ConfigDict, Field, model_validator


class CourseMetadataRevision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    title: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_changes(self) -> "CourseMetadataRevision":
        if self.title is None and self.description is None:
            raise ValueError("course_changes_required")
        return self


class ModuleTitleRevision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    module_order: int = Field(ge=1)
    title: str = Field(min_length=1)


class LessonTitleRevision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    module_order: int = Field(ge=1)
    lesson_order: int = Field(ge=1)
    title: str = Field(min_length=1)


class SectionRevision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    module_order: int = Field(ge=1)
    lesson_order: int = Field(ge=1)
    section_order: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1)
    content: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_changes(self) -> "SectionRevision":
        if self.title is None and self.content is None:
            raise ValueError("section_changes_required")
        return self


class AssessmentQuestionRevision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    question_index: int = Field(ge=0)
    prompt: str | None = Field(default=None, min_length=1)
    options: list[str] | None = None
    expected_answer: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_changes(self) -> "AssessmentQuestionRevision":
        if self.prompt is None and self.options is None and self.expected_answer is None:
            raise ValueError("assessment_changes_required")
        return self


class CourseDraftRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_result_ref: str = Field(min_length=1)
    change_summary: str = Field(min_length=1)
    course_changes: CourseMetadataRevision | None = None
    module_changes: list[ModuleTitleRevision] = Field(default_factory=list)
    lesson_changes: list[LessonTitleRevision] = Field(default_factory=list)
    section_changes: list[SectionRevision] = Field(default_factory=list)
    assessment_changes: list[AssessmentQuestionRevision] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_has_changes(self) -> "CourseDraftRevisionRequest":
        if not any((
            self.course_changes,
            self.module_changes,
            self.lesson_changes,
            self.section_changes,
            self.assessment_changes,
        )):
            raise ValueError("revision_changes_required")
        return self
