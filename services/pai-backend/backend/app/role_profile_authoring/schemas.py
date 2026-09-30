from enum import StrEnum
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.matching.schemas import (
    RoleProfileSemanticPolicy,
    RoleProfileStatus,
    RoleRequirement,
)
from app.semantic_policy.schemas import SemanticPolicyRef


class RoleProfileDraftStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    NEEDS_REVISION = "needs_revision"
    PROVISIONAL = "provisional"
    ACTIVE = "active"
    VALIDATED = "validated"
    APPROVED = "approved"


class QualityFindingSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    BLOCKING = "blocking"


class SummaryFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    code: str = Field(min_length=1)
    severity: QualityFindingSeverity
    affected_requirement_count: int = Field(ge=0)
    affected_requirement_ids: list[str] | None = None
    message: str = Field(min_length=1)


class RequirementFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    requirement_id: str | None = Field(default=None, min_length=1)
    code: str = Field(min_length=1)
    severity: QualityFindingSeverity
    field: str | None = Field(default=None, min_length=1)
    message: str = Field(min_length=1)


# Compatibility alias for internal callers migrated in stages.
QualityFinding = RequirementFinding


class ApprovalEligibility(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    can_create_draft: bool
    can_approve_provisional: bool
    can_approve_active: bool


class DuplicateCandidateGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    group_id: str = Field(min_length=1)
    requirement_ids: list[str] = Field(min_length=2)
    reason: str = Field(min_length=1)
    merge_recommended: bool
    reviewer_required: bool


class QualityGateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    passed: bool
    summary_findings: list[SummaryFinding] = Field(
        default_factory=list,
        validation_alias=AliasChoices("summary_findings", "findings"),
    )

    @property
    def has_blocking(self) -> bool:
        return any(
            item.severity is QualityFindingSeverity.BLOCKING for item in self.summary_findings
        )

    @property
    def findings(self) -> list[SummaryFinding]:
        """Compatibility accessor; serialized JSON only exposes summary_findings."""
        return self.summary_findings


class RoleProfileDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    id: str = Field(min_length=1, max_length=128)
    source_jd_profile_id: str = Field(min_length=1)
    source_jd_profile_version: int = Field(ge=1)
    owner_actor_id: UUID
    organization_id: UUID
    version: int = Field(ge=1)
    status: RoleProfileDraftStatus
    title: str | None = Field(default=None, min_length=1, max_length=256)
    requirements: list[RoleRequirement]
    quality_gate: QualityGateResult
    approval_eligibility: ApprovalEligibility = Field(
        default_factory=lambda: ApprovalEligibility(
            can_create_draft=True,
            can_approve_provisional=False,
            can_approve_active=False,
        )
    )
    source_schema: str = "legacy_v1"
    source_version: str = "1.1"
    authoring_findings: list[RequirementFinding] = Field(default_factory=list)
    duplicate_candidate_groups: list[DuplicateCandidateGroup] = Field(default_factory=list)
    approved_role_profile_id: str | None = None
    approved_role_profile_version: str | None = None
    role_id: UUID | None = None
    role_jd_version_id: UUID | None = None
    correlation_id: str = Field(min_length=1, max_length=64)


class RoleProfileDraftResponse(BaseModel):
    """Public projection; detailed findings are opt-in to avoid repeated warning payloads."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    id: str = Field(min_length=1, max_length=128)
    source_jd_profile_id: str = Field(min_length=1)
    source_jd_profile_version: int = Field(ge=1)
    owner_actor_id: UUID
    organization_id: UUID
    version: int = Field(ge=1)
    status: RoleProfileDraftStatus
    title: str | None = Field(default=None, min_length=1, max_length=256)
    requirements: list[RoleRequirement]
    quality_gate: QualityGateResult
    approval_eligibility: ApprovalEligibility
    source_schema: str
    source_version: str
    authoring_findings: list[RequirementFinding] | None = None
    duplicate_candidate_groups: list[DuplicateCandidateGroup] = Field(default_factory=list)
    approved_role_profile_id: str | None = None
    approved_role_profile_version: str | None = None
    role_id: UUID | None = None
    role_jd_version_id: UUID | None = None
    correlation_id: str = Field(min_length=1, max_length=64)


class CreateRoleProfileDraftRequest(BaseModel):
    # UUID values arrive as JSON strings over HTTP; keep unknown-field rejection
    # while allowing Pydantic's normal UUID coercion at this transport boundary.
    model_config = ConfigDict(extra="forbid")

    source_jd_profile_id: str = Field(min_length=1, max_length=128)
    correlation_id: str = Field(min_length=1, max_length=64)
    role_id: UUID | None = None
    role_jd_version_id: UUID | None = None

    @model_validator(mode="after")
    def require_complete_role_lineage(self) -> "CreateRoleProfileDraftRequest":
        if (self.role_id is None) != (self.role_jd_version_id is None):
            raise ValueError("role_id and role_jd_version_id must be supplied together")
        return self


class AuthorRoleProfileDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=256)
    requirements: list[dict[str, object]]


class ValidateRoleProfileDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    expected_version: int = Field(ge=1)


class ApproveRoleProfileDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    expected_version: int = Field(ge=1)
    requested_status: RoleProfileStatus = RoleProfileStatus.PROVISIONAL
    semantic_policy: RoleProfileSemanticPolicy
    semantic_policy_ref: SemanticPolicyRef | None = None

    @field_validator("requested_status", mode="before")
    @classmethod
    def accept_status_wire_value(cls, value: object) -> object:
        return RoleProfileStatus(value) if isinstance(value, str) else value
