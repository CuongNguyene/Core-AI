from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.course_catalog.schemas import CourseAvailability, CourseProvenance, ExternalCourse
from app.course_catalog.semantic_enrichment import (
    ENRICHMENT_POLICY_VERSION,
    ClaimReviewStatus,
    CourseCapabilityClaimProposal,
    CourseSemanticEvidence,
    EvidenceStrength,
    MappingMethod,
    MetadataSufficiency,
    RejectionReason,
    build_draft_profile,
    metadata_sufficiency,
    review_claim,
)

UUID = "4f3652e5-82d3-4a78-9b02-73126bb86bc9"


def course() -> ExternalCourse:
    return ExternalCourse(
        provider_ref="skillscommons",
        provider_course_id=UUID,
        title="MAN2582 Introduction to Project Management",
        description="Project planning and delivery course.",
        availability=CourseAvailability.AVAILABLE,
        provenance=[
            CourseProvenance(
                kind="provider",
                source_ref=UUID,
                source_field="uuid",
                method="dspace_rest_hal",
            )
        ],
    )


def evidence(*, strength: EvidenceStrength = EvidenceStrength.TITLE) -> CourseSemanticEvidence:
    return CourseSemanticEvidence(
        source_locator=f"dspace:item:{UUID}:metadata:dc.title",
        source_field="dc.title",
        excerpt="MAN2582 Introduction to Project Management",
        strength=strength,
    )


def proposal(*, ref: str = "project_management") -> CourseCapabilityClaimProposal:
    return CourseCapabilityClaimProposal(
        capability_ref=ref,
        evidence=[evidence()],
        evidence_strength=EvidenceStrength.TITLE,
        mapping_method=MappingMethod.GOVERNED_EXACT_MAPPING,
    )


def test_canonical_source_and_reviewed_draft_profile() -> None:
    reviewed = review_claim(
        proposal(),
        ClaimReviewStatus.ACCEPT,
        rationale="The reviewed source title names the canonical project-management capability exactly.",
    )
    profile = build_draft_profile(course(), [reviewed])

    assert profile is not None
    assert profile.status.value == "draft"
    assert profile.course_ref == f"skillscommons:{UUID}"
    assert profile.capabilities[0].capability_ref == "project_management"
    assert profile.capabilities[0].provenance[0].source_locator.endswith("metadata:dc.title")
    assert profile.target_level is None
    assert profile.prerequisites == []
    assert profile.provenance[-1].evidence_text == ENRICHMENT_POLICY_VERSION


def test_pending_claim_cannot_become_profile_and_empty_enrichment_is_valid() -> None:
    assert build_draft_profile(course(), []) is None
    with pytest.raises(ValueError, match="accepted_claims"):
        build_draft_profile(course(), [proposal()])


def test_noncanonical_ref_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown_canonical_capability_ref"):
        proposal(ref="cap:invented")


def test_evidence_and_locator_are_required() -> None:
    with pytest.raises(ValidationError):
        CourseCapabilityClaimProposal(
            capability_ref="project_management",
            evidence=[],
            evidence_strength=EvidenceStrength.TITLE,
            mapping_method=MappingMethod.MANUAL_REVIEW,
        )
    with pytest.raises(ValidationError, match="dspace_item_locator"):
        CourseSemanticEvidence(
            source_locator="made-up:locator",
            source_field="dc.title",
            excerpt="Project Management",
            strength=EvidenceStrength.TITLE,
        )


def test_duplicate_claim_evidence_and_duplicate_profile_refs_are_rejected() -> None:
    same = evidence()
    with pytest.raises(ValidationError, match="duplicate_claim_evidence_locator"):
        CourseCapabilityClaimProposal(
            capability_ref="project_management",
            evidence=[same, same],
            evidence_strength=EvidenceStrength.TITLE,
            mapping_method=MappingMethod.MANUAL_REVIEW,
        )
    first = review_claim(proposal(), ClaimReviewStatus.ACCEPT, rationale="Reviewed.")
    second = review_claim(proposal(), ClaimReviewStatus.ACCEPT, rationale="Reviewed.")
    with pytest.raises(ValueError, match="duplicate_accepted_capability_ref"):
        build_draft_profile(course(), [first, second])


def test_review_outcomes_require_explicit_reasoning() -> None:
    with pytest.raises(ValueError, match="non_accepted_claim_requires_rejection_reason"):
        review_claim(proposal(), ClaimReviewStatus.REJECT, rationale="Not enough.")
    rejected = review_claim(
        proposal(),
        ClaimReviewStatus.REJECT,
        rationale="Title is only a contextual hint.",
        rejection_reason=RejectionReason.INSUFFICIENT_EVIDENCE,
    )
    assert rejected.review_status is ClaimReviewStatus.REJECT


def test_metadata_sufficiency_does_not_promote_weak_metadata() -> None:
    assert metadata_sufficiency([evidence()]) is MetadataSufficiency.METADATA_PARTIAL
    assert (
        metadata_sufficiency([evidence(strength=EvidenceStrength.EXPLICIT_COURSE_OBJECTIVE)])
        is MetadataSufficiency.METADATA_SUFFICIENT
    )
    assert metadata_sufficiency([]) is MetadataSufficiency.METADATA_INSUFFICIENT


def test_title_subject_occupation_and_industry_are_evidence_not_automatic_claims() -> None:
    # The enrichment API has no automatic field-to-capability mapper by design.
    assert build_draft_profile(course(), []) is None
    for strength in (
        EvidenceStrength.TITLE,
        EvidenceStrength.STRUCTURED_SUBJECT_METADATA,
        EvidenceStrength.OCCUPATION_METADATA,
        EvidenceStrength.INDUSTRY_METADATA,
    ):
        assert metadata_sufficiency([evidence(strength=strength)]) in {
            MetadataSufficiency.METADATA_PARTIAL,
        }
