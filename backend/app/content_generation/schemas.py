from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.curriculum_planning.duration import NormalizedTrainingDuration, WeeklyEffortSource
from app.curriculum_planning.schemas import CurriculumPlanValidationIssue

NonEmptyReference = Annotated[str, Field(min_length=1)]


class ContentGenerationType(StrEnum):
    LESSON_CONTENT = "lesson_content"


class ContentGenerationStatus(StrEnum):
    CREATED = "CREATED"
    GENERATING = "GENERATING"
    DRAFT = "DRAFT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    APPROVED = "APPROVED"
    SUPERSEDED = "SUPERSEDED"
    IN_REVIEW = "IN_REVIEW"
    REJECTED = "REJECTED"
    READY_FOR_MATERIALIZATION = "READY_FOR_MATERIALIZATION"


class ContentSectionType(StrEnum):
    INTRODUCTION = "introduction"
    CONCEPT = "concept"
    EXAMPLE = "example"
    GUIDED_PRACTICE = "guided_practice"
    INDEPENDENT_PRACTICE = "independent_practice"
    SUMMARY = "summary"


class AssessmentQuestionType(StrEnum):
    MULTIPLE_CHOICE = "multiple_choice"
    SHORT_ANSWER = "short_answer"


class GenerationRunStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class LessonValidationDiagnosticStatus(StrEnum):
    REJECTED = "REJECTED"


class CurriculumPlanningAttemptStatus(StrEnum):
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class GenerationMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    prompt_version: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    provider: str | None = Field(default=None, min_length=1)
    created_at: datetime | None = None
    generation_run_id: str | None = Field(default=None, min_length=1)
    curriculum_plan_ref: str | None = Field(default=None, min_length=1)
    curriculum_plan_version: int | None = Field(default=None, ge=1)


class GenerationRun(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    run_id: NonEmptyReference
    request_ref: NonEmptyReference
    parent_run_ref: NonEmptyReference | None = None
    unit_type: str | None = Field(default=None, min_length=1)
    unit_ref: str | None = Field(default=None, min_length=1)
    generation_mode: str = Field(default="INITIAL", min_length=1)
    repair_source_diagnostic_ref: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    prompt_version: str | None = Field(default=None, min_length=1)
    provider: str | None = Field(default=None, min_length=1)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    status: GenerationRunStatus = GenerationRunStatus.SUCCEEDED
    error_code: str | None = Field(default=None, min_length=1)


class LessonValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    code: str = Field(min_length=1)
    path: str = Field(min_length=1)
    message: str = Field(min_length=1)
    actual: str | int | list[str] | list[int] | None = None
    expected: str | int | list[str] | list[int] | None = None


class LessonValidationSectionMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    section_type: str = Field(min_length=1)
    content_words: int = Field(ge=0)
    steps_words: int = Field(ge=0)
    success_criteria_words: int = Field(ge=0)
    effective_words: int = Field(ge=0)
    validation_words: int | None = Field(default=None, ge=0)
    threshold: int | None = Field(default=None, ge=0)


class LessonAssessmentValidationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    present: bool
    question_count: int = Field(ge=0)
    multiple_choice_count: int = Field(ge=0)
    short_answer_count: int = Field(ge=0)
    objective_refs: list[str]
    invalid_objective_refs: list[str]
    mcq_invalid_count: int = Field(ge=0)
    missing_answer_count: int = Field(ge=0)


class LessonValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    valid: bool
    issues: list[LessonValidationIssue]
    section_metrics: list[LessonValidationSectionMetrics]
    assessment_summary: LessonAssessmentValidationSummary

    @property
    def issue_codes(self) -> list[str]:
        return list(dict.fromkeys(issue.code for issue in self.issues))


class LessonValidationDiagnostic(BaseModel):
    """Rejected parsed lesson output retained for deterministic diagnostics only."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: NonEmptyReference
    authoring_request_ref: NonEmptyReference
    plan_ref: NonEmptyReference
    task_ref: NonEmptyReference
    lesson_ref: NonEmptyReference
    attempt: int = Field(ge=1)
    generation_run_ref: NonEmptyReference
    provider: NonEmptyReference
    model: NonEmptyReference
    prompt_version: NonEmptyReference
    created_at: datetime
    status: LessonValidationDiagnosticStatus = LessonValidationDiagnosticStatus.REJECTED
    sanitized_parsed_draft: dict[str, object]
    validation_issues: list[LessonValidationIssue]
    section_metrics: list[LessonValidationSectionMetrics]
    assessment_summary: LessonAssessmentValidationSummary

    @property
    def issue_codes(self) -> list[str]:
        return list(dict.fromkeys(issue.code for issue in self.validation_issues))


class CurriculumPlanningAttempt(BaseModel):
    """Diagnostic artifact for a parsed plan rejected before official persistence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: NonEmptyReference
    authoring_request_ref: NonEmptyReference
    correlation_id: NonEmptyReference
    provider: NonEmptyReference
    model: NonEmptyReference
    prompt_id: NonEmptyReference
    prompt_version: NonEmptyReference
    created_at: datetime
    completed_at: datetime
    status: CurriculumPlanningAttemptStatus
    original_duration_constraint: str | None = None
    normalized_duration: NormalizedTrainingDuration
    weekly_effort_hours: float | None = Field(default=None, gt=0)
    weekly_effort_source: WeeklyEffortSource
    estimated_total_learning_hours: float | None = Field(default=None, gt=0)
    min_modules: int = Field(ge=0)
    max_modules: int = Field(ge=0)
    min_lessons: int = Field(ge=0)
    max_lessons: int = Field(ge=0)
    objective_count: int = Field(ge=0)
    module_count: int = Field(ge=0)
    lesson_count: int = Field(ge=0)
    estimated_candidate_hours: float | None = Field(default=None, ge=0)
    covered_objective_count: int = Field(ge=0)
    validation_issues: list[CurriculumPlanValidationIssue]
    uncovered_objective_refs: list[str]
    unknown_objective_refs: list[str]
    sanitized_parsed_candidate: dict[str, object]

    @property
    def issue_codes(self) -> list[str]:
        return list(dict.fromkeys(issue.code for issue in self.validation_issues))


class RevisionMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    revision_id: NonEmptyReference
    result_ref: NonEmptyReference
    editor_actor_ref: NonEmptyReference
    created_at: datetime
    change_summary: NonEmptyReference
    source_version: int = Field(ge=1)


class ContentGenerationConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    language: str | None = Field(default=None, min_length=1)
    target_level: int | None = Field(default=None, ge=1, le=5)


class ContentGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: NonEmptyReference
    blueprint_ref: NonEmptyReference
    lesson_ref: NonEmptyReference
    objective_refs: list[NonEmptyReference] = Field(min_length=1)
    learning_need_refs: list[NonEmptyReference] = Field(default_factory=list)
    generation_type: ContentGenerationType
    constraints: ContentGenerationConstraints = Field(
        default_factory=ContentGenerationConstraints
    )
    generation_metadata: GenerationMetadata = Field(default_factory=GenerationMetadata)

    @model_validator(mode="after")
    def validate_objective_references(self) -> "ContentGenerationRequest":
        if len(self.objective_refs) != len(set(self.objective_refs)):
            raise ValueError("duplicate_objective_reference")
        return self


class ContentSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    type: ContentSectionType
    title: NonEmptyReference
    content: str = ""
    order: int = Field(ge=1)


class GeneratedCourse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    title: NonEmptyReference
    description: str = Field(min_length=1)


class GeneratedCourseSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    type: ContentSectionType
    title: NonEmptyReference
    content: str = Field(min_length=1)
    order: int = Field(ge=1)
    steps: list[NonEmptyReference] = Field(default_factory=list)
    success_criteria: list[NonEmptyReference] = Field(default_factory=list)


class GoalDerivedLearningObjective(BaseModel):
    """Training-brief-derived artifact; not a canonical capability objective."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: NonEmptyReference
    statement: NonEmptyReference
    measurable_outcome: NonEmptyReference | None = None
    sequence: int = Field(ge=1)
    origin: Literal["GOAL_DRIVEN_TRAINING_BRIEF"]


class GeneratedCourseLesson(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    lesson_ref: NonEmptyReference | None = None
    title: NonEmptyReference
    order: int = Field(ge=1)
    objective_refs: list[NonEmptyReference] = Field(default_factory=list)
    sections: list[GeneratedCourseSection] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_section_order(self) -> "GeneratedCourseLesson":
        orders = [section.order for section in self.sections]
        if orders != list(range(1, len(orders) + 1)):
            raise ValueError("invalid_lesson_section_order")
        return self


class GeneratedCourseModule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    title: NonEmptyReference
    order: int = Field(ge=1)
    lessons: list[GeneratedCourseLesson] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_lesson_order(self) -> "GeneratedCourseModule":
        orders = [lesson.order for lesson in self.lessons]
        if orders != list(range(1, len(orders) + 1)):
            raise ValueError("invalid_lesson_order")
        return self


class AssessmentQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    prompt: NonEmptyReference
    question_type: AssessmentQuestionType
    options: list[NonEmptyReference] = Field(default_factory=list)
    expected_answer: NonEmptyReference
    objective_refs: list[NonEmptyReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_question_shape(self) -> "AssessmentQuestion":
        if self.question_type is AssessmentQuestionType.MULTIPLE_CHOICE:
            if len(self.options) < 3 or len(self.options) != len(set(self.options)):
                raise ValueError("multiple_choice_options_required")
            if self.expected_answer not in self.options:
                raise ValueError("multiple_choice_answer_must_be_an_option")
        elif self.options:
            raise ValueError("short_answer_options_not_supported")
        return self


class GeneratedAssessmentDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    questions: list[AssessmentQuestion] = Field(min_length=1)


class GeneratedLessonDraft(BaseModel):
    """One independently generated lesson and its lesson-scoped assessment."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    lesson_ref: NonEmptyReference
    lesson: GeneratedCourseLesson
    assessment: GeneratedAssessmentDraft | None = None


class LessonAssessmentDraft(BaseModel):
    """Explicit lesson-to-assessment mapping for assembled course drafts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    lesson_ref: NonEmptyReference
    assessment: GeneratedAssessmentDraft


class GeneratedCourseDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    course: GeneratedCourse
    modules: list[GeneratedCourseModule] = Field(min_length=1)
    assessment: GeneratedAssessmentDraft | None = None
    lesson_assessments: list[LessonAssessmentDraft] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_module_order(self) -> "GeneratedCourseDraft":
        orders = [module.order for module in self.modules]
        if orders != list(range(1, len(orders) + 1)):
            raise ValueError("invalid_module_order")
        return self


class ContentGenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: NonEmptyReference
    request_ref: NonEmptyReference
    lesson_ref: NonEmptyReference | None = None
    objective_refs: list[NonEmptyReference] = Field(default_factory=list)
    generated_objectives: list[GoalDerivedLearningObjective] = Field(default_factory=list)
    learning_need_refs: list[NonEmptyReference] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)
    supersedes_result_ref: NonEmptyReference | None = None
    status: ContentGenerationStatus
    sections: list[ContentSection] = Field(default_factory=list)
    generation_metadata: GenerationMetadata = Field(default_factory=GenerationMetadata)
    generation_run: GenerationRun | None = None
    source_blueprint_ref: NonEmptyReference | None = None
    course_authoring_request_ref: NonEmptyReference | None = None
    generated_course: GeneratedCourseDraft | None = None
    revision_metadata: RevisionMetadata | None = None
    created_at: datetime | None = None

    @model_validator(mode="after")
    def validate_section_order(self) -> "ContentGenerationResult":
        orders = [section.order for section in self.sections]
        if orders != list(range(1, len(orders) + 1)):
            raise ValueError("invalid_section_order")
        return self
