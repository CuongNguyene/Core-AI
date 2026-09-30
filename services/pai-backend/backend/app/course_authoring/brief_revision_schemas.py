from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AuthoringBriefRevisionStatus(StrEnum):
    DRAFT = "DRAFT"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    READY_FOR_CONFIRMATION = "READY_FOR_CONFIRMATION"
    CONFIRMED = "CONFIRMED"


class BriefRevisionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    training_goal: str = Field(min_length=1)
    audience_summary: dict[str, object] = Field(default_factory=dict)
    desired_outcomes: tuple[str, ...] = Field(default_factory=tuple)
    prerequisites: tuple[str, ...] = Field(default_factory=tuple)
    constraints: dict[str, str] = Field(default_factory=dict)
    learning_horizon: str | None = None
    expected_learning_effort: str | None = None
    excluded_scope: tuple[str, ...] = Field(default_factory=tuple)
    emphasis: tuple[str, ...] = Field(default_factory=tuple)
    legacy_duration_constraint: str | None = None


class ClarificationItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    code: str = Field(min_length=1)
    field: str = Field(min_length=1)
    question: str = Field(min_length=1)
    required: bool = True


class BriefClarificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    readiness: str
    questions: tuple[ClarificationItem, ...] = Field(default_factory=tuple)
    assumptions: tuple[str, ...] = Field(default_factory=tuple)
    ambiguities: tuple[str, ...] = Field(default_factory=tuple)
    scope_risks: tuple[str, ...] = Field(default_factory=tuple)
    duration_risks: tuple[str, ...] = Field(default_factory=tuple)

    @property
    def issue_codes(self) -> list[str]:
        return [item.code for item in self.questions]


class BriefRevisionChanges(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    training_goal: str | None = None
    desired_outcomes: tuple[str, ...] | None = None
    prerequisites: tuple[str, ...] | None = None
    constraints: dict[str, str] | None = None
    learning_horizon: str | None = None
    expected_learning_effort: str | None = None
    excluded_scope: tuple[str, ...] | None = None
    emphasis: tuple[str, ...] | None = None
    author_feedback: str | None = None

    @model_validator(mode="after")
    def has_changes(self) -> "BriefRevisionChanges":
        if not any(value is not None for value in self.model_dump().values()):
            raise ValueError("revision_changes_required")
        return self


class AuthoringBriefRevision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    status: AuthoringBriefRevisionStatus
    payload: BriefRevisionPayload
    clarification: BriefClarificationResult = Field(
        default_factory=lambda: BriefClarificationResult(readiness="UNKNOWN")
    )
    author_feedback: str | None = None
    supersedes_revision_id: str | None = None
    confirmed_at: datetime | None = None
    confirmed_by: UUID | None = None
    created_at: datetime
    created_by: UUID
