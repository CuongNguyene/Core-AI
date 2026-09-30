"""Deterministic semantic-ish evidence retrieval for capability preview analysis.

Domain vocabulary is supplied only by an explicitly selected versioned pack.
"""

import re
from dataclasses import dataclass

from app.capability_analysis.domain_packs.contracts import (
    DomainKnowledgePack,
    DomainSemanticHints,
)
from app.capability_analysis.semantic_core.contracts import (
    EvidenceExpectation,
    SemanticConstraint,
    SemanticConstraintDimension,
    SemanticConstraintOperator,
    SemanticContext,
)
from app.capability_analysis.semantic_core.retrieval import normalize_identity_phrase
from app.extraction.evidence import EvidenceContext, EvidenceItem
from app.extraction.profile import CandidateProfile
from app.matching.schemas import RoleRequirement


@dataclass(frozen=True)
class NormalizationPolicy:
    version: str = "capability-normalization-v1"


@dataclass(frozen=True)
class EvidenceCandidate:
    evidence_id: str
    original_value: str
    canonical_capability: str
    source_excerpt: str
    source_context: EvidenceContext
    original_evidence_type: str | None
    confidence: float
    match_reason: str
    relevance_score: float
    strength_rank: int
    eligible: bool
    eligibility_reason_codes: tuple[str, ...]
    normalization_version: str


_STRENGTH_RANK = {
    EvidenceContext.MENTIONED: 1,
    EvidenceContext.STUDIED: 1,
    EvidenceContext.CREDENTIALED: 1,
    EvidenceContext.UNKNOWN: 1,
    EvidenceContext.USED_IN_PROJECT: 2,
    EvidenceContext.USED_IN_RESEARCH: 2,
    EvidenceContext.USED_IN_EMPLOYMENT: 3,
    EvidenceContext.USED_IN_PRODUCTION: 4,
    EvidenceContext.OWNED_SYSTEM: 4,
    EvidenceContext.LED_TEAM: 3,
}


def normalize_capability(
    value: str,
    policy: NormalizationPolicy | None = None,
    *,
    domain_pack: DomainKnowledgePack | None = None,
) -> str:
    """Return a stable canonical identifier for one supplied capability term."""
    del policy  # reserved for future policy versions
    if domain_pack is not None:
        return domain_pack.normalize_term(value)
    return normalize_identity_phrase(value).replace(" ", "_")


def canonical_concepts(
    text: str,
    policy: NormalizationPolicy | None = None,
    *,
    domain_pack: DomainKnowledgePack | None = None,
) -> set[str]:
    """Return identity only unless an explicit pack supplies vocabulary hints."""
    del policy
    if domain_pack is not None:
        return set(domain_pack.map_evidence_phrase(text).concepts)
    normalized = normalize_identity_phrase(text)
    return {normalized.replace(" ", "_")} if normalized else set()


def retrieve_evidence(
    requirement: RoleRequirement,
    candidate_profile: CandidateProfile,
    normalization_policy: NormalizationPolicy | None = None,
    *,
    domain_pack: DomainKnowledgePack | None = None,
) -> list[EvidenceCandidate]:
    """Retrieve source evidence first; eligibility remains a separate decision."""
    policy = normalization_policy or NormalizationPolicy()
    requirement_hints = tuple(
        _requirement_hints(term, policy, domain_pack)
        for term in requirement.evidence_terms
    )
    required = {concept for hints in requirement_hints for concept in hints.concepts}
    expectations = {
        concept: expectation
        for hints in requirement_hints
        for concept, expectation in hints.evidence_expectations
    }
    constraints = _generic_requirement_constraints(requirement)
    candidates: list[EvidenceCandidate] = []
    for original_value, evidence in _profile_evidence(candidate_profile):
        evidence_concepts = canonical_concepts(
            " ".join([original_value, evidence.source_excerpt]),
            policy,
            domain_pack=domain_pack,
        )
        for concept in sorted(required & evidence_concepts):
            reasons: list[str] = []
            if not _constraints_match(constraints, evidence):
                reasons.append("production_context_required")
            if (
                expectations.get(concept) is EvidenceExpectation.DEMONSTRATED_USAGE
                and evidence.context is EvidenceContext.MENTIONED
            ):
                reasons.append("mention_requires_verification")
            candidates.append(
                EvidenceCandidate(
                    evidence_id=_evidence_id(original_value, evidence),
                    original_value=original_value,
                    canonical_capability=concept,
                    source_excerpt=evidence.source_excerpt,
                    source_context=evidence.context,
                    original_evidence_type=evidence.original_evidence_type,
                    confidence=evidence.confidence,
                    match_reason=f"explicit_alias:{concept}",
                    relevance_score=_relevance(concept, required, evidence.source_excerpt),
                    strength_rank=_STRENGTH_RANK[evidence.context],
                    eligible=not reasons,
                    eligibility_reason_codes=tuple(reasons),
                    normalization_version=(
                        f"{domain_pack.pack_id}@{domain_pack.version}"
                        if domain_pack is not None
                        else policy.version
                    ),
                )
            )
    return sorted(candidates, key=lambda item: (-item.strength_rank, -item.relevance_score, item.evidence_id))


def _profile_evidence(profile: CandidateProfile) -> list[tuple[str, EvidenceItem]]:
    rows: list[tuple[str, EvidenceItem]] = []
    for entity in [
        *profile.skills,
        *profile.employment_history,
        *profile.projects,
        *profile.research_work,
        *profile.education,
        *profile.publications,
        *profile.credentials,
    ]:
        values = [
            getattr(entity, field, None)
            for field in ("entity", "name", "field", "degree", "title", "institution")
        ]
        original_value = next((value for value in values if isinstance(value, str)), None)
        if original_value is None:
            continue
        for item in entity.evidence:
            if item.source_locator is not None:
                rows.append((original_value, item))
    return rows


def _evidence_id(original_value: str, evidence: EvidenceItem) -> str:
    locator = evidence.source_locator
    assert locator is not None
    return "|".join([original_value, evidence.source_excerpt, locator.document_id, str(locator.start_offset)])


def _requirement_hints(
    term: str,
    policy: NormalizationPolicy,
    domain_pack: DomainKnowledgePack | None,
) -> DomainSemanticHints:
    if domain_pack is not None:
        return domain_pack.map_requirement_phrase(term)
    return DomainSemanticHints(concepts=(normalize_capability(term, policy),))


def _generic_requirement_constraints(
    requirement: RoleRequirement,
) -> tuple[SemanticConstraint, ...]:
    if not any(_contains_token(term, "production") for term in requirement.evidence_terms):
        return ()
    return (
        SemanticConstraint(
            dimension=SemanticConstraintDimension.CONTEXT,
            operator=SemanticConstraintOperator.ONE_OF,
            values=(
                SemanticContext.USED_IN_PRODUCTION.value,
                SemanticContext.OWNED_SYSTEM.value,
            ),
            source_field="evidence_terms:legacy_production_token",
            source_reference=requirement.source_requirement_ref,
        ),
    )


def _contains_token(value: str, token: str) -> bool:
    return token in re.findall(r"\w+", normalize_identity_phrase(value))


def _constraints_match(
    constraints: tuple[SemanticConstraint, ...],
    evidence: EvidenceItem,
) -> bool:
    return all(
        constraint.dimension is SemanticConstraintDimension.CONTEXT
        and constraint.operator is SemanticConstraintOperator.ONE_OF
        and evidence.context.value in constraint.values
        for constraint in constraints
    )


def _relevance(concept: str, required: set[str], excerpt: str) -> float:
    normalized_excerpt = normalize_identity_phrase(excerpt).replace(" ", "_")
    return 1.0 if concept in required and concept in normalized_excerpt else 0.8
