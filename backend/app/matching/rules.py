from dataclasses import dataclass
from hashlib import sha256

from app.extraction.schemas import CVExtractionOutput, ExtractedClaim, ExtractionProfile
from app.matching.schemas import (
    CriterionResult,
    CriterionStatus,
    EvidenceAllocation,
    MandatoryStatus,
    MatchEvaluation,
    PreliminarySkillGap,
    RequirementClassification,
    RoleCompetencyProfile,
    RoleRequirement,
    SourceEvidence,
)

_CLASSIFICATION_PRIORITY = {
    RequirementClassification.LEGAL_MANDATORY: 0,
    RequirementClassification.ROLE_CRITICAL: 1,
    RequirementClassification.TRAINABLE_MANDATORY: 2,
    RequirementClassification.PREFERRED: 3,
    RequirementClassification.OPTIONAL: 4,
    RequirementClassification.UNCLASSIFIED: 5,
}
_MANDATORY_CLASSIFICATIONS = frozenset(_CLASSIFICATION_PRIORITY.keys()) - {
    RequirementClassification.PREFERRED,
    RequirementClassification.OPTIONAL,
    RequirementClassification.UNCLASSIFIED,
}


@dataclass(frozen=True)
class _CandidateEvidence:
    evidence_id: str
    normalized_value: str
    confidence: float
    source: SourceEvidence


def evaluate_requirements(
    cv_profile: ExtractionProfile, role_profile: RoleCompetencyProfile
) -> MatchEvaluation:
    """Evaluate rules deterministically; eligibility guards belong to the service layer."""
    candidates = _candidate_evidence(cv_profile)
    allocations: list[EvidenceAllocation] = []
    allocated_ids: set[str] = set()
    results: list[CriterionResult] = []
    for requirement in sorted(
        (
            item
            for item in role_profile.requirements
            if item.criterion_dimension is not None
        ),
        key=lambda item: (_CLASSIFICATION_PRIORITY[item.classification], item.id),
    ):
        matching = _matching_candidates(candidates, requirement.evidence_terms)
        conflicting = _matching_candidates(candidates, requirement.conflicting_terms)
        reused_ids = [
            candidate.evidence_id
            for candidate in matching
            if candidate.evidence_id in allocated_ids
        ]
        available = [
            candidate for candidate in matching if candidate.evidence_id not in allocated_ids
        ]
        if matching and conflicting:
            results.append(
                _result(
                    requirement,
                    CriterionStatus.CONFLICTING,
                    [*matching, *conflicting],
                    reused_ids,
                )
            )
            continue
        if not available:
            results.append(_result(requirement, CriterionStatus.INSUFFICIENT, [], reused_ids))
            continue
        best = max(available, key=lambda item: (item.confidence, item.evidence_id))
        status = (
            CriterionStatus.MATCHED
            if best.confidence >= requirement.confidence_threshold
            else CriterionStatus.PARTIAL
        )
        if status is CriterionStatus.MATCHED:
            allocated_ids.add(best.evidence_id)
            allocations.append(
                EvidenceAllocation(evidence_id=best.evidence_id, requirement_id=requirement.id)
            )
        results.append(_result(requirement, status, [best], reused_ids))
    return MatchEvaluation(
        criterion_results=results,
        allocations=allocations,
        preliminary_skill_gaps=[
            PreliminarySkillGap(
                requirement_id=result.requirement_id,
                criterion_dimension=result.criterion_dimension,
                status=result.status,
                mandatory_status=result.mandatory_status,
                recommended_next_assessment=result.recommended_next_assessment,
            )
            for result in results
            if result.status is not CriterionStatus.MATCHED
        ],
    )


def _candidate_evidence(profile: ExtractionProfile) -> list[_CandidateEvidence]:
    if profile.candidate_profile is not None:
        return _graph_candidate_evidence(profile)
    if not isinstance(profile.output, CVExtractionOutput):
        raise ValueError("Preliminary matching requires a CV extraction profile")
    candidates: list[_CandidateEvidence] = []
    for claim in [*profile.output.skills, *profile.output.experience, *profile.output.education]:
        if claim.value is None or claim.source_locator is None:
            continue
        candidates.append(_to_candidate(profile.id, profile.version, claim))
    return candidates


def _graph_candidate_evidence(profile: ExtractionProfile) -> list[_CandidateEvidence]:
    assert profile.candidate_profile is not None
    entities = [
        *profile.candidate_profile.skills,
        *profile.candidate_profile.employment_history,
        *profile.candidate_profile.projects,
        *profile.candidate_profile.research_work,
        *profile.candidate_profile.education,
        *profile.candidate_profile.publications,
        *profile.candidate_profile.credentials,
    ]
    candidates: list[_CandidateEvidence] = []
    for entity in entities:
        for evidence in entity.evidence:
            if evidence.source_locator is None:
                continue
            identity = "|".join(
                [
                    profile.id,
                    str(profile.version),
                    entity.entity_id or entity.__class__.__name__,
                    evidence.context.value,
                    evidence.source_excerpt,
                ]
            )
            evidence_id = sha256(identity.encode()).hexdigest()
            candidates.append(
                _CandidateEvidence(
                    evidence_id=evidence_id,
                    normalized_value=_normalize(_entity_value(entity)),
                    confidence=evidence.confidence,
                    source=SourceEvidence(
                        evidence_id=evidence_id,
                        source_locator=evidence.source_locator,
                        confidence=evidence.confidence,
                    ),
                )
            )
    return candidates


def _entity_value(entity: object) -> str:
    for field in ("entity", "name", "institution", "title"):
        value = getattr(entity, field, None)
        if isinstance(value, str):
            return value
    raise ValueError("Candidate profile entity has no matchable value")


def _to_candidate(
    profile_id: str, profile_version: int, claim: ExtractedClaim
) -> _CandidateEvidence:
    assert claim.value is not None
    assert claim.source_locator is not None
    identity = "|".join(
        [
            profile_id,
            str(profile_version),
            claim.source_locator.document_id,
            claim.source_locator.section,
            str(claim.source_locator.start_offset),
            str(claim.source_locator.end_offset),
            _normalize(claim.value),
        ]
    )
    evidence_id = sha256(identity.encode()).hexdigest()
    return _CandidateEvidence(
        evidence_id=evidence_id,
        normalized_value=_normalize(claim.value),
        confidence=claim.confidence,
        source=SourceEvidence(
            evidence_id=evidence_id,
            source_locator=claim.source_locator,
            confidence=claim.confidence,
        ),
    )


def _matching_candidates(
    candidates: list[_CandidateEvidence], terms: list[str]
) -> list[_CandidateEvidence]:
    normalized_terms = {_normalize(term) for term in terms}
    return [candidate for candidate in candidates if candidate.normalized_value in normalized_terms]


def _result(
    requirement: RoleRequirement,
    status: CriterionStatus,
    candidates: list[_CandidateEvidence],
    reused_ids: list[str],
) -> CriterionResult:
    if requirement.criterion_dimension is None:
        raise ValueError("contextual requirement cannot produce a criterion result")
    mandatory = requirement.classification in _MANDATORY_CLASSIFICATIONS
    mandatory_status = (
        MandatoryStatus.SATISFIED
        if mandatory and status is CriterionStatus.MATCHED
        else MandatoryStatus.UNRESOLVED
        if mandatory
        else MandatoryStatus.NOT_MANDATORY
    )
    return CriterionResult(
        requirement_id=requirement.id,
        criterion_dimension=requirement.criterion_dimension,
        classification=requirement.classification,
        status=status,
        source_evidence=[candidate.source for candidate in candidates],
        reused_evidence_ids=reused_ids,
        confidence=max((candidate.confidence for candidate in candidates), default=None),
        mandatory_status=mandatory_status,
        recommended_next_assessment=requirement.assessment_recommendation,
    )


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())
