"""Identity-only semantic retrieval and candidate-derived assessment projection."""

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from app.capability_analysis.semantic_core.compatibility import (
    EvidenceCompatibility,
    EvidenceDirectness,
    evaluate_evidence_compatibility,
)
from app.capability_analysis.semantic_core.contracts import (
    AssessmentReasonCode,
    EvidenceSemantics,
    RequirementSemantics,
    SemanticContext,
    SemanticDecisionDetails,
    SemanticLogicalOperator,
)


class SemanticAssessmentStatus(StrEnum):
    SUPPORTED = "supported"
    REQUIRES_VERIFICATION = "requires_verification"
    CONTEXT_MISMATCH = "context_mismatch"
    NOT_FOUND_IN_EVIDENCE = "not_found_in_evidence"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True, slots=True)
class RetrievalCandidate:
    evidence: EvidenceSemantics
    matched_concepts: tuple[str, ...]
    compatibility: EvidenceCompatibility
    match_reason: str = "identity_phrase_equality"


@dataclass(frozen=True, slots=True)
class SemanticAssessmentProjection:
    status: SemanticAssessmentStatus
    candidates: tuple[RetrievalCandidate, ...]
    strongest_candidates: tuple[RetrievalCandidate, ...]
    retrieved_candidate_count: int
    eligible_candidate_count: int
    covered_concepts: tuple[str, ...]
    missing_concepts: tuple[str, ...]
    reason_codes: tuple[str, ...]
    decision_details: SemanticDecisionDetails

    @property
    def strongest_evidence_refs(self) -> tuple[str, ...]:
        return tuple(item.evidence.evidence_ref for item in self.strongest_candidates)


def normalize_identity_phrase(value: str) -> str:
    """Normalize representation only; do not add aliases, morphology or synonyms."""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def retrieve_candidates(
    requirement: RequirementSemantics,
    evidence: Iterable[EvidenceSemantics],
    *,
    assisted_evidence_refs: Iterable[str] = (),
) -> tuple[RetrievalCandidate, ...]:
    """Retrieve evidence through exact equality plus scoped human routing."""
    required = {normalize_identity_phrase(value) for value in requirement.concepts if value.strip()}
    assisted_refs = set(assisted_evidence_refs)
    candidates: list[RetrievalCandidate] = []
    for observation in evidence:
        observed = {
            normalize_identity_phrase(value) for value in observation.concepts if value.strip()
        }
        matched = tuple(sorted(required & observed))
        if not matched and observation.evidence_ref not in assisted_refs:
            continue
        candidates.append(
            RetrievalCandidate(
                evidence=observation,
                matched_concepts=tuple(sorted(matched or required)),
                compatibility=evaluate_evidence_compatibility(requirement, observation),
                match_reason=(
                    "human_assisted_evidence_selection"
                    if observation.evidence_ref in assisted_refs and not matched
                    else "identity_phrase_equality"
                ),
            )
        )
    return tuple(sorted(candidates, key=lambda item: item.evidence.evidence_ref))


def assess_retrieval(
    requirement: RequirementSemantics,
    candidates: Iterable[RetrievalCandidate],
    confidence_threshold: float,
) -> SemanticAssessmentProjection:
    """Project candidate compatibility and coverage without making a final decision."""
    retrieved = tuple(candidates)
    required = tuple(
        sorted(
            {
                normalize_identity_phrase(value)
                for value in requirement.concepts
                if value.strip()
            }
        )
    )
    covered = tuple(
        sorted({concept for candidate in retrieved for concept in candidate.matched_concepts})
    )
    missing = (
        tuple(sorted(set(required) - set(covered)))
        if requirement.logical_operator is SemanticLogicalOperator.AND
        else (() if covered else required)
    )
    eligible = tuple(item for item in retrieved if item.compatibility.eligible)
    compatibility_reason_codes = tuple(
        dict.fromkeys(
            code
            for candidate in retrieved
            for code in candidate.compatibility.reason_codes
        )
    )
    strongest_for_details = _strongest(retrieved) if retrieved else ()
    strongest_eligible = _strongest(eligible) if eligible else ()
    details = _decision_details(
        retrieved=retrieved,
        strongest=strongest_eligible or strongest_for_details,
        covered=covered,
        missing=missing,
        required_confidence=confidence_threshold,
        compatibility_reason_codes=compatibility_reason_codes,
        threshold_source=requirement.threshold_source,
        threshold_policy_id=requirement.threshold_policy_id,
        threshold_policy_version=requirement.threshold_policy_version,
    )

    if not retrieved:
        return _projection(
            SemanticAssessmentStatus.NOT_FOUND_IN_EVIDENCE,
            retrieved,
            (),
            eligible,
            covered,
            missing,
            details,
        )
    if not eligible:
        strongest = _strongest(retrieved)
        if "context_mismatch" in compatibility_reason_codes:
            status = SemanticAssessmentStatus.CONTEXT_MISMATCH
        elif any(
            item.compatibility.directness is EvidenceDirectness.INDIRECT
            for item in retrieved
        ):
            status = SemanticAssessmentStatus.REQUIRES_VERIFICATION
        else:
            status = SemanticAssessmentStatus.INSUFFICIENT
        return _projection(
            status,
            retrieved,
            strongest,
            eligible,
            covered,
            missing,
            details,
        )

    strongest = _strongest(eligible)
    if max(item.evidence.confidence for item in strongest) < confidence_threshold:
        status = SemanticAssessmentStatus.INSUFFICIENT
    elif missing:
        status = SemanticAssessmentStatus.REQUIRES_VERIFICATION
    elif any(
        item.compatibility.directness is EvidenceDirectness.DIRECT for item in strongest
    ) or any(_is_demonstrated_context(item.evidence.context) for item in strongest):
        status = SemanticAssessmentStatus.SUPPORTED
    else:
        status = SemanticAssessmentStatus.REQUIRES_VERIFICATION
    return _projection(
        status,
        retrieved,
        strongest,
        eligible,
        covered,
        missing,
        details,
    )


def _strongest(candidates: tuple[RetrievalCandidate, ...]) -> tuple[RetrievalCandidate, ...]:
    strongest_rank = max(item.compatibility.rank for item in candidates)
    return tuple(
        sorted(
            (item for item in candidates if item.compatibility.rank == strongest_rank),
            key=lambda item: item.evidence.evidence_ref,
        )
    )


def _is_demonstrated_context(context: SemanticContext) -> bool:
    return context in {
        SemanticContext.USED_IN_EMPLOYMENT,
        SemanticContext.USED_IN_PROJECT,
        SemanticContext.USED_IN_RESEARCH,
        SemanticContext.USED_IN_PRODUCTION,
        SemanticContext.OWNED_SYSTEM,
        SemanticContext.LED_TEAM,
    }


def _projection(
    status: SemanticAssessmentStatus,
    candidates: tuple[RetrievalCandidate, ...],
    strongest: tuple[RetrievalCandidate, ...],
    eligible: tuple[RetrievalCandidate, ...],
    covered: tuple[str, ...],
    missing: tuple[str, ...],
    details: SemanticDecisionDetails,
) -> SemanticAssessmentProjection:
    return SemanticAssessmentProjection(
        status=status,
        candidates=candidates,
        strongest_candidates=strongest,
        retrieved_candidate_count=len(candidates),
        eligible_candidate_count=len(eligible),
        covered_concepts=covered,
        missing_concepts=missing,
        reason_codes=details.reason_codes,
        decision_details=details,
    )


def _decision_details(
    *,
    retrieved: tuple[RetrievalCandidate, ...],
    strongest: tuple[RetrievalCandidate, ...],
    covered: tuple[str, ...],
    missing: tuple[str, ...],
    required_confidence: float,
    compatibility_reason_codes: tuple[str, ...],
    threshold_source: str,
    threshold_policy_id: str | None,
    threshold_policy_version: str | None,
) -> SemanticDecisionDetails:
    reason_codes: list[AssessmentReasonCode] = []
    if not retrieved:
        reason_codes.append(AssessmentReasonCode.NO_RELEVANT_EVIDENCE)
    for code in compatibility_reason_codes:
        mapped = _map_compatibility_reason(code)
        if mapped is not None and mapped not in reason_codes:
            reason_codes.append(mapped)
    if missing:
        reason_codes.append(AssessmentReasonCode.PARTIAL_SIGNAL_COVERAGE)
    observed_confidence = (
        max(item.evidence.confidence for item in strongest) if strongest else None
    )
    if observed_confidence is not None and observed_confidence < required_confidence:
        reason_codes.append(AssessmentReasonCode.CONFIDENCE_BELOW_THRESHOLD)
    verification_required = any(
        item.compatibility.verification_required for item in strongest
    )
    if verification_required:
        reason_codes.append(AssessmentReasonCode.REQUIRES_EXTERNAL_VERIFICATION)
    if strongest and all(
        item.compatibility.directness is EvidenceDirectness.INDIRECT for item in strongest
    ) and any(item.evidence.context is SemanticContext.MENTIONED for item in strongest):
        reason_codes.append(AssessmentReasonCode.EXPLICIT_MENTION_ONLY)
    if strongest and all(
        item.compatibility.directness is EvidenceDirectness.INDIRECT for item in strongest
    ) and not reason_codes:
        reason_codes.append(AssessmentReasonCode.TARGET_SIGNAL_NOT_SUPPORTED)
    if not reason_codes and not missing and retrieved:
        reason_codes = []
    return SemanticDecisionDetails(
        reason_codes=tuple(dict.fromkeys(item.value for item in reason_codes)),
        supported_signals=covered,
        missing_signals=missing,
        observed_confidence=observed_confidence,
        required_confidence=required_confidence if retrieved else None,
        evidence_directness=(strongest[0].compatibility.directness.value if strongest else None),
        verification_required=verification_required,
        threshold_source=threshold_source,
        threshold_policy_id=threshold_policy_id,
        threshold_policy_version=threshold_policy_version,
    )


def _map_compatibility_reason(code: str) -> AssessmentReasonCode | None:
    if code == "context_mismatch":
        return AssessmentReasonCode.EVIDENCE_CONTEXT_MISMATCH
    if code in {"participation_mismatch", "ownership_evidence_required"}:
        return AssessmentReasonCode.EVIDENCE_PARTICIPATION_MISMATCH
    if code == "demonstrated_usage_required":
        return AssessmentReasonCode.EVIDENCE_TYPE_INCOMPATIBLE
    if code in {
        "source_kind_mismatch",
        "education_evidence_required",
        "credential_evidence_required",
        "unsupported_evidence_expectation",
    }:
        return AssessmentReasonCode.EVIDENCE_TYPE_INCOMPATIBLE
    if code in {"unresolved_constraint", "unsupported_constraint", "invalid_constraint"}:
        return AssessmentReasonCode.TARGET_SIGNAL_NOT_SUPPORTED
    return None
