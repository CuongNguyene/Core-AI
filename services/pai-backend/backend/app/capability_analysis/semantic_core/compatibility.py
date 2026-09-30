"""Domain-neutral compatibility checks for already-retrieved evidence."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from app.capability_analysis.semantic_core.contracts import (
    EvidenceExpectation,
    EvidenceSemantics,
    EvidenceSourceKind,
    RequirementSemantics,
    SemanticConstraint,
    SemanticConstraintDimension,
    SemanticConstraintOperator,
    SemanticContext,
)


class EvidenceDirectness(StrEnum):
    DIRECT = "direct"
    INDIRECT = "indirect"
    INCOMPATIBLE = "incompatible"


@dataclass(frozen=True, slots=True)
class EvidenceCompatibility:
    evidence_ref: str
    eligible: bool
    directness: EvidenceDirectness
    rank: int
    reason_codes: tuple[str, ...]
    verification_required: bool = False


_DEMONSTRATED_CONTEXTS = {
    SemanticContext.USED_IN_EMPLOYMENT,
    SemanticContext.USED_IN_PROJECT,
    SemanticContext.USED_IN_RESEARCH,
    SemanticContext.USED_IN_PRODUCTION,
    SemanticContext.OWNED_SYSTEM,
    SemanticContext.LED_TEAM,
}
_STRENGTH_BY_CONTEXT = {
    SemanticContext.UNKNOWN: 0,
    SemanticContext.MENTIONED: 1,
    SemanticContext.STUDIED: 1,
    SemanticContext.CREDENTIALED: 1,
    SemanticContext.USED_IN_PROJECT: 2,
    SemanticContext.USED_IN_RESEARCH: 2,
    SemanticContext.USED_IN_EMPLOYMENT: 3,
    SemanticContext.LED_TEAM: 3,
    SemanticContext.USED_IN_PRODUCTION: 4,
    SemanticContext.OWNED_SYSTEM: 4,
}
_MINIMUM_STRENGTH = {
    "unknown": 0,
    "mention": 1,
    "project": 2,
    "work": 3,
    "production": 4,
}
_DIRECTNESS_RANK = {
    EvidenceDirectness.INCOMPATIBLE: 1,
    EvidenceDirectness.INDIRECT: 2,
    EvidenceDirectness.DIRECT: 3,
}


def evaluate_evidence_compatibility(
    requirement: RequirementSemantics,
    evidence: EvidenceSemantics,
) -> EvidenceCompatibility:
    """Evaluate generic semantic dimensions without deciding an assessment status."""
    reason_codes: list[str] = []
    direct_match = False
    hard_mismatch = False
    soft_expectation_mismatch = False

    expectation_reason = _expectation_mismatch(requirement.evidence_expectation, evidence)
    if expectation_reason is None:
        if requirement.evidence_expectation is not EvidenceExpectation.UNKNOWN:
            direct_match = True
    else:
        reason_codes.append(expectation_reason)
        soft_expectation_mismatch = (
            requirement.evidence_expectation is EvidenceExpectation.DEMONSTRATED_USAGE
        )
        hard_mismatch = not soft_expectation_mismatch

    for constraint in requirement.constraints:
        reason = _constraint_mismatch(constraint, evidence)
        if reason is None:
            direct_match = True
        else:
            reason_codes.append(reason)
            hard_mismatch = True

    if hard_mismatch:
        directness = EvidenceDirectness.INCOMPATIBLE
    elif soft_expectation_mismatch:
        directness = EvidenceDirectness.INDIRECT
    elif direct_match or (
        requirement.evidence_expectation is EvidenceExpectation.UNKNOWN
        and evidence.context in _DEMONSTRATED_CONTEXTS
    ):
        directness = EvidenceDirectness.DIRECT
    else:
        directness = EvidenceDirectness.INDIRECT

    eligible = not reason_codes
    rank = (
        _DIRECTNESS_RANK[directness] * 10_000
        + _STRENGTH_BY_CONTEXT[evidence.context] * 1_000
        + round(evidence.confidence * 100)
    )
    return EvidenceCompatibility(
        evidence_ref=evidence.evidence_ref,
        eligible=eligible,
        directness=directness,
        rank=rank,
        reason_codes=tuple(reason_codes),
        verification_required=(
            eligible
            and requirement.evidence_expectation
            in {EvidenceExpectation.EDUCATION, EvidenceExpectation.CREDENTIAL}
        ),
    )


def evaluate_compatibilities(
    requirement: RequirementSemantics,
    evidence: Iterable[EvidenceSemantics],
) -> tuple[EvidenceCompatibility, ...]:
    """Preserve every retrieved candidate, including ineligible candidates."""
    return tuple(evaluate_evidence_compatibility(requirement, item) for item in evidence)


def _expectation_mismatch(
    expectation: EvidenceExpectation,
    evidence: EvidenceSemantics,
) -> str | None:
    if expectation is EvidenceExpectation.UNKNOWN:
        return None
    if expectation is EvidenceExpectation.DEMONSTRATED_USAGE:
        if evidence.context in _DEMONSTRATED_CONTEXTS:
            return None
        return "demonstrated_usage_required"
    if expectation is EvidenceExpectation.EDUCATION:
        if (
            evidence.source_kind is EvidenceSourceKind.EDUCATION
            and evidence.context is SemanticContext.STUDIED
        ):
            return None
        return "education_evidence_required"
    if expectation is EvidenceExpectation.CREDENTIAL:
        if (
            evidence.source_kind is EvidenceSourceKind.CREDENTIAL
            and evidence.context is SemanticContext.CREDENTIALED
        ):
            return None
        return "credential_evidence_required"
    if expectation is EvidenceExpectation.OWNED_OUTCOME:
        if evidence.participation in {"owned", "led"}:
            return None
        return "ownership_evidence_required"
    return "unsupported_evidence_expectation"


def _constraint_mismatch(
    constraint: SemanticConstraint,
    evidence: EvidenceSemantics,
) -> str | None:
    if constraint.dimension is SemanticConstraintDimension.CONTEXT:
        return _exact_constraint_mismatch(
            constraint, evidence.context.value, "context_mismatch"
        )
    if constraint.dimension is SemanticConstraintDimension.PARTICIPATION:
        return _exact_constraint_mismatch(
            constraint, evidence.participation, "participation_mismatch"
        )
    if constraint.dimension is SemanticConstraintDimension.SOURCE_KIND:
        return _exact_constraint_mismatch(
            constraint, evidence.source_kind.value, "source_kind_mismatch"
        )
    if constraint.dimension is SemanticConstraintDimension.EDUCATION:
        if evidence.source_kind is EvidenceSourceKind.EDUCATION:
            return None
        return "education_evidence_required"
    if constraint.dimension is SemanticConstraintDimension.CREDENTIAL:
        if evidence.source_kind is EvidenceSourceKind.CREDENTIAL:
            return None
        return "credential_evidence_required"
    if constraint.dimension is SemanticConstraintDimension.MINIMUM_STRENGTH:
        return _minimum_strength_mismatch(constraint, evidence)
    if constraint.dimension is SemanticConstraintDimension.UNRESOLVED:
        return "unresolved_constraint"
    return "unsupported_constraint"


def _exact_constraint_mismatch(
    constraint: SemanticConstraint,
    observed: str | None,
    mismatch_code: str,
) -> str | None:
    if constraint.operator is SemanticConstraintOperator.EQUALS:
        if len(constraint.values) != 1:
            return "invalid_constraint"
        return None if observed == constraint.values[0] else mismatch_code
    if constraint.operator is SemanticConstraintOperator.ONE_OF:
        return None if observed in constraint.values else mismatch_code
    return "invalid_constraint"


def _minimum_strength_mismatch(
    constraint: SemanticConstraint,
    evidence: EvidenceSemantics,
) -> str | None:
    if (
        constraint.operator is not SemanticConstraintOperator.AT_LEAST
        or len(constraint.values) != 1
        or constraint.values[0] not in _MINIMUM_STRENGTH
    ):
        return "invalid_constraint"
    required = _MINIMUM_STRENGTH[constraint.values[0]]
    if _STRENGTH_BY_CONTEXT[evidence.context] >= required:
        return None
    return "minimum_evidence_strength_not_met"
