"""Read-only, reviewer-oriented projection for persisted capability analyses."""

from collections.abc import Mapping

from app.capability_analysis.schemas import (
    CombinedGapPortfolio,
    RequirementAssessment,
    TargetGap,
    VerificationQueueItem,
)
from app.course_authoring.learning_readiness import (
    IncludedLearningItemProjection,
    build_learning_readiness_projection,
)
from app.integration.capability_gap_schemas import (
    CapabilityAssessmentReviewItemV1,
    CapabilityGapReviewProjectionV1,
    CapabilityReviewDecisionV1,
    CapabilityReviewEvidenceV1,
    CapabilityReviewProvenanceV1,
    CapabilityReviewRequirementV1,
    CapabilityReviewSummaryV1,
    CapabilityReviewVerificationV1,
)
from app.learning_need_profile.projection import LearningNeedProjectionService
from app.matching.schemas import RoleCompetencyProfile, RoleRequirement


def build_capability_gap_review_projection(
    portfolio: CombinedGapPortfolio,
    role_profile: RoleCompetencyProfile,
    evidence_by_ref: Mapping[str, CapabilityReviewEvidenceV1],
) -> CapabilityGapReviewProjectionV1:
    """Project one exact role-profile version without recomputing analysis semantics."""
    if (
        role_profile.id != portfolio.current_role.target_id
        or role_profile.version != portfolio.current_target_version
    ):
        raise ValueError("Review projection requires the analyzed role profile version")
    requirements = {item.id: item for item in role_profile.requirements}
    queue_by_requirement: dict[str, VerificationQueueItem] = {
        item.requirement_id: item for item in portfolio.verification_queue
        if item.target_type.value == "current_role"
    }
    gaps_by_requirement: dict[str, TargetGap] = {
        item.requirement_id: item for item in portfolio.current_role.gaps
    }
    assessments = []
    for assessment in portfolio.current_role.assessments:
        requirement = requirements.get(assessment.requirement_id)
        if requirement is None:
            raise ValueError("Review projection cannot resolve assessment requirement")
        assessments.append(
            _assessment_item(
                assessment,
                requirement,
                gaps_by_requirement.get(assessment.requirement_id),
                queue_by_requirement.get(assessment.requirement_id),
                evidence_by_ref,
            )
        )
    counts = {status: 0 for status in (
        "supported", "insufficient", "requires_verification", "context_mismatch",
        "not_found_in_evidence",
    )}
    for item in assessments:
        if item.status in counts:
            counts[item.status] += 1
    try:
        learning_needs = LearningNeedProjectionService().project(
            portfolio=portfolio,
            role_profile=role_profile,
        )
    except ValueError as exc:
        if str(exc) != "candidate_reference_missing":
            raise
        # Legacy in-memory preview fixtures may not carry a candidate id;
        # preserve the existing review projection while failing closed on
        # learning scope.
        learning_needs = []
    readiness = build_learning_readiness_projection(learning_needs)
    learning_by_ref = {item.id: item for item in learning_needs}
    requirement_labels = {
        item.id: "; ".join(item.evidence_terms)
        for item in role_profile.requirements
    }
    included_items = tuple(
        IncludedLearningItemProjection(
            learning_need_ref=reference,
            requirement_ref=learning_by_ref[reference].requirement_reference or learning_by_ref[reference].competency.id,
            label=requirement_labels[learning_by_ref[reference].requirement_reference or learning_by_ref[reference].competency.id],
            assessment_status=learning_by_ref[reference].assessment_status or learning_by_ref[reference].learning_eligibility.value,
            resolution_type=learning_by_ref[reference].resolution_type.value,
        )
        for reference in readiness.included_learning_need_refs
        if reference in learning_by_ref
    )
    readiness = readiness.model_copy(update={"included_learning_items": included_items})
    return CapabilityGapReviewProjectionV1(
        portfolio_id=portfolio.id,
        candidate_reference=portfolio.candidate_id,
        target_reference=f"{role_profile.id}@{role_profile.version}",
        role_profile_state=str(getattr(role_profile.status, "value", role_profile.status)),
        usage_mode=portfolio.current_role.usage_mode.value,
        warnings=list(portfolio.current_role.warning_codes),
        summary=CapabilityReviewSummaryV1(
            total_assessments=len(assessments),
            matched=counts["supported"],
            insufficient=counts["insufficient"],
            requires_verification=counts["requires_verification"],
            context_mismatch=counts["context_mismatch"],
            not_found_in_evidence=counts["not_found_in_evidence"],
            verification_queue_size=len(portfolio.verification_queue),
        ),
        preview_readiness=(
            portfolio.preview_readiness.model_dump(mode="json")
            if portfolio.preview_readiness is not None else None
        ),
        learning_readiness=readiness,
        assessments=assessments,
        verification_queue=[item.model_dump(mode="json") for item in portfolio.verification_queue],
    )


def _assessment_item(
    assessment: RequirementAssessment,
    requirement: RoleRequirement,
    gap: TargetGap | None,
    queue_item: VerificationQueueItem | None,
    evidence_by_ref: Mapping[str, CapabilityReviewEvidenceV1],
) -> CapabilityAssessmentReviewItemV1:
    details = assessment.decision_details
    refs = assessment.matched_evidence_refs
    status = assessment.evidence_status.value
    required = bool(details.verification_required or queue_item is not None)
    return CapabilityAssessmentReviewItemV1(
        id=f"{assessment.target_id}:{assessment.requirement_id}",
        requirement_ref=assessment.requirement_id,
        requirement=CapabilityReviewRequirementV1(
            statement="; ".join(requirement.evidence_terms),
            criterion_dimension=(
                requirement.criterion_dimension.value
                if requirement.criterion_dimension is not None else None
            ),
            modality=requirement.modality,
            priority=requirement.priority,
            target_level=requirement.target_level,
            observable_behaviors=list(requirement.observable_behaviors),
        ),
        status=status,
        candidate_evidence=[evidence_by_ref[ref] for ref in refs if ref in evidence_by_ref],
        decision=CapabilityReviewDecisionV1(
            reason_codes=list(details.reason_codes),
            explanation=_status_explanation(status),
            observed_confidence=details.observed_confidence,
            required_confidence=details.required_confidence,
            evidence_directness=details.evidence_directness,
            verification_required=required,
            threshold_source=details.threshold_source,
        ),
        verification=CapabilityReviewVerificationV1(
            required=required,
            state=queue_item.status.value if queue_item else "not_required",
            reason=(assessment.missing_signals[0] if required and assessment.missing_signals else None),
        ),
        role_provenance=CapabilityReviewProvenanceV1(
            source_requirement_ref=requirement.source_requirement_ref,
            source_locator_display=_locator_display(requirement.source_locator),
        ),
    )


def _status_explanation(status: str) -> str:
    return {
        "supported": "Relevant candidate evidence supports this requirement under the current policy.",
        "insufficient": "Relevant evidence exists, but it is not sufficient for the required judgment.",
        "requires_verification": "Evidence was found, but reviewer verification is required.",
        "context_mismatch": "Related evidence exists, but it does not satisfy the required context.",
        "not_found_in_evidence": (
            "No relevant evidence was found in the current CandidateProfile. "
            "This does not prove the candidate lacks this capability."
        ),
    }.get(status, "The assessment requires reviewer interpretation.")


def _locator_display(locator: object | None) -> str | None:
    if locator is None:
        return None
    page = getattr(locator, "page_number", None)
    section = getattr(locator, "section", None)
    if page is not None:
        return f"Page {page}" + (f" · {section}" if section else "")
    if section:
        return str(section)
    return None
