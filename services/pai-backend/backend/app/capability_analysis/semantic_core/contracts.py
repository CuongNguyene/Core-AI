"""Immutable, domain-neutral semantic values for capability analysis."""

from dataclasses import dataclass
from enum import StrEnum


class EvidenceExpectation(StrEnum):
    """The kind of evidence explicitly requested by an authored requirement."""

    DEMONSTRATED_USAGE = "demonstrated_usage"
    EDUCATION = "education"
    CREDENTIAL = "credential"
    OWNED_OUTCOME = "owned_outcome"
    UNKNOWN = "unknown"


class EvidenceSourceKind(StrEnum):
    """Structural source of one observation, independent of its subject matter."""

    SKILL = "skill"
    EMPLOYMENT = "employment"
    PROJECT = "project"
    RESEARCH = "research"
    EDUCATION = "education"
    PUBLICATION = "publication"
    CREDENTIAL = "credential"
    ACTIVITY = "activity"


class SemanticContext(StrEnum):
    """Source-grounded context; values intentionally mirror extraction semantics."""

    MENTIONED = "mentioned"
    USED_IN_EMPLOYMENT = "used_in_employment"
    STUDIED = "studied"
    USED_IN_PROJECT = "used_in_project"
    USED_IN_RESEARCH = "used_in_research"
    USED_IN_PRODUCTION = "used_in_production"
    OWNED_SYSTEM = "owned_system"
    LED_TEAM = "led_team"
    CREDENTIALED = "credentialed"
    UNKNOWN = "unknown"


class SemanticConstraintDimension(StrEnum):
    CONTEXT = "context"
    PARTICIPATION = "participation"
    SOURCE_KIND = "source_kind"
    MINIMUM_STRENGTH = "minimum_strength"
    EDUCATION = "education"
    CREDENTIAL = "credential"
    DURATION = "duration"
    UNRESOLVED = "unresolved"


class SemanticConstraintOperator(StrEnum):
    EQUALS = "equals"
    ONE_OF = "one_of"
    AT_LEAST = "at_least"
    DECLARED = "declared"


class SemanticLogicalOperator(StrEnum):
    AND = "AND"
    OR = "OR"


class AssessmentReasonCode(StrEnum):
    """Fixed, domain-neutral reasons emitted by deterministic assessment."""

    NO_RELEVANT_EVIDENCE = "NO_RELEVANT_EVIDENCE"
    EVIDENCE_CONTEXT_MISMATCH = "EVIDENCE_CONTEXT_MISMATCH"
    EVIDENCE_PARTICIPATION_MISMATCH = "EVIDENCE_PARTICIPATION_MISMATCH"
    EVIDENCE_TYPE_INCOMPATIBLE = "EVIDENCE_TYPE_INCOMPATIBLE"
    PARTIAL_SIGNAL_COVERAGE = "PARTIAL_SIGNAL_COVERAGE"
    TARGET_SIGNAL_NOT_SUPPORTED = "TARGET_SIGNAL_NOT_SUPPORTED"
    CONFIDENCE_BELOW_THRESHOLD = "CONFIDENCE_BELOW_THRESHOLD"
    EXPLICIT_MENTION_ONLY = "EXPLICIT_MENTION_ONLY"
    REQUIRES_EXTERNAL_VERIFICATION = "REQUIRES_EXTERNAL_VERIFICATION"


@dataclass(frozen=True, slots=True)
class SemanticDecisionDetails:
    """Explainable decision inputs produced without an LLM or domain inference."""

    reason_codes: tuple[str, ...]
    supported_signals: tuple[str, ...]
    missing_signals: tuple[str, ...]
    observed_confidence: float | None
    required_confidence: float | None
    evidence_directness: str | None
    verification_required: bool
    threshold_source: str = "unknown"
    threshold_policy_id: str | None = None
    threshold_policy_version: str | None = None


@dataclass(frozen=True, slots=True)
class SemanticSourceLocator:
    document_id: str
    section: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    page_number: int | None = None


@dataclass(frozen=True, slots=True)
class SemanticConstraint:
    dimension: SemanticConstraintDimension
    operator: SemanticConstraintOperator
    values: tuple[str, ...]
    source_field: str
    source_reference: str | None = None


@dataclass(frozen=True, slots=True)
class RequirementSemantics:
    requirement_id: str
    concepts: tuple[str, ...]
    behaviors: tuple[str, ...]
    objects: tuple[str, ...]
    constraints: tuple[SemanticConstraint, ...]
    evidence_expectation: EvidenceExpectation
    source_requirement_ref: str | None
    source_locator: SemanticSourceLocator | None
    provenance: tuple[tuple[str, str], ...]
    unresolved_fields: tuple[str, ...]
    logical_operator: SemanticLogicalOperator = SemanticLogicalOperator.AND
    threshold_source: str = "unknown"
    threshold_policy_id: str | None = None
    threshold_policy_version: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceSemantics:
    """One actual source observation; absence is represented by no instance."""

    evidence_ref: str
    concepts: tuple[str, ...]
    behaviors: tuple[str, ...]
    objects: tuple[str, ...]
    context: SemanticContext
    participation: str | None
    source_kind: EvidenceSourceKind
    confidence: float
    original_evidence_type: str | None
    source_locator: SemanticSourceLocator | None
    source_value: str
    source_excerpt: str
    provenance: tuple[tuple[str, str], ...]
    unresolved_fields: tuple[str, ...]
