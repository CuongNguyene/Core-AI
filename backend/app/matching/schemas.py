from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.capability_analysis.domain_packs.contracts import DomainPackReference
from app.extraction.schemas import NativePdfLocator, SourceLocator
from app.semantic_policy.schemas import SemanticPolicyRef


class RequirementClassification(StrEnum):
    LEGAL_MANDATORY = "legal_mandatory"
    ROLE_CRITICAL = "role_critical"
    TRAINABLE_MANDATORY = "trainable_mandatory"
    PREFERRED = "preferred"
    OPTIONAL = "optional"
    UNCLASSIFIED = "unclassified"


class CriterionDimension(StrEnum):
    SKILL = "skill"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    CREDENTIAL = "credential"
    QUALIFICATION = "qualification"


class CriterionStatus(StrEnum):
    MATCHED = "matched"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"
    CONFLICTING = "conflicting"


class RoleProfileStatus(StrEnum):
    DRAFT = "draft"
    PROVISIONAL = "provisional"
    ACTIVE = "active"
    RETIRED = "retired"


class MandatoryStatus(StrEnum):
    SATISFIED = "satisfied"
    UNRESOLVED = "unresolved"
    NOT_MANDATORY = "not_mandatory"


class PreliminaryMatchStatus(StrEnum):
    CREATED = "created"
    COMPLETED = "completed"
    REVIEWED = "reviewed"
    SUPERSEDED = "superseded"
    FAILED = "failed"


class SemanticPolicySelectionSource(StrEnum):
    PROFILE_METADATA = "profile_metadata"
    LEGACY_PROFILE_VERSION_MAPPING = "legacy_profile_version_mapping"


class RoleProfileSemanticPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    core_version: str = Field(min_length=1)
    pack_refs: tuple[DomainPackReference, ...] = Field(min_length=1)

    @field_validator("pack_refs", mode="before")
    @classmethod
    def accept_explicit_pack_reference_objects(cls, value: object) -> object:
        if not isinstance(value, (list, tuple)):
            return value
        return tuple(
            DomainPackReference(
                pack_id=item["pack_id"],
                version=item["version"],
            )
            if isinstance(item, dict)
            and isinstance(item.get("pack_id"), str)
            and isinstance(item.get("version"), str)
            else item
            for item in value
        )


class RoleProfileSemanticPolicyMapping(RoleProfileSemanticPolicy):
    role_profile_id: str = Field(min_length=1)
    role_profile_version: str = Field(min_length=1)
    selection_source: Literal[
        SemanticPolicySelectionSource.LEGACY_PROFILE_VERSION_MAPPING
    ] = SemanticPolicySelectionSource.LEGACY_PROFILE_VERSION_MAPPING


class RoleRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    criterion_dimension: CriterionDimension | None = None
    classification: RequirementClassification
    evidence_terms: list[str] = Field(min_length=1)
    conflicting_terms: list[str] = Field(default_factory=list)
    confidence_threshold: float = Field(ge=0, le=1)
    assessment_recommendation: str = Field(min_length=1)
    rubric_version: str = Field(min_length=1)
    priority: str | None = None
    target_level: str | None = None
    observable_behaviors: list[str] = Field(default_factory=list)
    evidence_constraints: list[str] = Field(default_factory=list)
    provenance: dict[str, str] = Field(default_factory=dict)
    modality: str | None = None
    logical_group: str | None = None
    logical_operator: Literal["AND", "OR"] = "AND"
    evidence_expectation: Literal[
        "demonstrated_usage", "education", "credential", "owned_outcome", "unknown"
    ] | None = None
    threshold_source: str = "policy_default"
    threshold_policy_id: str | None = "capability-assessment-default"
    threshold_policy_version: str | None = "1"
    source_locator: SourceLocator | NativePdfLocator | None = None
    source_requirement_ref: str | None = None


class RoleCompetencyProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    status: RoleProfileStatus
    source_jd_profile_id: str = Field(min_length=1)
    source_jd_profile_version: int = Field(ge=1)
    rule_set_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    requirements: list[RoleRequirement] = Field(min_length=1)
    semantic_policy_ref: SemanticPolicyRef | None = None
    semantic_policy: RoleProfileSemanticPolicy | None = None
    role_id: UUID | None = None
    role_jd_version_id: UUID | None = None
    governance_version: int | None = Field(default=None, ge=1)


class ActivateRoleCompetencyProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    governance_version: int = Field(ge=1)


class RoleCompetencyProfileHistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    profile_id: str = Field(min_length=1)
    profile_version: str = Field(min_length=1)
    governance_version: int | None = Field(default=None, ge=1)
    status: RoleProfileStatus
    is_active: bool
    role_jd_version_id: UUID | None = None


class SourceEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    evidence_id: str = Field(min_length=1)
    source_locator: SourceLocator
    confidence: float = Field(ge=0, le=1)


class EvidenceAllocation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    evidence_id: str = Field(min_length=1)
    requirement_id: str = Field(min_length=1)


class CriterionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    requirement_id: str = Field(min_length=1)
    criterion_dimension: CriterionDimension
    classification: RequirementClassification
    status: CriterionStatus
    source_evidence: list[SourceEvidence]
    reused_evidence_ids: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    mandatory_status: MandatoryStatus
    recommended_next_assessment: str = Field(min_length=1)
    human_review_required: Literal[True] = True


class PreliminarySkillGap(BaseModel):
    """Unresolved evidence gap, not a competency or hiring decision."""

    model_config = ConfigDict(extra="forbid", strict=True)

    requirement_id: str = Field(min_length=1)
    criterion_dimension: CriterionDimension
    status: CriterionStatus
    mandatory_status: MandatoryStatus
    recommended_next_assessment: str = Field(min_length=1)
    human_review_required: Literal[True] = True


class MatchEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    criterion_results: list[CriterionResult]
    allocations: list[EvidenceAllocation]
    preliminary_skill_gaps: list[PreliminarySkillGap]
    human_review_required: Literal[True] = True


class PreliminaryMatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    cv_profile_id: str = Field(min_length=1)
    cv_profile_version: int = Field(ge=1)
    jd_profile_id: str = Field(min_length=1)
    jd_profile_version: int = Field(ge=1)
    role_profile_id: str = Field(min_length=1)
    role_profile_version: str = Field(min_length=1)
    rule_set_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    actor_id: UUID
    correlation_id: str = Field(min_length=1)
    status: PreliminaryMatchStatus
    criterion_results: list[CriterionResult]
    evidence_allocations: list[EvidenceAllocation]
    preliminary_skill_gaps: list[PreliminarySkillGap]
    human_review_required: Literal[True] = True
    version: int = Field(default=1, ge=1)
    approved_gap_ids: list[str] = Field(default_factory=list)
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
