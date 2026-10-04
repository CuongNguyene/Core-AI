"""Bounded source-grounded semantic evidence values."""

import json
from collections.abc import Iterable
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.capability_governance.identity import SourceSemanticRef


class SemanticEvidenceKind(StrEnum):
    EXPLICIT_OUTCOME = "explicit_outcome"
    EXPLICIT_OBJECTIVE = "explicit_objective"
    DIRECT_CAPABILITY_STATEMENT = "direct_capability_statement"
    STRUCTURED_METADATA = "structured_metadata"
    SOURCE_TEXT = "source_text"
    OTHER = "other"


class SemanticEvidence(BaseModel):
    """A concise, locatable excerpt attached to a stable source semantic ref."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    source_ref: SourceSemanticRef
    source_locator: str = Field(min_length=1, max_length=2048)
    evidence_text: str = Field(min_length=1, max_length=500)
    evidence_kind: SemanticEvidenceKind

    @field_validator("source_locator", "evidence_text")
    @classmethod
    def reject_blank_or_surrounding_whitespace(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("semantic evidence text must be non-blank and exact")
        return value


def canonicalize_semantic_evidence(
    evidence: Iterable[SemanticEvidence],
) -> tuple[SemanticEvidence, ...]:
    """Sort full evidence values canonically and reject exact duplicates."""
    keyed = [(_evidence_key(item), item) for item in evidence]
    keys = [key for key, _ in keyed]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate_semantic_evidence")
    return tuple(item for _, item in sorted(keyed, key=lambda pair: pair[0]))


def _evidence_key(evidence: SemanticEvidence) -> str:
    return json.dumps(
        evidence.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
