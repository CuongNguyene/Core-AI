from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.documents.schemas import DocumentKind


class CandidateStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class CandidateReviewState(StrEnum):
    DRAFT = "draft"
    EXTRACTION_PENDING = "extraction_pending"
    PENDING_REVIEW = "pending_review"
    ACCEPTED = "accepted"
    NEEDS_REVISION = "needs_revision"
    REJECTED = "rejected"


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    candidate_id: UUID
    candidate_code: str = Field(default="", max_length=32)
    display_name: str | None = None
    primary_email: str | None = None
    primary_phone: str | None = None
    organization_id: UUID
    created_by_actor_id: UUID
    status: CandidateStatus = CandidateStatus.ACTIVE
    review_state: CandidateReviewState = CandidateReviewState.DRAFT
    current_profile_id: str | None = None
    current_profile_version: int | None = Field(default=None, ge=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CandidateDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    candidate_document_id: UUID
    candidate_id: UUID
    document_id: UUID
    kind: DocumentKind
    is_primary: bool = False
    attached_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CandidateCVVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    cv_version_id: UUID
    candidate_id: UUID
    candidate_cv_id: UUID
    version: int = Field(ge=1)
    document_id: UUID
    created_by_actor_id: UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CandidateProfileLink(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    candidate_profile_id: UUID
    candidate_id: UUID
    profile_id: str = Field(min_length=1)
    profile_version: int = Field(ge=1)
    governance_version: int | None = Field(default=None, ge=1)
    document_id: UUID
    review_state: CandidateReviewState
    linked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CandidateClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    claim_id: UUID
    candidate_id: UUID
    profile_id: str = Field(min_length=1)
    profile_version: int = Field(ge=1)
    bucket: str = Field(min_length=1)
    claim_index: int = Field(ge=0)
    value: str = Field(min_length=1)
    evidence_type: str = Field(min_length=1)
    evidence_status: str = Field(min_length=1)
    context: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[UUID] = Field(default_factory=list)
    evidence_available: bool = False


class CandidateEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    evidence_id: UUID
    claim_id: UUID
    candidate_id: UUID
    document_id: UUID
    source_locator: dict[str, object] | None = None
    excerpt: str = Field(min_length=1, max_length=500)
    evidence_type: str = Field(min_length=1)
    context: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    provenance: dict[str, object] = Field(default_factory=dict)


class CandidateSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    candidate_id: UUID
    candidate_code: str
    display_name: str | None = None
    email: str | None = None
    phone: str | None = None
    status: CandidateStatus
    review_state: CandidateReviewState
    version: int | None = Field(default=None, ge=1)
    current_profile_id: str | None = None
    updated_at: datetime


class CandidateDetail(CandidateSummary):
    profile: dict[str, object] | None = None
    claims: list[CandidateClaim] = Field(default_factory=list)
    extraction_review: dict[str, object] | None = None
    cv: dict[str, object] | None = None


class CandidateListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    items: list[CandidateSummary] = Field(default_factory=list)
    next_cursor: str | None = None


class CandidateReviewActionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    candidate_id: UUID
    idempotency_key: str = Field(min_length=1, max_length=128)
    action: str = Field(min_length=1)
    version: int = Field(ge=1)


class CandidateDocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=False)

    document_id: UUID
    is_primary: bool = False


class CandidateCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    display_name: str | None = Field(default=None, min_length=1, max_length=256)
    email: str | None = Field(default=None, min_length=3, max_length=320)
    phone: str | None = Field(default=None, min_length=3, max_length=64)


class CandidateCVVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=False)

    document_id: UUID


class CandidateCVVersionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: UUID
    version: int
    document_id: UUID
    created_at: datetime
    extraction_status: str | None = None
    profile_version: int | None = None


class CandidateCVVersionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    items: list[CandidateCVVersionResponse]


class CandidateProfileHistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    profile_id: str = Field(min_length=1)
    governance_version: int = Field(ge=1)
    profile_version: int = Field(ge=1)
    review_state: CandidateReviewState
    document_id: UUID
    source_cv_version: int | None = Field(default=None, ge=1)
    is_current: bool


class CandidateProfileHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    items: list[CandidateProfileHistoryEntry]


class CandidateProfileLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=False)

    profile_id: str = Field(min_length=1)


class CandidateReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=False)

    expected_profile_version: int | None = Field(default=None, ge=1)
    reason: str | None = Field(default=None, max_length=512)
    idempotency_key: str = Field(min_length=1, max_length=128)


class CandidateExactReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=False)

    expected_governance_version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=512)
    idempotency_key: str = Field(min_length=1, max_length=128)


class CandidateEvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    candidate_id: UUID
    claim_id: UUID
    items: list["CandidateEvidenceResponseItem"]


class CandidateEvidenceResponseItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    evidence_id: UUID
    source_document_reference: UUID
    source_locator: dict[str, object] | None = None
    excerpt: str
    evidence_type: str
    context: str
    confidence: float
    provenance: dict[str, object]


class CandidateExtractionDocumentStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    candidate_document_id: UUID
    kind: DocumentKind
    status: str
    review_state: CandidateReviewState | None = None
    profile_version: int | None = None


class CandidateExtractionStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    candidate_id: UUID
    status: str
    documents: list[CandidateExtractionDocumentStatus]
    stage: str | None = None
    completed_units: int | None = Field(default=None, ge=0)
    total_units: int | None = Field(default=None, ge=1)
    latest_error: str | None = None
