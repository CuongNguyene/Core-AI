from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.extraction.locators import SourceLocator
from app.extraction.profile import CandidateProfile

__all__ = ["SourceLocator"]


class DocumentKind(StrEnum):
    CV = "cv"
    JD = "jd"


class EvidenceStatus(StrEnum):
    SUPPORTED = "supported"
    UNKNOWN = "unknown"
    INSUFFICIENT = "insufficient"


class EvidenceType(StrEnum):
    EXPLICIT_SKILL = "explicit_skill"
    PROJECT_USAGE = "project_usage"
    WORK_EXPERIENCE = "work_experience"
    EDUCATION = "education"
    PUBLICATION = "publication"
    CERTIFICATION = "certification"
    UNKNOWN = "unknown"


class ReviewState(StrEnum):
    PENDING_REVIEW = "pending_review"
    CORRECTED = "corrected"
    ACCEPTED = "accepted"
    NEEDS_REVISION = "needs_revision"
    REJECTED = "rejected"


class SectionType(StrEnum):
    EXPERIENCE = "experience"
    EDUCATION = "education"
    SKILLS = "skills"
    PROJECTS = "projects"
    PUBLICATIONS = "publications"
    QUALIFICATIONS = "qualifications"
    RESPONSIBILITIES = "responsibilities"
    UNKNOWN = "unknown"


class DocumentSection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    section_type: SectionType
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def require_increasing_offsets(self) -> "DocumentSection":
        if self.end_offset <= self.start_offset:
            raise ValueError("Document section end offset must follow start offset")
        return self


class DocumentStructureOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    document_type: str = Field(min_length=1)
    sections: list[DocumentSection]


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ExtractionStage(StrEnum):
    """The last worker stage reached by an extraction job.

    Stages deliberately describe work, not a guessed percentage.  Only chunked
    extraction supplies unit counts that callers may turn into a determinate bar.
    """

    QUEUED = "queued"
    READING_DOCUMENT = "reading_document"
    EXTRACTING = "extracting"
    VALIDATING = "validating"
    PERSISTING = "persisting"


class EvidenceClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    value: str | None
    evidence_type: EvidenceType
    confidence: float = Field(ge=0, le=1)
    evidence_status: Literal["supported", "insufficient", "unknown"]
    source_excerpt: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def enforce_evidence_boundary(self) -> "EvidenceClaim":
        if self.evidence_status == "supported":
            if self.value is None or not self.source_excerpt:
                raise ValueError("Supported claim requires value and source evidence")
        elif self.value is not None or self.source_excerpt is not None:
            raise ValueError(
                "Unknown or insufficient claim must not invent value or source evidence"
            )
        return self


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    evidence_type: EvidenceType
    confidence: float = Field(ge=0, le=1)
    source_locator: SourceLocator
    source_excerpt: str = Field(min_length=1, max_length=500)


class ExtractedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    value: str | None
    evidence_type: EvidenceType = EvidenceType.UNKNOWN
    confidence: float = Field(ge=0, le=1)
    evidence_status: EvidenceStatus
    source_locator: SourceLocator | None = None
    source_excerpt: str | None = Field(default=None, max_length=500)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    unresolved_reason: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def enforce_evidence_boundary(self) -> "ExtractedClaim":
        if self.evidence_status is EvidenceStatus.SUPPORTED:
            if self.value is None or self.source_locator is None or not self.source_excerpt:
                raise ValueError("Supported claim requires value and source evidence")
        elif (
            self.value is not None
            or self.source_locator is not None
            or self.source_excerpt is not None
        ):
            raise ValueError(
                "Unknown or insufficient claim must not invent value or source evidence"
            )
        if self.unresolved_reason is not None and self.evidence_status is EvidenceStatus.SUPPORTED:
            raise ValueError("Supported claim must not carry an unresolved reason")
        return self


class ChunkExtractedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    value: str | None
    evidence_type: EvidenceType = EvidenceType.UNKNOWN
    confidence: float = Field(ge=0, le=1)
    evidence_status: EvidenceStatus
    source_excerpt: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def enforce_chunk_evidence_boundary(self) -> "ChunkExtractedClaim":
        if self.evidence_status is EvidenceStatus.SUPPORTED:
            if self.value is None or not self.source_excerpt:
                raise ValueError("Supported chunk claim requires value and source excerpt")
        elif self.value is not None or self.source_excerpt is not None:
            raise ValueError("Unknown or insufficient chunk claim must not invent evidence")
        return self


class CVExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    skills: list[ExtractedClaim]
    experience: list[ExtractedClaim]
    education: list[ExtractedClaim]


class JDExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    required_skills: list[ExtractedClaim]
    responsibilities: list[ExtractedClaim]
    qualifications: list[ExtractedClaim]


class JDRequirementModality(StrEnum):
    MUST = "must"
    PREFERRED = "preferred"
    RESPONSIBILITY = "responsibility"
    UNSPECIFIED = "unspecified"


class RequirementFieldProvenance(StrEnum):
    JD_EXTRACTION = "jd_extraction"
    TAXONOMY_NORMALIZATION = "taxonomy_normalization"
    APPROVED_TEMPLATE = "approved_template"
    POLICY_DEFAULT = "policy_default"
    REVIEWER_AUTHORED = "reviewer_authored"


class NativePdfLocator(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    document_id: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    section: str | None = Field(default=None, min_length=1)


class ProviderPdfLocator(BaseModel):
    """Provider-facing PDF locator; backend binds the canonical document ID."""

    model_config = ConfigDict(extra="forbid", strict=True)

    document_id: str | None = Field(default=None, min_length=1)
    page_number: int = Field(ge=1)
    section: str | None = Field(default=None, min_length=1)


class ProviderTextLocator(BaseModel):
    """Provider-facing text locator resolved to canonical offsets by the backend."""

    model_config = ConfigDict(extra="forbid", strict=True)

    document_id: str | None = Field(default=None, min_length=1)
    section: str | None = Field(default=None, min_length=1)
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, gt=0)


class JDRequirementExtractionV2(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    requirement_id: str | None = Field(default=None, min_length=1)
    statement: str | None = Field(default=None, min_length=1)
    criterion_dimension: Literal[
        "skill", "experience", "education", "credential", "qualification"
    ] | None = None
    modality: JDRequirementModality | None = None
    logical_group: str | None = Field(default=None, min_length=1)
    logical_operator: Literal["AND", "OR"] = "AND"
    evidence_terms: list[str] = Field(default_factory=list)
    conflicting_terms: list[str] = Field(default_factory=list)
    priority: str | None = None
    target_level: str | None = None
    observable_behaviors: list[str] = Field(default_factory=list)
    evidence_constraints: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    evidence_status: EvidenceStatus
    source_locator: SourceLocator | ProviderPdfLocator | ProviderTextLocator | NativePdfLocator | None = Field(
        default=None,
        description=(
            "Exact source locator into the supplied document. Its document_id must be "
            "copied verbatim from input metadata."
        ),
    )
    source_excerpt: str | None = Field(default=None, max_length=500)
    provenance: dict[str, RequirementFieldProvenance] = Field(default_factory=dict)

    @model_validator(mode="after")
    def enforce_requirement_evidence(self) -> "JDRequirementExtractionV2":
        if self.evidence_status is EvidenceStatus.SUPPORTED:
            if self.statement is None or self.source_locator is None or not self.source_excerpt:
                raise ValueError("Supported JD requirement requires statement and source evidence")
        elif any(
            value is not None
            for value in (self.requirement_id, self.statement, self.source_locator, self.source_excerpt)
        ):
            raise ValueError("Unsupported JD requirement must not invent source data")
        return self


class JDRequirementExtractionOutputV2(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    requirements: list[JDRequirementExtractionV2] = Field(default_factory=list)


class JDRequirementExtractionV2Text(JDRequirementExtractionV2):
    """Provider contract for non-paginated JD input."""

    requirement_id: str = Field(min_length=1)
    source_locator: ProviderTextLocator | None = None


class JDRequirementExtractionV2Pdf(JDRequirementExtractionV2):
    """Provider contract for native PDF JD input."""

    requirement_id: str = Field(min_length=1)
    source_locator: ProviderPdfLocator | None = None


class JDRequirementExtractionOutputV2Text(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    requirements: list[JDRequirementExtractionV2Text] = Field(default_factory=list)


class JDRequirementExtractionOutputV2Pdf(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    requirements: list[JDRequirementExtractionV2Pdf] = Field(default_factory=list)


class JDReviewCorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    review_item_id: str = Field(min_length=1)
    operation: Literal["correct", "remove"]
    statement: str | None = Field(default=None, min_length=1)
    modality: JDRequirementModality | None = None
    criterion_dimension: Literal[
        "skill", "experience", "education", "credential", "qualification"
    ] | None = None
    reason: str = Field(min_length=1, max_length=512)


# Public name for callers that do not need to know the wire-version suffix.
JDRequirementExtractionOutput = JDRequirementExtractionOutputV2


class CVFullExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    skills: list[EvidenceClaim]
    experience: list[EvidenceClaim]
    education: list[EvidenceClaim]


class EvidenceStrength(StrEnum):
    """How strongly a CV passage demonstrates an extracted item."""

    EXPLICIT_MENTION = "explicit_mention"
    DEMONSTRATED_IN_ROLE = "demonstrated_in_role"
    DEMONSTRATED_WITH_OUTCOME = "demonstrated_with_outcome"
    MULTIPLE_SUPPORTING_EXPERIENCES = "multiple_supporting_experiences"


class CapabilityMappingStatus(StrEnum):
    MAPPED = "mapped"
    UNMAPPED_BUT_GROUNDED = "unmapped_but_grounded"
    REJECTED_UNSUPPORTED = "rejected_unsupported"


class CapabilityEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source_excerpt: str = Field(min_length=1, max_length=500)
    source_locator: SourceLocator | NativePdfLocator
    evidence_strength: EvidenceStrength
    confidence: float = Field(ge=0, le=1, default=0.0)


class CapabilityItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    raw_name: str = Field(min_length=1)
    canonical_name: str = Field(min_length=1)
    category: str | None = Field(default=None, min_length=1)
    evidence: list[CapabilityEvidence] = Field(min_length=1)
    supporting_experience_refs: list[str] = Field(default_factory=list)
    evidence_strength: EvidenceStrength = EvidenceStrength.EXPLICIT_MENTION
    mapping_status: CapabilityMappingStatus = CapabilityMappingStatus.MAPPED


class ToolPlatformItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1)
    evidence: list[CapabilityEvidence] = Field(min_length=1)


class ExperienceItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str = Field(min_length=1)
    company: str | None = Field(default=None, min_length=1)
    start_date: str | None = Field(default=None, min_length=1)
    end_date: str | None = Field(default=None, min_length=1)
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    evidence: list[CapabilityEvidence] = Field(default_factory=list)


class EducationItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    degree: str = Field(min_length=1)
    field: str | None = Field(default=None, min_length=1)
    institution: str | None = Field(default=None, min_length=1)
    location: str | None = Field(default=None, min_length=1)
    year: int | None = Field(default=None, ge=0)
    evidence: list[CapabilityEvidence] = Field(default_factory=list)


class CVFullExtractionOutputV2(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    candidate_summary: str | None = Field(default=None, min_length=1)
    experience: list[ExperienceItem] = Field(default_factory=list)
    capabilities: list[CapabilityItem] = Field(default_factory=list)
    tools_platforms: list[ToolPlatformItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)


class JDFullExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    required_skills: list[EvidenceClaim]
    responsibilities: list[EvidenceClaim]
    qualifications: list[EvidenceClaim]


class CVSectionExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    skills: list[EvidenceClaim]
    experience: list[EvidenceClaim]
    education: list[EvidenceClaim]


class JDSectionExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    required_skills: list[EvidenceClaim]
    responsibilities: list[EvidenceClaim]
    qualifications: list[EvidenceClaim]


class CVChunkExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    skills: list[ChunkExtractedClaim]
    experience: list[ChunkExtractedClaim]
    education: list[ChunkExtractedClaim]


class JDChunkExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    required_skills: list[ChunkExtractedClaim]
    responsibilities: list[ChunkExtractedClaim]
    qualifications: list[ChunkExtractedClaim]


class ExtractionProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str
    job_id: str
    document_id: str
    document_kind: DocumentKind
    owner_actor_id: UUID
    version: int = Field(ge=1)
    review_state: ReviewState
    created_at: datetime | None = None
    accepted_by: UUID | None = None
    accepted_at: datetime | None = None
    supersedes_profile_id: str | None = None
    output: CVExtractionOutput | CVFullExtractionOutputV2 | JDExtractionOutput | JDRequirementExtractionOutputV2
    candidate_profile: CandidateProfile | None = None
    audit: dict[str, object]

    @model_validator(mode="after")
    def enforce_acceptance_metadata(self) -> "ExtractionProfile":
        if self.review_state is ReviewState.ACCEPTED:
            if self.accepted_by is None or self.accepted_at is None:
                raise ValueError("Accepted profile requires reviewer and acceptance timestamp")
        elif self.accepted_by is not None or self.accepted_at is not None:
            raise ValueError("Only accepted profile can contain acceptance metadata")
        return self


class ExtractionJob(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str
    document_id: str
    document_kind: DocumentKind
    owner_actor_id: UUID
    correlation_id: str
    status: JobStatus
    stage: ExtractionStage = ExtractionStage.QUEUED
    completed_units: int | None = Field(default=None, ge=0)
    total_units: int | None = Field(default=None, ge=1)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    error_category: str | None = None
    error_details: dict[str, object] | None = None
    profile_id: str | None = None

    @model_validator(mode="after")
    def enforce_progress_bounds(self) -> "ExtractionJob":
        if (
            self.completed_units is not None
            and self.total_units is not None
            and self.completed_units > self.total_units
        ):
            raise ValueError("Completed extraction units cannot exceed total units")
        return self
