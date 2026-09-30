"""Pure, deterministic rules for provisional capability-gap analysis."""

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import replace
from hashlib import sha256
from typing import Protocol

from app.capability_analysis.domain_packs.contracts import DomainKnowledgePack
from app.capability_analysis.evidence_index import build_evidence_index
from app.capability_analysis.retrieval import canonical_concepts, normalize_capability
from app.capability_analysis.schemas import (
    AssessmentDecisionDetails,
    AssessmentEvidenceStatus,
    CapabilityEvidenceStatus,
    CapabilityObservation,
    CapabilitySourceLocator,
    EvidenceStrength,
    GapOverlapLink,
    PreliminaryPriority,
    PreviewReadiness,
    ProvisionalCapability,
    ProvisionalCurrentCapabilityProfile,
    RequirementAssessment,
    TargetGap,
    TargetGapAnalysis,
    TargetType,
    TargetUsageMode,
    VerificationQueueItem,
    VerificationQueueStatus,
    VerificationStatus,
)
from app.capability_analysis.semantic_core.adapters import (
    adapt_evidence_index,
    adapt_role_requirement,
)
from app.capability_analysis.semantic_core.contracts import (
    EvidenceExpectation,
    EvidenceSemantics,
    RequirementSemantics,
    SemanticConstraint,
    SemanticConstraintDimension,
    SemanticConstraintOperator,
    SemanticContext,
    SemanticDecisionDetails,
)
from app.capability_analysis.semantic_core.retrieval import (
    assess_retrieval,
    normalize_identity_phrase,
    retrieve_candidates,
)
from app.extraction.evidence import EvidenceContext, EvidenceItem
from app.extraction.profile import CandidateProfile
from app.extraction.schemas import ExtractionProfile
from app.matching.schemas import (
    RequirementClassification,
    RoleCompetencyProfile,
    RoleRequirement,
)

_CAPABILITY_SUPPORT_THRESHOLD = 0.8
_MISSING_PRIORITY_INPUTS = [
    "business_impact",
    "risk",
    "frequency",
    "deadline",
    "manager_confirmation",
]
_ENVIRONMENT_BY_CONTEXT = {
    EvidenceContext.MENTIONED: "unknown",
    EvidenceContext.USED_IN_EMPLOYMENT: "employment",
    EvidenceContext.STUDIED: "education",
    EvidenceContext.CREDENTIALED: "credential",
    EvidenceContext.USED_IN_PROJECT: "project",
    EvidenceContext.USED_IN_RESEARCH: "research",
    EvidenceContext.USED_IN_PRODUCTION: "production",
    EvidenceContext.OWNED_SYSTEM: "production",
    EvidenceContext.LED_TEAM: "leadership",
}
_EVIDENCE_STRENGTH_BY_CONTEXT = {
    EvidenceContext.MENTIONED.value: EvidenceStrength.MENTION,
    EvidenceContext.STUDIED.value: EvidenceStrength.MENTION,
    EvidenceContext.CREDENTIALED.value: EvidenceStrength.MENTION,
    EvidenceContext.UNKNOWN.value: EvidenceStrength.MENTION,
    EvidenceContext.USED_IN_PROJECT.value: EvidenceStrength.PROJECT,
    EvidenceContext.USED_IN_RESEARCH.value: EvidenceStrength.PROJECT,
    EvidenceContext.USED_IN_EMPLOYMENT.value: EvidenceStrength.WORK,
    EvidenceContext.LED_TEAM.value: EvidenceStrength.WORK,
    EvidenceContext.USED_IN_PRODUCTION.value: EvidenceStrength.PRODUCTION,
    EvidenceContext.OWNED_SYSTEM.value: EvidenceStrength.PRODUCTION,
}
_EVIDENCE_STRENGTH_RANK = {
    EvidenceStrength.MENTION: 1,
    EvidenceStrength.PROJECT: 2,
    EvidenceStrength.WORK: 3,
    EvidenceStrength.PRODUCTION: 4,
}
_PRIORITY_BY_CLASSIFICATION = {
    RequirementClassification.LEGAL_MANDATORY: PreliminaryPriority.HIGH,
    RequirementClassification.ROLE_CRITICAL: PreliminaryPriority.HIGH,
    RequirementClassification.TRAINABLE_MANDATORY: PreliminaryPriority.MEDIUM,
    RequirementClassification.PREFERRED: PreliminaryPriority.LOW,
    RequirementClassification.OPTIONAL: PreliminaryPriority.LOW,
    RequirementClassification.UNCLASSIFIED: PreliminaryPriority.LOW,
}


class _EvidenceBackedEntity(Protocol):
    entity_id: str | None
    evidence: list[EvidenceItem]


def build_provisional_capability_profile(
    profile: ExtractionProfile,
) -> ProvisionalCurrentCapabilityProfile:
    """Create a source-preserving, unverified snapshot from graph evidence only."""
    evidence_index = build_evidence_index(profile)
    candidate_profile = evidence_index.candidate_profile

    capabilities_by_id: dict[str, list[tuple[_EvidenceBackedEntity, list[EvidenceItem]]]] = (
        defaultdict(list)
    )
    for entity in _candidate_entities(candidate_profile):
        for capability_id in _entity_capability_ids(entity):
            capabilities_by_id[capability_id].append((entity, entity.evidence))

    capabilities = [
        _capability(profile, capability_id, values)
        for capability_id, values in sorted(capabilities_by_id.items())
    ]
    return ProvisionalCurrentCapabilityProfile(
        source_profile_id=profile.id,
        source_profile_version=profile.version,
        capabilities=tuple(capabilities),
        semantic_evidence=adapt_evidence_index(evidence_index),
    )


def evaluate_target(
    capability_profile: ProvisionalCurrentCapabilityProfile,
    target: RoleCompetencyProfile,
    target_type: TargetType,
    usage_mode: TargetUsageMode,
    *,
    domain_packs: tuple[DomainKnowledgePack, ...] = (),
    assisted_evidence_by_requirement: Mapping[str, tuple[str, ...]] | None = None,
) -> TargetGapAnalysis:
    """Evaluate each target requirement independently; no cross-target allocation occurs."""
    assessments_and_gaps = [
        _evaluate_requirement(
            capability_profile,
            target,
            requirement,
            target_type,
            domain_packs,
            tuple((assisted_evidence_by_requirement or {}).get(requirement.id, ())),
        )
        for requirement in sorted(
            (
                item
                for item in target.requirements
                if item.criterion_dimension is not None
            ),
            key=lambda item: item.id,
        )
    ]
    assessments = [item[0] for item in assessments_and_gaps]
    gaps = [item[1] for item in assessments_and_gaps if item[1] is not None]
    warning_codes = (
        ["future_target_profile_provisional"]
        if target_type is TargetType.FUTURE_ROLE and usage_mode is TargetUsageMode.PREVIEW
        else []
    )
    return TargetGapAnalysis(
        target_id=target.id,
        target_type=target_type,
        usage_mode=usage_mode,
        assessments=assessments,
        gaps=gaps,
        warning_codes=warning_codes,
    )


def build_gap_overlap_links(
    current: TargetGapAnalysis, future: TargetGapAnalysis
) -> list[GapOverlapLink]:
    """Link shared requirement-evidence keys without merging either target's gaps."""
    if current.target_type is not TargetType.CURRENT_ROLE:
        raise ValueError("Overlap source analysis must be a current-role track")
    if future.target_type is not TargetType.FUTURE_ROLE:
        raise ValueError("Overlap target analysis must be a future-role track")

    links: list[GapOverlapLink] = []
    for source_gap in sorted(current.gaps, key=lambda item: item.id):
        source_keys = set(source_gap.overlap_keys)
        for target_gap in sorted(future.gaps, key=lambda item: item.id):
            shared_requirement_keys = sorted(source_keys & set(target_gap.overlap_keys))
            if not shared_requirement_keys:
                continue
            links.append(
                GapOverlapLink(
                    source_gap_id=source_gap.id,
                    target_gap_id=target_gap.id,
                    shared_theme=shared_requirement_keys[0],
                )
            )
    return links


def build_preview_readiness(analysis: TargetGapAnalysis) -> PreviewReadiness:
    if analysis.usage_mode is not TargetUsageMode.PREVIEW:
        raise ValueError("Preview readiness requires preview analysis")
    return PreviewReadiness()


def build_verification_queue(analysis: TargetGapAnalysis) -> list[VerificationQueueItem]:
    items = [
        VerificationQueueItem(
            requirement_id=assessment.requirement_id,
            target_type=assessment.target_type,
            evidence_status=assessment.evidence_status,
            status=(
                VerificationQueueStatus.RECOMMENDED
                if assessment.evidence_status is AssessmentEvidenceStatus.REQUIRES_VERIFICATION
                else VerificationQueueStatus.PENDING
            ),
            evidence_refs=tuple(assessment.matched_evidence_refs),
        )
        for assessment in analysis.assessments
        if assessment.evidence_status is not AssessmentEvidenceStatus.SUPPORTED
    ]
    return sorted(items, key=lambda item: item.requirement_id)


def _candidate_entities(candidate_profile: CandidateProfile) -> Iterable[_EvidenceBackedEntity]:
    return (
        *candidate_profile.skills,
        *candidate_profile.employment_history,
        *candidate_profile.projects,
        *candidate_profile.research_work,
        *candidate_profile.education,
        *candidate_profile.publications,
        *candidate_profile.credentials,
    )


def _entity_value(entity: object) -> str:
    for field in ("entity", "name", "institution", "title"):
        value = getattr(entity, field, None)
        if isinstance(value, str):
            return value
    raise ValueError("CandidateProfile entity has no capability value")


def _entity_capability_ids(entity: _EvidenceBackedEntity) -> set[str]:
    values = [
        getattr(entity, field, None)
        for field in ("entity", "name", "field", "degree", "title", "institution")
    ]
    labels = [value for value in values if isinstance(value, str)]
    identifiers = {normalize_capability(label) for label in labels}
    # Skill labels are already atomic; only contextual entities may contribute
    # explicit aliases from their source excerpts (e.g. Kafka/Spark in a project).
    if entity.__class__.__name__ == "SkillEntity":
        identifiers.update(canonical_concepts(" ".join(labels)))
    else:
        identifiers.update(
            canonical_concepts(
                " ".join([*labels, *(item.source_excerpt for item in entity.evidence)])
            )
        )
    return {item for item in identifiers if item}


def _capability(
    profile: ExtractionProfile,
    capability_id: str,
    entity_evidence: list[tuple[_EvidenceBackedEntity, list[EvidenceItem]]],
) -> ProvisionalCapability:
    observations = [
        _observation(
            profile,
            capability_id,
            entity,
            evidence,
            _entity_original_value(entity, capability_id),
        )
        for entity, evidence_items in entity_evidence
        for evidence in evidence_items
        if evidence.source_locator is not None
    ]
    all_evidence = [
        evidence for _, evidence_items in entity_evidence for evidence in evidence_items
    ]
    if _has_material_source_backed_conflict(capability_id, all_evidence):
        status = CapabilityEvidenceStatus.CONFLICTING
    elif observations:
        status = (
            CapabilityEvidenceStatus.SUPPORTED
            if max(item.confidence for item in observations) >= _CAPABILITY_SUPPORT_THRESHOLD
            else CapabilityEvidenceStatus.PARTIAL
        )
    elif all_evidence:
        status = CapabilityEvidenceStatus.INSUFFICIENT
    else:
        status = CapabilityEvidenceStatus.NOT_FOUND_IN_EVIDENCE
    return ProvisionalCapability(
        capability_id=capability_id,
        status=status,
        verification_status=VerificationStatus.PROVISIONAL,
        observations=tuple(sorted(observations, key=lambda item: item.evidence_ref)),
    )


def _has_material_source_backed_conflict(
    capability_id: str, evidence_items: list[EvidenceItem]
) -> bool:
    """Require both positive and explicitly negative source-backed observations."""
    source_backed_excerpts = [
        _normalize(item.source_excerpt)
        for item in evidence_items
        if item.source_locator is not None
    ]
    negative = [
        excerpt
        for excerpt in source_backed_excerpts
        if _is_explicitly_negative_for(capability_id, excerpt)
    ]
    positive = [
        excerpt
        for excerpt in source_backed_excerpts
        if _has_token_safe_phrase(excerpt, capability_id)
        and not _is_explicitly_negative_for(capability_id, excerpt)
    ]
    return bool(positive and negative)


def _is_explicitly_negative_for(capability_id: str, excerpt: str) -> bool:
    return any(
        _has_token_safe_phrase(excerpt, marker)
        for marker in (
            f"no {capability_id}",
            f"without {capability_id}",
            f"lack {capability_id}",
            f"lacks {capability_id}",
            f"not {capability_id}",
        )
    )


def _has_token_safe_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


def _observation(
    profile: ExtractionProfile,
    capability_id: str,
    entity: _EvidenceBackedEntity,
    evidence: EvidenceItem,
    original_value: str,
) -> CapabilityObservation:
    assert evidence.source_locator is not None
    identity = "|".join(
        [
            profile.id,
            str(profile.version),
            getattr(entity, "entity_id", None) or entity.__class__.__name__,
            capability_id,
            evidence.context.value,
            evidence.source_excerpt,
            evidence.source_locator.document_id,
            evidence.source_locator.section,
            str(evidence.source_locator.start_offset),
            str(evidence.source_locator.end_offset),
        ]
    )
    return CapabilityObservation(
        evidence_ref=sha256(identity.encode()).hexdigest(),
        source_locator=CapabilitySourceLocator.model_validate(evidence.source_locator.model_dump()),
        environment=_ENVIRONMENT_BY_CONTEXT[evidence.context],
        context=evidence.context.value,
        participation=evidence.usage,
        confidence=evidence.confidence,
        explicit_production_claim=(
            evidence.context is EvidenceContext.USED_IN_EMPLOYMENT
            and _has_token_safe_phrase(_normalize(evidence.source_excerpt), "production")
        ),
        original_value=original_value,
        source_excerpt=evidence.source_excerpt,
        original_evidence_type=evidence.original_evidence_type,
    )


def _entity_original_value(entity: object, capability_id: str) -> str:
    values = [
        getattr(entity, field, None)
        for field in ("entity", "name", "field", "degree", "title", "institution")
    ]
    for value in values:
        if isinstance(value, str) and (
            normalize_capability(value) == capability_id
            or capability_id in canonical_concepts(value)
        ):
            return value
    return _entity_value(entity)


def _evaluate_requirement(
    capability_profile: ProvisionalCurrentCapabilityProfile,
    target: RoleCompetencyProfile,
    requirement: RoleRequirement,
    target_type: TargetType,
    domain_packs: tuple[DomainKnowledgePack, ...],
    assisted_evidence_refs: tuple[str, ...] = (),
) -> tuple[RequirementAssessment, TargetGap | None]:
    production_required = _requires_production(requirement)
    (
        evidence_status,
        evidence_strength,
        matched_refs,
        retrieved_candidate_count,
        eligible_candidate_count,
        semantic_decision_details,
    ) = _assess_evidence(
        capability_profile.semantic_evidence,
        requirement,
        production_required,
        domain_packs,
        assisted_evidence_refs,
    )
    missing_signals = _missing_signals(evidence_status)
    if evidence_status is AssessmentEvidenceStatus.INSUFFICIENT and matched_refs:
        missing_signals = [
            "Source-backed evidence is incomplete or below the target confidence threshold."
        ]
    rationale = _rationale(target, target_type, requirement, missing_signals)
    decision_details = _assessment_decision_details(semantic_decision_details)
    priority = _PRIORITY_BY_CLASSIFICATION[requirement.classification]
    assessment = RequirementAssessment(
        target_id=target.id,
        target_type=target_type,
        requirement_id=requirement.id,
        matched_evidence_refs=matched_refs,
        missing_signals=missing_signals,
        rationale=rationale,
        preliminary_priority=priority,
        missing_priority_inputs=list(_MISSING_PRIORITY_INPUTS),
        evidence_status=evidence_status,
        evidence_strength=evidence_strength,
        production_required=production_required,
        retrieved_candidate_count=retrieved_candidate_count,
        eligible_candidate_count=eligible_candidate_count,
        decision_details=decision_details,
        recommendation=requirement.assessment_recommendation,
    )
    if not missing_signals:
        return assessment, None
    gap = TargetGap(
        id=_gap_id(target.id, target_type, requirement.id),
        target_id=target.id,
        target_type=target_type,
        requirement_id=requirement.id,
        matched_evidence_refs=matched_refs,
        missing_signals=missing_signals,
        rationale=rationale,
        preliminary_priority=priority,
        missing_priority_inputs=list(_MISSING_PRIORITY_INPUTS),
        evidence_status=evidence_status,
        evidence_strength=evidence_strength,
        production_required=production_required,
        retrieved_candidate_count=retrieved_candidate_count,
        eligible_candidate_count=eligible_candidate_count,
        overlap_keys=_normalized_requirement_evidence_keys(requirement),
        decision_details=decision_details,
        recommendation=requirement.assessment_recommendation,
    )
    return assessment, gap


def _requires_production(requirement: RoleRequirement) -> bool:
    return any(_contains_production_token(term) for term in requirement.evidence_terms)


def _contains_production_token(value: str) -> bool:
    normalized = normalize_identity_phrase(value)
    return "production" in re.findall(r"\w+", normalized)


def _without_production_token(value: str) -> str:
    normalized = normalize_identity_phrase(value)
    remainder = re.sub(r"(?<!\w)production(?!\w)", " ", normalized)
    return normalize_identity_phrase(remainder).strip(" -_/,:;")


def _assess_evidence(
    evidence: tuple[EvidenceSemantics, ...],
    requirement: RoleRequirement,
    production_required: bool,
    domain_packs: tuple[DomainKnowledgePack, ...],
    assisted_evidence_refs: tuple[str, ...] = (),
) -> tuple[
    AssessmentEvidenceStatus,
    EvidenceStrength | None,
    list[str],
    int,
    int,
    SemanticDecisionDetails,
]:
    semantic_requirement = _semantic_requirement(
        requirement,
        production_required,
        domain_packs=domain_packs,
    )
    semantic_evidence = _semantic_evidence_with_packs(evidence, domain_packs)
    candidates = retrieve_candidates(
        semantic_requirement,
        semantic_evidence,
        assisted_evidence_refs=assisted_evidence_refs,
    )
    projection = assess_retrieval(
        semantic_requirement,
        candidates,
        requirement.confidence_threshold,
    )
    strongest_evidence = tuple(item.evidence for item in projection.strongest_candidates)
    strength = _strongest_semantic_strength(strongest_evidence)
    refs = sorted(item.evidence_ref for item in strongest_evidence)
    return (
        AssessmentEvidenceStatus(projection.status.value),
        strength,
        refs,
        projection.retrieved_candidate_count,
        projection.eligible_candidate_count,
        projection.decision_details,
    )


def _semantic_requirement(
    requirement: RoleRequirement,
    production_required: bool,
    domain_packs: tuple[DomainKnowledgePack, ...] = (),
) -> RequirementSemantics:
    semantics = adapt_role_requirement(requirement)
    concepts = tuple(
        remainder
        for term in requirement.evidence_terms
        if (
            remainder := (
                _without_production_token(term)
                if _contains_production_token(term)
                else term
            )
        )
    )
    if production_required:
        production_constraint = SemanticConstraint(
            dimension=SemanticConstraintDimension.CONTEXT,
            operator=SemanticConstraintOperator.ONE_OF,
            values=(
                SemanticContext.USED_IN_PRODUCTION.value,
                SemanticContext.OWNED_SYSTEM.value,
            ),
            source_field="evidence_terms:legacy_exact_production",
            source_reference=requirement.source_requirement_ref,
        )
        constraints = (*semantics.constraints, production_constraint)
    else:
        constraints = semantics.constraints
    semantics = replace(
        semantics,
        concepts=concepts,
        constraints=tuple(constraints),
    )
    return _requirement_with_packs(semantics, domain_packs)


def _requirement_with_packs(
    requirement: RequirementSemantics,
    domain_packs: tuple[DomainKnowledgePack, ...],
) -> RequirementSemantics:
    if not domain_packs:
        return requirement
    concepts: set[str] = set()
    expectation = requirement.evidence_expectation
    for phrase in requirement.concepts:
        mapped_phrase = False
        for pack in domain_packs:
            hints = pack.map_requirement_phrase(phrase)
            if hints.concepts:
                concepts.update(hints.concepts)
                mapped_phrase = True
            for _concept, hinted_expectation in hints.evidence_expectations:
                if (
                    expectation is EvidenceExpectation.UNKNOWN
                    and hinted_expectation is not EvidenceExpectation.UNKNOWN
                ):
                    expectation = hinted_expectation
        if not mapped_phrase:
            concepts.add(phrase)
    return replace(
        requirement,
        concepts=tuple(sorted(concepts)),
        evidence_expectation=expectation,
    )


def _semantic_evidence_with_packs(
    evidence: tuple[EvidenceSemantics, ...],
    domain_packs: tuple[DomainKnowledgePack, ...],
) -> tuple[EvidenceSemantics, ...]:
    if not domain_packs:
        return evidence
    transformed: list[EvidenceSemantics] = []
    for item in evidence:
        concepts = {
            concept
            for pack in domain_packs
            for phrase in (*item.concepts, *item.behaviors, *item.objects, item.source_value)
            for concept in pack.map_evidence_phrase(phrase).concepts
        }
        transformed.append(
            replace(
                item,
                concepts=tuple(sorted(concepts)) if concepts else item.concepts,
            )
        )
    return tuple(transformed)


def _assessment_decision_details(
    details: SemanticDecisionDetails,
) -> AssessmentDecisionDetails:
    return AssessmentDecisionDetails(
        reason_codes=list(details.reason_codes),
        supported_signals=list(details.supported_signals),
        missing_signals=list(details.missing_signals),
        observed_confidence=details.observed_confidence,
        required_confidence=details.required_confidence,
        evidence_directness=details.evidence_directness,
        verification_required=details.verification_required,
        threshold_source=details.threshold_source,
        threshold_policy_id=details.threshold_policy_id,
        threshold_policy_version=details.threshold_policy_version,
    )


def _strongest_semantic_strength(
    evidence: tuple[EvidenceSemantics, ...],
) -> EvidenceStrength | None:
    if not evidence:
        return None
    return max(
        (_EVIDENCE_STRENGTH_BY_CONTEXT[item.context.value] for item in evidence),
        key=_EVIDENCE_STRENGTH_RANK.__getitem__,
    )


def _missing_signals(status: AssessmentEvidenceStatus) -> list[str]:
    if status is AssessmentEvidenceStatus.CONFLICTING:
        return ["Source-backed evidence materially conflicts and requires human review."]
    if status is AssessmentEvidenceStatus.NOT_FOUND_IN_EVIDENCE:
        return [
            "No matching source-backed evidence was found; this does not establish absence of capability."
        ]
    if status is AssessmentEvidenceStatus.CONTEXT_MISMATCH:
        return ["Source-backed evidence does not meet the explicit production context required."]
    if status is AssessmentEvidenceStatus.INSUFFICIENT:
        return ["Available evidence cannot support the required judgment."]
    if status is AssessmentEvidenceStatus.REQUIRES_VERIFICATION:
        return ["Evidence is an explicit mention and requires verification."]
    return []


def _rationale(
    target: RoleCompetencyProfile,
    target_type: TargetType,
    requirement: RoleRequirement,
    missing_signals: list[str],
) -> str:
    outcome = "requires a provisional gap" if missing_signals else "is source-backed"
    return f"Target {target.id} ({target_type.value}) requirement {requirement.id} {outcome}."


def _gap_id(target_id: str, target_type: TargetType, requirement_id: str) -> str:
    identity = "|".join([target_id, target_type.value, requirement_id])
    return f"gap-{sha256(identity.encode()).hexdigest()}"


def _normalized_requirement_evidence_keys(requirement: RoleRequirement) -> list[str]:
    return sorted({_normalize(term) for term in requirement.evidence_terms})


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())
