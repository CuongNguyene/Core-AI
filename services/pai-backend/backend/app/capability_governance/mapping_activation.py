"""Source freshness, review fingerprint, and activation approval contracts."""

import json
from collections.abc import Iterable
from hashlib import sha256

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.capability_governance.evidence import (
    SemanticEvidence,
    canonicalize_semantic_evidence,
)
from app.capability_governance.identity import SourceSemanticRef
from app.capability_governance.mapping import CapabilityMappingReview
from app.capability_governance.mapping_errors import MappingGovernanceError
from app.capability_governance.resolution import CapabilityDefinitionPin

_SHA256_PATTERN = r"^sha256:[a-f0-9]{64}$"


class SourceSemanticPin(BaseModel):
    """Pins one source semantic identity and its complete canonical evidence."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    source_ref: SourceSemanticRef
    evidence_fingerprint: str = Field(pattern=_SHA256_PATTERN)


def build_source_semantic_pin(
    source_ref: SourceSemanticRef,
    evidence: Iterable[SemanticEvidence],
) -> SourceSemanticPin:
    """Build a deterministic source pin from identity and canonical evidence."""
    canonical_evidence = canonicalize_semantic_evidence(evidence)
    if not canonical_evidence:
        raise MappingGovernanceError("source_pin_mismatch", "source evidence must be non-empty")
    if any(item.source_ref != source_ref for item in canonical_evidence):
        raise MappingGovernanceError(
            "source_pin_mismatch", "evidence source identity does not match source pin"
        )

    payload = {
        "source_ref": source_ref.model_dump(mode="json"),
        "evidence": [item.model_dump(mode="json") for item in canonical_evidence],
    }
    canonical_json = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    fingerprint = f"sha256:{sha256(canonical_json.encode('utf-8')).hexdigest()}"
    return SourceSemanticPin(source_ref=source_ref, evidence_fingerprint=fingerprint)


def fingerprint_mapping_review(review: CapabilityMappingReview) -> str:
    """Fingerprint every semantic field of the immutable 3D-3A review value."""
    canonical_json = json.dumps(
        review.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"sha256:{sha256(canonical_json.encode('utf-8')).hexdigest()}"


class MappingActivationApproval(BaseModel):
    """Explicit approval bound to one exact proposal, review, source, and target."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    approval_ref: str = Field(min_length=1, max_length=256)
    proposal_id: str = Field(min_length=1, max_length=256)
    proposal_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    review_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    source_pin: SourceSemanticPin
    target_definition_pin: CapabilityDefinitionPin
    approver_ref: str = Field(min_length=1, max_length=256)

    @field_validator("approval_ref", "proposal_id", "approver_ref")
    @classmethod
    def reject_blank_or_surrounding_whitespace(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("activation approval references must be non-blank and exact")
        return value
