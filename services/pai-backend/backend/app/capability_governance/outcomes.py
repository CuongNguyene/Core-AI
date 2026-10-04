"""Source-owned course learning outcome contracts."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.capability_governance.identity import SourceSemanticKind, SourceSemanticRef


class CourseLearningOutcome(BaseModel):
    """An intended learning result explicitly represented by a course source."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    outcome_ref: SourceSemanticRef
    course_ref: str = Field(min_length=1, max_length=512)
    statement: str = Field(min_length=1, max_length=4000)
    source_locator: str = Field(min_length=1, max_length=2048)

    @field_validator("course_ref", "statement", "source_locator")
    @classmethod
    def reject_blank_or_surrounding_whitespace(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("outcome source text must be non-blank and exact")
        return value

    @field_validator("outcome_ref")
    @classmethod
    def require_course_outcome_identity(cls, value: SourceSemanticRef) -> SourceSemanticRef:
        if value.entity_kind is not SourceSemanticKind.COURSE_LEARNING_OUTCOME:
            raise ValueError("course_learning_outcome_ref_required")
        return value
