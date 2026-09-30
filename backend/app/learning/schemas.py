from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LearningPathStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    FAILED = "failed"


class LearningPathSourceType(StrEnum):
    VERIFIED = "verified"
    CAPABILITY_ANALYSIS = "capability_analysis"


class LearningObjectType(StrEnum):
    READING = "reading"
    VIDEO = "video"
    EXERCISE = "exercise"
    QUIZ = "quiz"
    PRACTICAL = "practical"
    CASE = "case"


class ProvenanceStatus(StrEnum):
    APPROVED = "approved"


class LearningPathRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: UUID
    target_profile_id: str = Field(min_length=1)
    target_profile_version: str = Field(min_length=1)
    preliminary_match_id: str = Field(min_length=1)
    verified_competency_record_ids: list[UUID] = Field(min_length=1)
    approved_gap_ids: list[str] = Field(min_length=1)
    development_goal: str = Field(min_length=1, max_length=500)
    target_completion_date: date
    correlation_id: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_date(self) -> "LearningPathRequest":
        if self.target_completion_date <= date.today():
            raise ValueError("target_completion_date must be in the future")
        return self


class CapabilityAnalysisLearningPathRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    capability_analysis_id: str = Field(min_length=1, max_length=128)
    development_goal: str = Field(min_length=1, max_length=500)
    target_completion_date: date

    @model_validator(mode="after")
    def validate_date(self) -> "CapabilityAnalysisLearningPathRequest":
        if self.target_completion_date <= date.today():
            raise ValueError("target_completion_date must be in the future")
        return self


class LearningPathLifecycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    expected_version: int = Field(ge=1)


class LearningObjective(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    learning_need_ref: str | None = Field(default=None, min_length=1)
    statement: str | None = Field(default=None, min_length=1)
    bloom_level: str | None = Field(default=None, min_length=1)
    evidence_required: list[str] | None = None
    competency_id: str = Field(min_length=1)
    current_level: int | None = Field(default=None, ge=1, le=5)
    target_level: int = Field(ge=1, le=5)
    measurable_outcome: str = Field(min_length=1)
    gap_id: str = Field(min_length=1)
    sequence: int = Field(ge=1)


class PrerequisiteNode(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    learning_object_id: str = Field(min_length=1)


class PrerequisiteEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    from_node_id: str = Field(min_length=1)
    to_node_id: str = Field(min_length=1)
    reason_reference: str = Field(default="catalog:prerequisite", min_length=1)


class LearningObjectMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    object_type: LearningObjectType
    title: str = Field(min_length=1)
    estimated_minutes: int = Field(gt=0)
    competency_id: str = Field(min_length=1)
    target_level: int = Field(ge=1, le=5)
    assessment_template_id: str = Field(min_length=1)
    assessment_template_version: str = Field(min_length=1)
    approved_source_reference: str = Field(min_length=1)
    provenance_status: Literal[ProvenanceStatus.APPROVED] = ProvenanceStatus.APPROVED


class Lesson(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    title: str = Field(min_length=1)
    objective_ids: list[str] = Field(min_length=1)
    learning_object_ids: list[str] = Field(min_length=1)


class LearningModule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    title: str = Field(min_length=1)
    objective_ids: list[str] = Field(min_length=1)
    lesson_ids: list[str] = Field(min_length=1)
    prerequisite_node_ids: list[str] = Field(default_factory=list)


class CourseBlueprint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    title: str = Field(min_length=1)
    objective_ids: list[str] = Field(min_length=1)
    module_ids: list[str] = Field(min_length=1)
    provenance_status: Literal[ProvenanceStatus.APPROVED] = ProvenanceStatus.APPROVED


class LearningPath(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str = Field(min_length=1)
    version: int = Field(ge=1)
    status: LearningPathStatus
    subject_id: UUID
    organization_id: UUID
    target_profile_id: str = Field(min_length=1)
    target_profile_version: str = Field(min_length=1)
    preliminary_match_id: str | None = None
    verified_competency_record_ids: list[UUID] = Field(default_factory=list)
    approved_gap_ids: list[str] = Field(min_length=1)
    development_goal: str = Field(min_length=1)
    target_completion_date: date
    objectives: list[LearningObjective] = Field(min_length=1)
    prerequisite_nodes: list[PrerequisiteNode] = Field(min_length=1)
    prerequisite_edges: list[PrerequisiteEdge] = Field(default_factory=list)
    learning_objects: list[LearningObjectMetadata] = Field(min_length=1)
    lessons: list[Lesson] = Field(min_length=1)
    modules: list[LearningModule] = Field(min_length=1)
    blueprints: list[CourseBlueprint] = Field(min_length=1)
    generator_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    created_by: UUID
    created_at: datetime
    source_type: LearningPathSourceType = LearningPathSourceType.VERIFIED
    capability_analysis_id: str | None = None
    capability_analysis_version: int | None = Field(default=None, ge=1)
    source_candidate_id: UUID | None = None
    source_profile_id: str | None = None
    source_profile_version: int | None = Field(default=None, ge=1)
    source_target_id: str | None = None
    source_target_version: str | None = None
    source_gap_ids: list[str] = Field(default_factory=list)
    source_evidence_refs: list[str] = Field(default_factory=list)
    source_recommendation_refs: list[str] = Field(default_factory=list)
    validation: "LearningPathValidation" = Field(default_factory=lambda: LearningPathValidation())
    reviewed: bool = False
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    reviewed_version: int | None = Field(default=None, ge=1)
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    approved_version: int | None = Field(default=None, ge=1)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)
    request_fingerprint: str | None = Field(default=None, min_length=1, max_length=128)
    is_stale: bool = False
    stale_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_review_metadata(self) -> "LearningPath":
        if self.reviewed and (self.reviewed_by is None or self.reviewed_at is None):
            raise ValueError("Reviewed path requires reviewer metadata")
        if self.reviewed_version is not None and self.reviewed_version != self.version:
            raise ValueError("Reviewed version must match the path version")
        if self.approved_by is not None and self.approved_at is None:
            raise ValueError("Approved path requires approval timestamp")
        if self.approved_version is not None and self.approved_version != self.version:
            raise ValueError("Approved version must match the path version")
        return self


class LearningPathValidationFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: Literal["error", "warning"] = "error"


class LearningPathValidation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    valid: bool = True
    ready_for_review: bool = True
    findings: list[LearningPathValidationFinding] = Field(default_factory=list)
