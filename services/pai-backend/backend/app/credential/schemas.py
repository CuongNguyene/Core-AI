from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CredentialType(StrEnum):
    COMPLETION = "completion"
    LEARNING_ACHIEVEMENT = "learning_achievement"
    COMPETENCY = "competency"


class CredentialPolicyStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


class EligibilityStatus(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    NOT_EVALUABLE = "not_evaluable"
    REQUIRES_REVIEW = "requires_review"


class CredentialRequestStatus(StrEnum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    ISSUED = "issued"
    EXPIRED = "expired"
    REVOKED = "revoked"


class CredentialStatus(StrEnum):
    ISSUED = "issued"
    EXPIRED = "expired"
    REVOKED = "revoked"


class CredentialPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    credential_type: CredentialType
    status: CredentialPolicyStatus
    organization_id: UUID
    valid_for_days: int = Field(ge=1, le=3650)
    allow_duplicate_active: bool
    requires_distinct_approver_and_issuer: bool
    competency_id: str | None = None
    minimum_level: int | None = Field(default=None, ge=1, le=5)


class EligibilityDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    subject_id: UUID
    organization_id: UUID
    status: EligibilityStatus
    reason_code: str = Field(min_length=1, max_length=128)
    evaluator_version: str = Field(min_length=1, max_length=64)


class CredentialRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    credential_type: CredentialType
    subject_id: UUID
    organization_id: UUID
    source_reference_id: str | None = None
    eligibility: EligibilityDecision
    status: CredentialRequestStatus
    requested_by: UUID
    version: int = Field(ge=1)
    correlation_id: UUID
    approver_id: UUID | None = None
    issuer_id: UUID | None = None


class Credential(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    request_id: UUID
    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    credential_type: CredentialType
    subject_id: UUID
    organization_id: UUID
    status: CredentialStatus
    issued_at: datetime
    valid_until: datetime
    issued_by: UUID
    version: int = Field(ge=1)


class CredentialVerification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    credential_id: UUID
    credential_type: CredentialType | None = None
    status: CredentialStatus | None = None
    valid: bool
    policy_id: str | None = None
    policy_version: str | None = None
    organization_id: UUID | None = None
