"""Governed, reviewable semantic enrichment for external course facts.

This module is intentionally proposal-first. It validates references against
the existing professional capability taxonomy and can build only DRAFT
CourseCapabilityProfile artifacts from explicitly reviewed claims.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.course_catalog.schemas import (
    CourseCapability,
    CourseCapabilityProfile,
    CourseProfileStatus,
    CourseProvenance,
    CourseSourceType,
    CoverageType,
    ExternalCourse,
)
from app.extraction.capability_taxonomy import TAXONOMY_ID, TAXONOMY_VERSION, get_taxonomy

ENRICHMENT_POLICY_VERSION = "skillscommons_course_semantic_enrichment@0.1"


class EvidenceStrength(StrEnum):
    DIRECT_COMPETENCY_STATEMENT = "DIRECT_COMPETENCY_STATEMENT"
    EXPLICIT_LEARNING_OUTCOME = "EXPLICIT_LEARNING_OUTCOME"
    EXPLICIT_COURSE_OBJECTIVE = "EXPLICIT_COURSE_OBJECTIVE"
    STRUCTURED_SUBJECT_METADATA = "STRUCTURED_SUBJECT_METADATA"
    OCCUPATION_METADATA = "OCCUPATION_METADATA"
    INDUSTRY_METADATA = "INDUSTRY_METADATA"
    TITLE = "TITLE"
    ABSTRACT = "ABSTRACT"
    FILE_NAME = "FILE_NAME"
    OTHER = "OTHER"


class MappingMethod(StrEnum):
    MANUAL_REVIEW = "MANUAL_REVIEW"
    GOVERNED_EXACT_MAPPING = "GOVERNED_EXACT_MAPPING"
    SOURCE_EXPLICIT = "SOURCE_EXPLICIT"


class ClaimReviewStatus(StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    UNCERTAIN = "UNCERTAIN"


class RejectionReason(StrEnum):
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    WRONG_CAPABILITY = "WRONG_CAPABILITY"
    TOO_BROAD = "TOO_BROAD"
    TOO_NARROW = "TOO_NARROW"
    SEMANTIC_LEAP = "SEMANTIC_LEAP"
    DUPLICATE = "DUPLICATE"
    OTHER = "OTHER"


class MetadataSufficiency(StrEnum):
    METADATA_SUFFICIENT = "METADATA_SUFFICIENT"
    METADATA_PARTIAL = "METADATA_PARTIAL"
    METADATA_INSUFFICIENT = "METADATA_INSUFFICIENT"


class CourseSemanticEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    source_locator: str = Field(min_length=1)
    source_field: str = Field(min_length=1)
    excerpt: str = Field(min_length=1, max_length=500)
    strength: EvidenceStrength

    @model_validator(mode="after")
    def validate_locator(self) -> Self:
        if not self.source_locator.startswith("dspace:item:"):
            raise ValueError("source_locator_must_be_dspace_item_locator")
        return self


class CourseCapabilityClaimProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    capability_ref: str = Field(min_length=1)
    evidence: list[CourseSemanticEvidence] = Field(min_length=1)
    evidence_strength: EvidenceStrength
    mapping_method: MappingMethod
    review_status: ClaimReviewStatus = ClaimReviewStatus.PENDING_REVIEW
    confidence: float | None = Field(default=None, ge=0, le=1)
    rationale: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_governance(self) -> Self:
        taxonomy = get_taxonomy(TAXONOMY_ID, TAXONOMY_VERSION)
        known = {item.id for item in taxonomy.capabilities}
        if self.capability_ref not in known:
            raise ValueError("unknown_canonical_capability_ref")
        locators = [item.source_locator for item in self.evidence]
        if len(locators) != len(set(locators)):
            raise ValueError("duplicate_claim_evidence_locator")
        if self.review_status is ClaimReviewStatus.ACCEPT and not self.rationale:
            raise ValueError("accepted_claim_requires_review_rationale")
        return self


def review_claim(
    proposal: CourseCapabilityClaimProposal,
    status: ClaimReviewStatus,
    *,
    rationale: str,
    rejection_reason: RejectionReason | None = None,
) -> CourseCapabilityClaimProposal:
    """Apply an explicit human/governed review decision to a proposal."""
    if status is ClaimReviewStatus.ACCEPT and rejection_reason is not None:
        raise ValueError("accepted_claim_cannot_have_rejection_reason")
    if status in {ClaimReviewStatus.REJECT, ClaimReviewStatus.UNCERTAIN} and not rejection_reason:
        raise ValueError("non_accepted_claim_requires_rejection_reason")
    final_rationale = (
        rationale if rejection_reason is None else f"{rationale} [{rejection_reason.value}]"
    )
    return proposal.model_copy(update={"review_status": status, "rationale": final_rationale})


def metadata_sufficiency(evidence: list[CourseSemanticEvidence]) -> MetadataSufficiency:
    strengths = {item.strength for item in evidence}
    if strengths.intersection(
        {
            EvidenceStrength.DIRECT_COMPETENCY_STATEMENT,
            EvidenceStrength.EXPLICIT_LEARNING_OUTCOME,
            EvidenceStrength.EXPLICIT_COURSE_OBJECTIVE,
        }
    ):
        return MetadataSufficiency.METADATA_SUFFICIENT
    if strengths.intersection(
        {
            EvidenceStrength.STRUCTURED_SUBJECT_METADATA,
            EvidenceStrength.OCCUPATION_METADATA,
            EvidenceStrength.INDUSTRY_METADATA,
            EvidenceStrength.TITLE,
            EvidenceStrength.ABSTRACT,
        }
    ):
        return MetadataSufficiency.METADATA_PARTIAL
    return MetadataSufficiency.METADATA_INSUFFICIENT


def build_draft_profile(
    course: ExternalCourse,
    accepted_claims: list[CourseCapabilityClaimProposal],
    *,
    policy_version: str = ENRICHMENT_POLICY_VERSION,
) -> CourseCapabilityProfile | None:
    """Build a DRAFT profile from accepted claims; return None for coverage gaps."""
    if not accepted_claims:
        return None
    if any(claim.review_status is not ClaimReviewStatus.ACCEPT for claim in accepted_claims):
        raise ValueError("draft_profile_requires_accepted_claims")
    refs = [claim.capability_ref for claim in accepted_claims]
    if len(refs) != len(set(refs)):
        raise ValueError("duplicate_accepted_capability_ref")
    capabilities = [
        CourseCapability(
            capability_ref=claim.capability_ref,
            coverage_type=CoverageType.DIRECT,
            target_level=None,
            provenance=[
                CourseProvenance(
                    kind="semantic_evidence",
                    source_ref=course.provider_course_id,
                    source_field=evidence.source_field,
                    source_locator=evidence.source_locator,
                    evidence_text=evidence.excerpt,
                    method=claim.mapping_method.value,
                )
                for evidence in claim.evidence
            ],
        )
        for claim in accepted_claims
    ]
    provenance = [
        *course.provenance,
        CourseProvenance(
            kind="semantic_enrichment_policy",
            source_ref=course.provider_course_id,
            source_field="enrichment_policy",
            evidence_text=policy_version,
            method="governed_review",
        ),
    ]
    return CourseCapabilityProfile(
        id=f"course-profile:{course.provider_ref}:{course.provider_course_id}:semantic",
        version=1,
        course_ref=f"{course.provider_ref}:{course.provider_course_id}",
        source_type=CourseSourceType.EXTERNAL,
        source_system=course.provider_ref,
        provider_ref=course.provider_ref,
        provider_course_id=course.provider_course_id,
        title_snapshot=course.title,
        description_snapshot=course.description,
        capabilities=capabilities,
        prerequisites=[],
        target_level=None,
        duration_minutes=course.duration_minutes,
        delivery_mode=course.delivery_mode,
        language=course.language,
        availability=course.availability,
        status=CourseProfileStatus.DRAFT,
        provenance=provenance,
    )
