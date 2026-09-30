from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CompetencyEvidenceState(StrEnum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"
    CONFLICTING = "conflicting"


class CompetencyLevelStatus(StrEnum):
    UNKNOWN = "unknown"
    DECLARED = "declared"
    ASSESSED = "assessed"
    PENDING_VERIFICATION = "pending_verification"
    RETURNED_FOR_REVIEW = "returned_for_review"
    VERIFIED = "verified"
    EXPIRED = "expired"
    REVOKED = "revoked"
    REQUIRES_REASSESSMENT = "requires_reassessment"


class CompetencyHypothesis(BaseModel):
    subject_id: UUID
    competency_id: str
    target_level: int = Field(ge=1, le=5)
    estimated_level: int | None = Field(default=None, ge=1, le=5)
    evidence_state: CompetencyEvidenceState
    evidence_ids: list[UUID]
    confidence: float = Field(ge=0, le=1)
    assessment_required: bool
    recommended_assessment_type: str | None = None


class VerifiedCompetency(BaseModel):
    subject_id: UUID
    competency_id: str
    level: int = Field(ge=1, le=5)
    status: CompetencyLevelStatus
    evidence_ids: list[UUID]
    rubric_version: str
    verified_by: UUID
    confidence: float = Field(ge=0, le=1)


class CompetencyDecision(BaseModel):
    """Immutable decision contract; persistence and transitions follow separately."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID
    subject_id: UUID
    organization_id: UUID | None = None
    competency_id: str = Field(min_length=1)
    assessment_submission_id: UUID
    evidence_ids: list[UUID] = Field(min_length=1)
    rubric_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    previous_status: CompetencyLevelStatus = CompetencyLevelStatus.UNKNOWN
    status: CompetencyLevelStatus
    decided_by: UUID | None = None
    delegation_id: UUID | None = None
    valid_until: datetime
    reassessment_due_at: datetime

    @model_validator(mode="after")
    def validate_reassessment_window(self) -> "CompetencyDecision":
        if self.reassessment_due_at >= self.valid_until:
            raise ValueError("Reassessment must be due before competency validity ends")
        return self


class CompetencyRecord(BaseModel):
    """Current derived state; the supporting decision history is immutable."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID
    subject_id: UUID
    organization_id: UUID
    competency_id: str = Field(min_length=1)
    status: CompetencyLevelStatus
    level: int | None = Field(default=None, ge=1, le=5)
    version: int = Field(ge=1)
    last_decision_id: UUID | None = None
    valid_until: datetime | None = None
    reassessment_due_at: datetime | None = None
