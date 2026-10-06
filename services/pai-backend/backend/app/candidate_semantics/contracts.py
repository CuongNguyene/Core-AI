"""Strict, source-neutral contracts for unvalidated candidate evidence proposals."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.capability_governance.definitions import CapabilityDefinition
from app.capability_governance.identity import CanonicalCapabilityRef
from app.capability_governance.resolution import CapabilityDefinitionPin
from app.model_gateway.contracts import InferenceAuditMetadata


class SemanticRelation(StrEnum):
    DIRECT_SUPPORT = "DIRECT_SUPPORT"
    PARTIAL_SUPPORT = "PARTIAL_SUPPORT"
    NO_SUPPORT = "NO_SUPPORT"
    CONTRADICTORY = "CONTRADICTORY"
    CONTEXT_MISMATCH = "CONTEXT_MISMATCH"


class SemanticProposalValidationStatus(StrEnum):
    UNVALIDATED = "UNVALIDATED"


class CandidateSemanticEvidenceKind(StrEnum):
    EMPLOYMENT = "employment"
    EDUCATION = "education"
    CREDENTIAL = "credential"
    PROJECT = "project"


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class CandidateSemanticEvidenceInput(_StrictFrozenModel):
    """One verbatim source fact plus the identity needed to locate it."""

    candidate_ref: str = Field(min_length=1, max_length=256)
    source_system: str = Field(min_length=1, max_length=64)
    source_revision: int = Field(gt=0)
    snapshot_ref: str = Field(min_length=1, max_length=256)
    content_fingerprint: str = Field(pattern=r"^(?:sha256:)?[a-f0-9]{64}$")
    transport_schema_version: str | None = Field(default=None, min_length=1, max_length=32)
    source_kind: CandidateSemanticEvidenceKind
    source_record_ref: str | None = Field(default=None, min_length=1, max_length=256)
    field_path: str = Field(min_length=1, max_length=512)
    content: str = Field(min_length=1, max_length=8000)

    @field_validator("candidate_ref", "source_system", "snapshot_ref", "field_path")
    @classmethod
    def reject_blank_or_surrounded_values(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("evidence values must be non-blank and have no surrounding whitespace")
        return value

    @field_validator("content")
    @classmethod
    def content_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("evidence content must not be blank")
        return value


class TargetCapabilityContext(_StrictFrozenModel):
    """A target definition tied to its exact canonical-definition pin."""

    definition_pin: CapabilityDefinitionPin
    definition: CapabilityDefinition

    @model_validator(mode="after")
    def definition_matches_pin(self) -> "TargetCapabilityContext":
        if self.definition_pin.capability_ref != self.definition.canonical_ref:
            raise ValueError("target definition does not match the exact capability pin")
        return self


class StructuredCandidateEvidenceBasis(_StrictFrozenModel):
    candidate_ref: str = Field(min_length=1, max_length=256)
    source_system: str = Field(min_length=1, max_length=64)
    source_revision: int = Field(gt=0)
    snapshot_ref: str = Field(min_length=1, max_length=256)
    content_fingerprint: str = Field(pattern=r"^(?:sha256:)?[a-f0-9]{64}$")
    transport_schema_version: str | None = Field(default=None, min_length=1, max_length=32)


class StructuredCandidateSourceLocator(_StrictFrozenModel):
    locator_type: Literal["structured_candidate_source"] = "structured_candidate_source"
    source_system: str = Field(min_length=1, max_length=64)
    snapshot_ref: str = Field(min_length=1, max_length=256)
    source_revision: int = Field(gt=0)
    field_path: str = Field(min_length=1, max_length=512)
    source_record_ref: str | None = Field(default=None, min_length=1, max_length=256)


class SemanticEvidenceProposalV1(_StrictFrozenModel):
    """Ephemeral model proposal; never a verified capability fact."""

    target_ref: CanonicalCapabilityRef
    relation: SemanticRelation
    validation_status: SemanticProposalValidationStatus
    rationale: str = Field(min_length=1, max_length=1000)
    source_locator: StructuredCandidateSourceLocator
    source_basis: StructuredCandidateEvidenceBasis
    generator_id: str = Field(min_length=1, max_length=128)
    generator_version: str = Field(min_length=1, max_length=64)
    prompt_template_id: str = Field(min_length=1, max_length=128)
    prompt_template_version: str = Field(min_length=1, max_length=64)
    output_schema_id: str = Field(min_length=1, max_length=128)
    output_schema_version: str = Field(min_length=1, max_length=64)
    input_fingerprint: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    audit: InferenceAuditMetadata

    @field_validator("rationale")
    @classmethod
    def rationale_is_nonblank_and_exact(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("rationale must be non-blank and have no surrounding whitespace")
        return value

    @model_validator(mode="after")
    def proposal_status_is_unvalidated(self) -> "SemanticEvidenceProposalV1":
        if self.validation_status is not SemanticProposalValidationStatus.UNVALIDATED:
            raise ValueError("semantic relation proposals must remain unvalidated")
        return self
