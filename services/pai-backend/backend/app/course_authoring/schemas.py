from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AudienceSnapshotSource(StrEnum):
    MANUAL_SELECTION = "MANUAL_SELECTION"


class CourseAuthoringMode(StrEnum):
    GAP_DRIVEN = "GAP_DRIVEN"
    GOAL_DRIVEN = "GOAL_DRIVEN"


class CourseAuthoringStatus(StrEnum):
    DRAFT = "DRAFT"


class TrainingBrief(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    goal: str
    language: str | None = None
    target_completion_context: str | None = None
    duration_constraint: str | None = None
    notes: str | None = None
    desired_outcomes: tuple[str, ...] = Field(default_factory=tuple)
    prerequisites: tuple[str, ...] = Field(default_factory=tuple)
    learning_horizon: str | None = None
    expected_learning_effort: str | None = None

    @field_validator("goal")
    @classmethod
    def validate_goal(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("training_goal_required")
        return value


class AudienceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    learner_refs: tuple[str, ...] = Field(min_length=0)
    learner_count: int = Field(ge=0)
    captured_at: datetime
    source: AudienceSnapshotSource
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("audience_snapshot_id_required")
        return value

    @field_validator("learner_refs", mode="before")
    @classmethod
    def coerce_learner_refs(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @field_validator("learner_refs", mode="after")
    @classmethod
    def validate_learner_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not learner_ref.strip() for learner_ref in value):
            raise ValueError("learner_reference_required")
        if len(value) != len(set(value)):
            raise ValueError("duplicate_learner_reference")
        return value

    @model_validator(mode="after")
    def validate_count(self) -> "AudienceSnapshot":
        if self.learner_count != len(self.learner_refs):
            raise ValueError("audience_learner_count_mismatch")
        return self


def _validate_reference_list(value: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if any(not reference.strip() for reference in value):
        raise ValueError(f"{field_name}_reference_required")
    if len(value) != len(set(value)):
        raise ValueError(f"duplicate_{field_name}_reference")
    return value


class CourseAuthoringRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    title: str
    training_brief: TrainingBrief
    learner_refs: tuple[str, ...] = Field(min_length=0)
    learning_need_refs: tuple[str, ...] = Field(default_factory=tuple)
    objective_refs: tuple[str, ...] = Field(default_factory=tuple)
    instructional_blueprint_ref: str | None = None
    constraints: dict[str, str] = Field(default_factory=dict)
    mode: CourseAuthoringMode = CourseAuthoringMode.GOAL_DRIVEN

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("course_authoring_title_required")
        return value

    @field_validator("learner_refs", "learning_need_refs", "objective_refs", mode="before")
    @classmethod
    def coerce_reference_lists(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @field_validator("learner_refs")
    @classmethod
    def validate_learner_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_reference_list(value, "learner")

    @field_validator("learning_need_refs")
    @classmethod
    def validate_learning_need_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_reference_list(value, "learning_need")

    @field_validator("objective_refs")
    @classmethod
    def validate_objective_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_reference_list(value, "objective")

    @field_validator("instructional_blueprint_ref")
    @classmethod
    def validate_blueprint_ref(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("instructional_blueprint_reference_required")
        return value

    @model_validator(mode="after")
    def validate_mode(self) -> "CourseAuthoringRequestCreate":
        if self.mode is CourseAuthoringMode.GAP_DRIVEN and not (
            self.learning_need_refs
            or self.objective_refs
            or self.instructional_blueprint_ref
        ):
            raise ValueError("gap_driven_reference_required")
        return self


class CourseAuthoringRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    title: str
    training_brief: TrainingBrief
    audience_snapshot: AudienceSnapshot
    learning_need_refs: tuple[str, ...] = Field(default_factory=tuple)
    objective_refs: tuple[str, ...] = Field(default_factory=tuple)
    instructional_blueprint_ref: str | None = None
    constraints: dict[str, str] = Field(default_factory=dict)
    mode: CourseAuthoringMode
    status: CourseAuthoringStatus
    authoring_workflow_version: str | None = None
    created_by_actor_ref: UUID
    created_at: datetime


class CourseAuthoringRequestAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    request_id: str = Field(min_length=1)
    status: CourseAuthoringStatus
    audience_snapshot_id: str = Field(min_length=1)
