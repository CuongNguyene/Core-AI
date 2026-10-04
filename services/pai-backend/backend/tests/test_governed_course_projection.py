from __future__ import annotations

import pytest

from app.capability_governance.course_projection import (
    CourseProjectionError,
    DirectCourseCapabilityClaim,
    GovernedDirectClaimMappingInput,
    GovernedOutcomeMappingInput,
    project_governed_course_capabilities,
)
from app.capability_governance.definitions import CapabilityDefinition, CapabilityDefinitionStatus
from app.capability_governance.direct_claim_identity import make_direct_claim_source_id
from app.capability_governance.evidence import SemanticEvidence, SemanticEvidenceKind
from app.capability_governance.governed_mapping import (
    activate_governed_mapping,
    deprecate_governed_mapping,
)
from app.capability_governance.identity import SourceSemanticKind, SourceSemanticRef
from app.capability_governance.mapping import (
    CapabilityMappingProposal,
    CapabilityMappingReview,
    MappingDecision,
    MappingScope,
    MappingType,
    ProposalMethod,
)
from app.capability_governance.mapping_activation import (
    MappingActivationApproval,
    build_source_semantic_pin,
    fingerprint_mapping_review,
)
from app.capability_governance.mapping_errors import MappingGovernanceError
from app.capability_governance.outcomes import CourseLearningOutcome
from app.capability_governance.packs import (
    CapabilityGovernanceDecision,
    CapabilityGovernanceReview,
    CapabilityReleaseApproval,
    activate_capability_pack_release,
    build_capability_pack_release,
)
from app.course_catalog.schemas import (
    CourseAvailability,
    CourseCapability,
    CourseCapabilityProfile,
    CoursePrerequisite,
    CourseProfileStatus,
    CourseProvenance,
    CourseSourceType,
    CoverageType,
)

COURSE_REF = "skillscommons:course-123"
CAPABILITY_REF = "capability:test_core:project_management"


def _source(
    kind: SourceSemanticKind,
    source_id: str,
    version: str = "v1",
    namespace: str = "skillscommons",
) -> SourceSemanticRef:
    return SourceSemanticRef(
        source_namespace=namespace,
        entity_kind=kind,
        source_id=source_id,
        source_version=version,
    )


def _evidence(source: SourceSemanticRef, locator: str, text: str) -> SemanticEvidence:
    return SemanticEvidence(
        source_ref=source,
        source_locator=locator,
        evidence_text=text,
        evidence_kind=(
            SemanticEvidenceKind.EXPLICIT_OUTCOME
            if source.entity_kind is SourceSemanticKind.COURSE_LEARNING_OUTCOME
            else SemanticEvidenceKind.DIRECT_CAPABILITY_STATEMENT
        ),
    )


def _active_release():
    draft = build_capability_pack_release(
        pack_id="test_core_pack",
        namespace_key="test_core",
        version="1.0",
        owner_ref="team:governance",
        definitions=(
            CapabilityDefinition(
                canonical_ref=CAPABILITY_REF,
                label="Project Management",
                definition="Plan and coordinate project work.",
                status=CapabilityDefinitionStatus.DRAFT,
            ),
        ),
    )
    return activate_capability_pack_release(
        draft,
        review=CapabilityGovernanceReview(
            review_ref="review:test-core:1.0",
            reviewer_ref="actor:reviewer",
            decision=CapabilityGovernanceDecision.APPROVE,
            collision_review_ref="collision:test-core:1.0",
        ),
        approval=CapabilityReleaseApproval(
            approval_ref="approval:test-core:1.0",
            approver_ref="actor:approver",
            decision=CapabilityGovernanceDecision.APPROVE,
        ),
    )


def _mapping(
    source: SourceSemanticRef, evidence: tuple[SemanticEvidence, ...], scope: MappingScope
):
    proposal = CapabilityMappingProposal(
        proposal_id=f"proposal:{source.source_id}",
        source_ref=source,
        target_capability_ref=CAPABILITY_REF,
        mapping_type=MappingType.EXACT,
        mapping_scope=scope,
        evidence=evidence,
        proposal_method=ProposalMethod.MANUAL,
        proposer_ref="actor:proposer",
    )
    review = CapabilityMappingReview(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
        reviewer_ref="actor:independent-reviewer",
        decision=MappingDecision.APPROVE,
        rationale="Exact bounded course semantic reviewed.",
    )
    release = _active_release()
    definition = next(
        item for item in release.definitions if str(item.canonical_ref) == CAPABILITY_REF
    )
    from app.capability_governance.packs import CapabilityPackReleaseRef
    from app.capability_governance.resolution import CapabilityDefinitionPin

    target_pin = CapabilityDefinitionPin(
        capability_ref=definition.canonical_ref,
        pack_release_ref=CapabilityPackReleaseRef(
            pack_id=release.pack_id,
            version=release.version,
            checksum=release.content_checksum,
        ),
    )
    approval = MappingActivationApproval(
        approval_ref=f"approval:{source.source_id}",
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
        review_fingerprint=fingerprint_mapping_review(review),
        source_pin=build_source_semantic_pin(source, evidence),
        target_definition_pin=target_pin,
        approver_ref="actor:approver",
    )
    mapping = activate_governed_mapping(
        mapping_id=f"mapping:{source.source_id}",
        proposal=proposal,
        review=review,
        current_source_pin=build_source_semantic_pin(source, evidence),
        activation_approval=approval,
        active_release_context=(release,),
    )
    return mapping, release


def _profile(
    status: CourseProfileStatus = CourseProfileStatus.DRAFT,
    capability_ref: str = CAPABILITY_REF,
) -> CourseCapabilityProfile:
    return CourseCapabilityProfile(
        id="profile:skillscommons:course-123",
        version=1,
        course_ref=COURSE_REF,
        source_type=CourseSourceType.EXTERNAL,
        source_system="skillscommons",
        provider_ref="skillscommons",
        provider_course_id="course-123",
        title_snapshot="Source title",
        description_snapshot="Provider description",
        capabilities=[
            CourseCapability(
                capability_ref=capability_ref,
                coverage_type=CoverageType.SUPPORTING,
                target_level=None,
                provenance=[
                    CourseProvenance(kind="legacy", source_ref=COURSE_REF, method="fixture")
                ],
            )
        ],
        prerequisites=[
            CoursePrerequisite(
                kind="capability",
                ref="capability:test_core:foundations",
                provenance=[
                    CourseProvenance(
                        kind="explicit_prerequisite", source_ref=COURSE_REF, method="fixture"
                    )
                ],
            )
        ],
        target_level="explicit_source_level",
        status=status,
        availability=CourseAvailability.AVAILABLE,
        duration_minutes=90,
        language="en",
        provenance=[CourseProvenance(kind="provider", source_ref=COURSE_REF, method="fixture")],
    )


def _outcome_input():
    source = _source(SourceSemanticKind.COURSE_LEARNING_OUTCOME, "course-123#outcome-1")
    outcome = CourseLearningOutcome(
        outcome_ref=source,
        course_ref=COURSE_REF,
        statement="Plan and coordinate project work.",
        source_locator="course:course-123:outcome:1",
    )
    evidence = (_evidence(source, outcome.source_locator, outcome.statement),)
    mapping, release = _mapping(source, evidence, MappingScope.OUTCOME_CAPABILITY_FACET)
    return GovernedOutcomeMappingInput(outcome=outcome, evidence=evidence, mapping=mapping), release


def _direct_input():
    claim_id = "claim-1"
    source = _source(
        SourceSemanticKind.COURSE_DIRECT_CLAIM,
        make_direct_claim_source_id(course_ref=COURSE_REF, claim_id=claim_id),
    )
    evidence = (
        _evidence(source, "course:course-123:claim:1", "Directly teaches project planning."),
    )
    mapping, release = _mapping(source, evidence, MappingScope.DIRECT_CAPABILITY_CLAIM)
    claim = DirectCourseCapabilityClaim(
        course_ref=COURSE_REF, claim_id=claim_id, source_ref=source, evidence=evidence
    )
    return GovernedDirectClaimMappingInput(claim=claim, mapping=mapping), release


def test_outcome_projection_keeps_course_source_and_exact_definition_provenance() -> None:
    outcome_input, release = _outcome_input()

    result = project_governed_course_capabilities(
        _profile(), outcomes=(outcome_input,), active_release_context=(release,)
    )

    assert result.course_ref == COURSE_REF
    assert len(result.coverage) == 1
    assert result.coverage[0].capability_ref.root == CAPABILITY_REF
    assert result.coverage[0].sources[0].source_ref == outcome_input.outcome.outcome_ref
    assert (
        result.coverage[0].sources[0].definition_pin == outcome_input.mapping.target_definition_pin
    )
    assert result.profile_candidate.status is CourseProfileStatus.DRAFT
    assert result.profile_candidate.target_level == "explicit_source_level"
    assert result.profile_candidate.prerequisites[0].ref == "capability:test_core:foundations"
    assert result.profile_candidate.duration_minutes == 90
    assert result.profile_candidate.availability is CourseAvailability.AVAILABLE
    assert result.normalized_candidate is None


def test_direct_claim_projects_without_fabricating_an_outcome() -> None:
    direct_input, release = _direct_input()

    result = project_governed_course_capabilities(
        _profile(), direct_claims=(direct_input,), active_release_context=(release,)
    )

    assert result.coverage[0].sources[0].source_ref == direct_input.claim.source_ref
    assert (
        result.coverage[0].sources[0].source_ref.entity_kind
        is SourceSemanticKind.COURSE_DIRECT_CLAIM
    )


def test_internal_course_uses_same_provider_neutral_projection_path() -> None:
    course_ref = "frappe_lms:course-9"
    source = _source(
        SourceSemanticKind.COURSE_LEARNING_OUTCOME,
        "course-9#outcome-1",
        namespace="frappe_lms",
    )
    outcome = CourseLearningOutcome(
        outcome_ref=source,
        course_ref=course_ref,
        statement="Coordinate a project plan.",
        source_locator="lms:course-9:outcome:1",
    )
    evidence = (_evidence(source, outcome.source_locator, outcome.statement),)
    mapping, release = _mapping(source, evidence, MappingScope.OUTCOME_CAPABILITY_FACET)
    profile = CourseCapabilityProfile(
        id="profile:lms:course-9",
        version=1,
        course_ref=course_ref,
        source_type=CourseSourceType.INTERNAL,
        source_system="frappe_lms",
        title_snapshot="Internal course",
        capabilities=[
            CourseCapability(
                capability_ref=CAPABILITY_REF,
                coverage_type=CoverageType.DIRECT,
                provenance=[
                    CourseProvenance(kind="existing", source_ref=course_ref, method="fixture")
                ],
            )
        ],
        status=CourseProfileStatus.DRAFT,
        provenance=[CourseProvenance(kind="source", source_ref=course_ref, method="fixture")],
    )

    result = project_governed_course_capabilities(
        profile,
        outcomes=(
            GovernedOutcomeMappingInput(outcome=outcome, evidence=evidence, mapping=mapping),
        ),
        active_release_context=(release,),
    )

    assert result.course_ref == course_ref
    assert result.profile_candidate.source_type is CourseSourceType.INTERNAL


def test_internal_direct_claim_uses_exact_course_ref_identity() -> None:
    course_ref = "frappe_lms:course-9"
    claim_id = "claim/with:#separators"
    source = _source(
        SourceSemanticKind.COURSE_DIRECT_CLAIM,
        make_direct_claim_source_id(course_ref=course_ref, claim_id=claim_id),
        namespace="frappe_lms",
    )
    evidence = (_evidence(source, "lms:course-9:claim:1", "Direct course claim."),)
    mapping, release = _mapping(source, evidence, MappingScope.DIRECT_CAPABILITY_CLAIM)
    profile = CourseCapabilityProfile(
        id="profile:lms:course-9",
        version=1,
        course_ref=course_ref,
        source_type=CourseSourceType.INTERNAL,
        source_system="frappe_lms",
        title_snapshot="Internal course",
        capabilities=[
            CourseCapability(
                capability_ref=CAPABILITY_REF,
                coverage_type=CoverageType.DIRECT,
                provenance=[
                    CourseProvenance(kind="existing", source_ref=course_ref, method="fixture")
                ],
            )
        ],
        status=CourseProfileStatus.DRAFT,
        provenance=[CourseProvenance(kind="source", source_ref=course_ref, method="fixture")],
    )
    claim = DirectCourseCapabilityClaim(
        course_ref=course_ref, claim_id=claim_id, source_ref=source, evidence=evidence
    )

    result = project_governed_course_capabilities(
        profile,
        direct_claims=(GovernedDirectClaimMappingInput(claim=claim, mapping=mapping),),
        active_release_context=(release,),
    )

    assert result.coverage[0].sources[0].source_ref == source


def test_mapping_from_another_course_fails_closed() -> None:
    outcome_input, release = _outcome_input()
    other_outcome = outcome_input.outcome.model_copy(
        update={"course_ref": "skillscommons:other-course"}
    )
    mismatched = outcome_input.model_copy(update={"outcome": other_outcome})

    with pytest.raises(CourseProjectionError, match="course_source_mismatch"):
        project_governed_course_capabilities(
            _profile(), outcomes=(mismatched,), active_release_context=(release,)
        )


def test_stale_mapping_source_is_not_projected() -> None:
    outcome_input, release = _outcome_input()
    changed_evidence = (
        _evidence(outcome_input.outcome.outcome_ref, "outcome:1", "Changed source text."),
    )
    stale = outcome_input.model_copy(update={"evidence": changed_evidence})

    with pytest.raises(MappingGovernanceError, match="stale_source"):
        project_governed_course_capabilities(
            _profile(), outcomes=(stale,), active_release_context=(release,)
        )


def test_unmapped_semantic_does_not_fabricate_coverage() -> None:
    source = _source(SourceSemanticKind.COURSE_LEARNING_OUTCOME, "course-123#outcome-2")
    outcome = CourseLearningOutcome(
        outcome_ref=source,
        course_ref=COURSE_REF,
        statement="Explain stakeholder communication.",
        source_locator="course:course-123:outcome:2",
    )
    evidence = (_evidence(source, outcome.source_locator, outcome.statement),)

    result = project_governed_course_capabilities(
        _profile(),
        outcomes=(GovernedOutcomeMappingInput(outcome=outcome, evidence=evidence, mapping=None),),
        active_release_context=(),
    )

    assert result.coverage == ()
    assert result.warnings[0].source_ref == source
    assert result.profile_candidate is None


def test_legacy_draft_profile_is_not_rewritten_to_a_new_canonical_ref() -> None:
    outcome_input, release = _outcome_input()
    legacy_profile = _profile(capability_ref="project_management")

    result = project_governed_course_capabilities(
        legacy_profile, outcomes=(outcome_input,), active_release_context=(release,)
    )

    assert result.coverage[0].capability_ref.root == CAPABILITY_REF
    assert result.profile_candidate is None
    assert legacy_profile.capabilities[0].capability_ref == "project_management"


def test_duplicate_canonical_coverage_retains_all_source_traces_once() -> None:
    first, release = _outcome_input()
    second_source = _source(SourceSemanticKind.COURSE_LEARNING_OUTCOME, "course-123#outcome-2")
    second_outcome = CourseLearningOutcome(
        outcome_ref=second_source,
        course_ref=COURSE_REF,
        statement="Coordinate project activities.",
        source_locator="course:course-123:outcome:2",
    )
    second_evidence = (
        _evidence(second_source, second_outcome.source_locator, second_outcome.statement),
    )
    second_mapping, _ = _mapping(
        second_source, second_evidence, MappingScope.OUTCOME_CAPABILITY_FACET
    )
    second = GovernedOutcomeMappingInput(
        outcome=second_outcome, evidence=second_evidence, mapping=second_mapping
    )

    result = project_governed_course_capabilities(
        _profile(), outcomes=(second, first), active_release_context=(release,)
    )

    assert len(result.coverage) == 1
    assert len(result.coverage[0].sources) == 2
    assert len(result.profile_candidate.capabilities) == 1
    assert len(result.profile_candidate.capabilities[0].provenance) == 2


def test_active_profile_is_not_rewritten_and_candidate_uses_existing_profile() -> None:
    outcome_input, release = _outcome_input()
    active_profile = _profile(CourseProfileStatus.ACTIVE).model_copy(
        update={
            "capabilities": [
                CourseCapability(
                    capability_ref=CAPABILITY_REF,
                    coverage_type=CoverageType.DIRECT,
                    provenance=[
                        CourseProvenance(
                            kind="existing_reviewed_profile",
                            source_ref=COURSE_REF,
                            method="fixture",
                        )
                    ],
                )
            ]
        }
    )

    result = project_governed_course_capabilities(
        active_profile, outcomes=(outcome_input,), active_release_context=(release,)
    )

    assert result.profile_candidate is None
    assert result.normalized_candidate is not None
    assert (
        result.normalized_candidate.capabilities[0].provenance[0].kind
        == "existing_reviewed_profile"
    )


def test_active_profile_with_unmapped_legacy_ref_fails_closed() -> None:
    outcome_input, release = _outcome_input()
    with pytest.raises(CourseProjectionError, match="active_profile_projection_mismatch"):
        project_governed_course_capabilities(
            _profile(CourseProfileStatus.ACTIVE, capability_ref="project_management"),
            outcomes=(outcome_input,),
            active_release_context=(release,),
        )


def test_direct_claim_from_another_course_is_rejected_during_projection() -> None:
    foreign_course_ref = "skillscommons:another-course"
    claim_id = "claim-1"
    source = _source(
        SourceSemanticKind.COURSE_DIRECT_CLAIM,
        make_direct_claim_source_id(course_ref=foreign_course_ref, claim_id=claim_id),
    )
    evidence = (_evidence(source, "claim:1", "Direct course capability evidence."),)
    mapping, release = _mapping(source, evidence, MappingScope.DIRECT_CAPABILITY_CLAIM)
    claim = DirectCourseCapabilityClaim(
        course_ref=foreign_course_ref, claim_id=claim_id, source_ref=source, evidence=evidence
    )

    with pytest.raises(CourseProjectionError, match="course_source_mismatch"):
        project_governed_course_capabilities(
            _profile(),
            direct_claims=(GovernedDirectClaimMappingInput(claim=claim, mapping=mapping),),
            active_release_context=(release,),
        )


def test_legacy_delimited_direct_claim_identity_is_rejected() -> None:
    source = _source(SourceSemanticKind.COURSE_DIRECT_CLAIM, "course-123#claim-1")
    evidence = (_evidence(source, "claim:1", "Direct course capability evidence."),)

    with pytest.raises(ValueError, match="direct_claim_source_id_mismatch"):
        DirectCourseCapabilityClaim(
            course_ref=COURSE_REF, claim_id="claim-1", source_ref=source, evidence=evidence
        )


def test_direct_claim_rejects_source_namespace_mismatch() -> None:
    claim_id = "claim-1"
    source = _source(
        SourceSemanticKind.COURSE_DIRECT_CLAIM,
        make_direct_claim_source_id(course_ref=COURSE_REF, claim_id=claim_id),
        namespace="another_provider",
    )
    evidence = (_evidence(source, "claim:1", "Direct course capability evidence."),)

    with pytest.raises(ValueError, match="course_source_mismatch"):
        DirectCourseCapabilityClaim(
            course_ref=COURSE_REF, claim_id=claim_id, source_ref=source, evidence=evidence
        )


def test_direct_claim_rejects_wrong_source_kind() -> None:
    claim_id = "claim-1"
    source = _source(
        SourceSemanticKind.COURSE_LEARNING_OUTCOME,
        make_direct_claim_source_id(course_ref=COURSE_REF, claim_id=claim_id),
    )
    evidence = (_evidence(source, "claim:1", "Direct course capability evidence."),)

    with pytest.raises(ValueError, match="course_direct_claim_ref_required"):
        DirectCourseCapabilityClaim(
            course_ref=COURSE_REF, claim_id=claim_id, source_ref=source, evidence=evidence
        )


def test_changed_direct_claim_identity_changes_source_pin_and_rejects_old_mapping() -> None:
    original_input, _ = _direct_input()
    changed_claim_id = "claim-2"
    changed_source = _source(
        SourceSemanticKind.COURSE_DIRECT_CLAIM,
        make_direct_claim_source_id(course_ref=COURSE_REF, claim_id=changed_claim_id),
    )
    changed_evidence = (
        _evidence(
            changed_source, "course:course-123:claim:1", "Directly teaches project planning."
        ),
    )
    changed_claim = DirectCourseCapabilityClaim(
        course_ref=COURSE_REF,
        claim_id=changed_claim_id,
        source_ref=changed_source,
        evidence=changed_evidence,
    )

    assert build_source_semantic_pin(
        original_input.claim.source_ref, original_input.claim.evidence
    ) != build_source_semantic_pin(changed_source, changed_evidence)
    with pytest.raises(ValueError, match="course_source_mismatch"):
        GovernedDirectClaimMappingInput(claim=changed_claim, mapping=original_input.mapping)


def test_deprecated_mapping_cannot_feed_current_course_projection() -> None:
    outcome_input, release = _outcome_input()
    deprecated = deprecate_governed_mapping(
        outcome_input.mapping, actor_ref="actor:governance", reason="Superseded source mapping."
    )
    deprecated_input = outcome_input.model_copy(update={"mapping": deprecated})

    with pytest.raises(MappingGovernanceError, match="mapping_deprecated"):
        project_governed_course_capabilities(
            _profile(), outcomes=(deprecated_input,), active_release_context=(release,)
        )
