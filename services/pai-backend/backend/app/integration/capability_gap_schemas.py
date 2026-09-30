from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.course_authoring.learning_readiness import LearningReadinessProjection


class CapabilityAnalysisCreateV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    current_target_reference: str = Field(min_length=1, max_length=192)
    future_target_reference: str | None = Field(default=None, min_length=1, max_length=192)


class CapabilityGapSummaryV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    gap_count: int = Field(ge=0)
    warning_codes: list[str]
    provisional: Literal[True] = True


class CapabilityGapV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    gap_reference: str = Field(min_length=1)
    target_type: Literal["current_role", "future_role"]
    requirement_reference: str = Field(min_length=1)
    status: str = Field(min_length=1)
    priority: str = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    missing_signals: list[str]
    evidence_references: list[str]
    rationale: str = Field(min_length=1)
    verification_required: bool


class RecommendationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    recommendation_reference: str = Field(min_length=1)
    gap_reference: str = Field(min_length=1)
    title: str = Field(min_length=1)
    provisional: Literal[True] = True


class CapabilityCandidateReferenceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    candidate_id: UUID
    candidate_code: str
    display_name: str | None = None


class CapabilityCandidateProfileReferenceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    profile_id: str = Field(min_length=1)
    profile_version: int = Field(ge=1)
    governance_version: int | None = Field(default=None, ge=1)
    review_state: str = Field(min_length=1)


class CapabilityRoleReferenceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    role_id: UUID
    role_code: str
    title: str


class CapabilityRoleProfileReferenceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    profile_id: str = Field(min_length=1)
    profile_version: str = Field(min_length=1)
    governance_version: int | None = Field(default=None, ge=1)
    status: str = Field(min_length=1)


class HumanAssistedSelectionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    requirement_id: str = Field(min_length=1)
    selected_evidence_refs: list[str] = Field(min_length=1)


class HumanAssistedAnalysisV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    origin: Literal["HUMAN_ASSISTED_EVIDENCE"]
    source_analysis_id: str = Field(min_length=1)
    evidence_selections: list[HumanAssistedSelectionV1] = Field(min_length=1)


class CapabilityAnalysisProjectionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    analysis_id: str = Field(min_length=1)
    status: Literal["ready"]
    analysis_version: int = Field(ge=1)
    candidate_reference: UUID
    target_reference: str = Field(min_length=1)
    snapshot_schema_version: str = Field(min_length=1)
    summary: CapabilityGapSummaryV1
    gaps: list[CapabilityGapV1]
    recommendations: list[RecommendationV1]
    evidence_available: bool
    candidate: CapabilityCandidateReferenceV1 | None = None
    candidate_profile: CapabilityCandidateProfileReferenceV1 | None = None
    role: CapabilityRoleReferenceV1 | None = None
    role_profile: CapabilityRoleProfileReferenceV1 | None = None
    human_assisted: HumanAssistedAnalysisV1 | None = None
    review: "CapabilityGapReviewProjectionV1 | None" = None


class CandidateCapabilityAnalysisHistoryItemV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    analysis_id: str = Field(min_length=1)
    created_at: str | None = None
    analysis_version: int = Field(ge=1)
    status: str = Field(min_length=1)
    usage_mode: str = Field(min_length=1)
    candidate_profile_id: str = Field(min_length=1)
    candidate_profile_version: int = Field(ge=1)
    candidate_code: str | None = None
    candidate_display_name: str | None = None
    role_id: UUID | None = None
    role_code: str | None = None
    role_title: str | None = None
    role_profile_id: str = Field(min_length=1)
    role_profile_version: str = Field(min_length=1)
    readiness: "CapabilityReviewSummaryV1 | None" = None


class CandidateCapabilityAnalysisHistoryResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    items: list[CandidateCapabilityAnalysisHistoryItemV1]


class LearningDecisionProjectionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    analysis_id: str = Field(min_length=1)
    candidate: CapabilityCandidateReferenceV1 | None = None
    candidate_profile: CapabilityCandidateProfileReferenceV1 | None = None
    role: CapabilityRoleReferenceV1 | None = None
    role_profile: CapabilityRoleProfileReferenceV1 | None = None
    usage_mode: str = Field(min_length=1)
    learning_readiness: LearningReadinessProjection


class CapabilityReviewSummaryV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    total_assessments: int = Field(ge=0)
    matched: int = Field(ge=0)
    insufficient: int = Field(ge=0)
    requires_verification: int = Field(ge=0)
    context_mismatch: int = Field(ge=0)
    not_found_in_evidence: int = Field(ge=0)
    verification_queue_size: int = Field(ge=0)


class CapabilityReviewRequirementV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    statement: str = Field(min_length=1)
    criterion_dimension: str | None = None
    modality: str | None = None
    priority: str | None = None
    target_level: str | None = None
    observable_behaviors: list[str]


class CapabilityReviewDecisionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    reason_codes: list[str]
    explanation: str = Field(min_length=1)
    observed_confidence: float | None = Field(default=None, ge=0, le=1)
    required_confidence: float | None = Field(default=None, ge=0, le=1)
    evidence_directness: str | None = None
    verification_required: bool
    threshold_source: str


class CapabilityReviewVerificationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    required: bool
    state: str
    reason: str | None = None


class CapabilityReviewEvidenceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    reference: str = Field(min_length=1)
    excerpt: str | None = None
    section: str | None = None
    context: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class CapabilityReviewProvenanceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source_requirement_ref: str | None = None
    source_locator_display: str | None = None


class CapabilityAssessmentReviewItemV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    requirement_ref: str = Field(min_length=1)
    requirement: CapabilityReviewRequirementV1
    status: str = Field(min_length=1)
    candidate_evidence: list[CapabilityReviewEvidenceV1]
    decision: CapabilityReviewDecisionV1
    verification: CapabilityReviewVerificationV1
    role_provenance: CapabilityReviewProvenanceV1


class CapabilityGapReviewProjectionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    portfolio_id: str = Field(min_length=1)
    candidate_reference: UUID | None = None
    target_reference: str = Field(min_length=1)
    role_profile_state: str = Field(min_length=1)
    usage_mode: str = Field(min_length=1)
    warnings: list[str]
    summary: CapabilityReviewSummaryV1
    preview_readiness: dict[str, object] | None = None
    learning_readiness: LearningReadinessProjection
    assessments: list[CapabilityAssessmentReviewItemV1]
    verification_queue: list[dict[str, object]]


CapabilityAnalysisProjectionV1.model_rebuild()
CandidateCapabilityAnalysisHistoryItemV1.model_rebuild()
CandidateCapabilityAnalysisHistoryResponseV1.model_rebuild()


class CapabilityEvidenceItemV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    reference: str = Field(min_length=1)
    excerpt: str | None = None
    section: str | None = None
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=1)
    context: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class CapabilityEvidenceProjectionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    analysis_id: str = Field(min_length=1)
    gap_reference: str = Field(min_length=1)
    items: list[CapabilityEvidenceItemV1]


class CandidateEvidenceOptionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    evidence_ref: str = Field(min_length=1)
    evidence_type: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=256)
    source_label: str | None = Field(default=None, max_length=128)
    excerpt: str | None = Field(default=None, max_length=500)


class CandidateEvidenceProjectionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    analysis_id: str = Field(min_length=1)
    items: list[CandidateEvidenceOptionV1]
