from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class EvidenceSourceType(StrEnum):
    CV = "cv"
    JD = "jd"
    ASSESSMENT = "assessment"
    WORK_PRODUCT = "work_product"
    MANAGER_REVIEW = "manager_review"
    SME_REVIEW = "sme_review"
    CREDENTIAL = "credential"


class EvidenceVerificationStatus(StrEnum):
    DECLARED = "declared"
    INFERRED = "inferred"
    ASSESSED = "assessed"
    VERIFIED = "verified"
    CONFLICTING = "conflicting"
    EXPIRED = "expired"


class EvidenceItem(BaseModel):
    id: UUID
    subject_id: UUID
    source_type: EvidenceSourceType
    source_document_id: UUID | None = None
    claim: str
    normalized_concept_id: str | None = None
    source_locator: str | None = None
    source_excerpt: str | None = None
    extraction_confidence: float = Field(ge=0, le=1)
    verification_status: EvidenceVerificationStatus
