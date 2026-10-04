"""Source-side capability mapping proposal, review, and unmapped contracts.

These values describe semantic proposals only. They do not establish target
capability authority or recommendation eligibility.
"""

import json
from enum import StrEnum
from hashlib import sha256

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.capability_governance.evidence import (
    SemanticEvidence,
    canonicalize_semantic_evidence,
)
from app.capability_governance.identity import (
    CanonicalCapabilityRef,
    SourceSemanticRef,
)


class MappingType(StrEnum):
    EXACT = "exact"


class MappingScope(StrEnum):
    CAPABILITY_FACET = "capability_facet"
    OUTCOME_CAPABILITY_FACET = "outcome_capability_facet"
    DIRECT_CAPABILITY_CLAIM = "direct_capability_claim"


class ProposalMethod(StrEnum):
    MANUAL = "manual"
    GOVERNED_RULE = "governed_rule"
    AI_ASSISTED = "ai_assisted"


class MappingDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    UNCERTAIN = "uncertain"


class UnmappedSemanticReason(StrEnum):
    NO_CANONICAL_MATCH = "no_canonical_match"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    MAPPING_REJECTED = "mapping_rejected"
    DEFERRED_GOVERNANCE = "deferred_governance"


class CapabilityMappingProposal(BaseModel):
    """An evidence-backed EXACT proposal for one bounded semantic facet."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    proposal_id: str = Field(min_length=1, max_length=256)
    source_ref: SourceSemanticRef
    target_capability_ref: CanonicalCapabilityRef
    mapping_type: MappingType = MappingType.EXACT
    mapping_scope: MappingScope
    evidence: tuple[SemanticEvidence, ...] = Field(min_length=1)
    proposal_method: ProposalMethod
    proposer_ref: str = Field(min_length=1, max_length=256)
    rationale: str | None = Field(default=None, min_length=1, max_length=1000)

    @field_validator("evidence")
    @classmethod
    def sort_and_reject_duplicate_evidence(
        cls, value: tuple[SemanticEvidence, ...]
    ) -> tuple[SemanticEvidence, ...]:
        return canonicalize_semantic_evidence(value)

    @field_validator("proposal_id", "proposer_ref", "rationale")
    @classmethod
    def reject_blank_or_surrounding_whitespace(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or value != value.strip()):
            raise ValueError("mapping proposal text must be non-blank and exact")
        return value

    @property
    def proposal_fingerprint(self) -> str:
        """Return a deterministic pin over all serialized proposal fields."""
        canonical_payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = sha256(canonical_payload.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"


class CapabilityMappingReview(BaseModel):
    """A review decision pinned to one exact proposal fingerprint."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    proposal_id: str = Field(min_length=1, max_length=256)
    proposal_fingerprint: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    reviewer_ref: str = Field(min_length=1, max_length=256)
    decision: MappingDecision
    rationale: str = Field(min_length=1, max_length=1000)

    @field_validator("proposal_id", "reviewer_ref", "rationale")
    @classmethod
    def reject_blank_or_surrounding_whitespace(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("mapping review text must be non-blank and exact")
        return value


def validate_mapping_review_for_proposal(
    proposal: CapabilityMappingProposal,
    review: CapabilityMappingReview,
) -> None:
    """Check that a review pins this proposal and is independent of its proposer."""
    if review.proposal_id != proposal.proposal_id:
        raise ValueError("review_proposal_id_mismatch")
    if review.proposal_fingerprint != proposal.proposal_fingerprint:
        raise ValueError("review_proposal_fingerprint_mismatch")
    if review.reviewer_ref == proposal.proposer_ref:
        raise ValueError("reviewer_must_be_independent")


class UnmappedSemantic(BaseModel):
    """A valid source semantic with evidence but no canonical target binding."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    source_ref: SourceSemanticRef
    evidence: tuple[SemanticEvidence, ...] = Field(min_length=1)
    reason: UnmappedSemanticReason
    provenance_ref: str | None = Field(default=None, min_length=1, max_length=256)

    @field_validator("evidence")
    @classmethod
    def sort_and_reject_duplicate_evidence(
        cls, value: tuple[SemanticEvidence, ...]
    ) -> tuple[SemanticEvidence, ...]:
        return canonicalize_semantic_evidence(value)

    @field_validator("provenance_ref")
    @classmethod
    def reject_blank_or_surrounding_whitespace(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or value != value.strip()):
            raise ValueError("unmapped provenance ref must be non-blank and exact")
        return value
