from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from app.capability_analysis.schemas import (
    AnalysisStatus,
    AssessmentEvidenceStatus,
    CapabilityGapProfile,
    CapabilityGapProfileEntry,
    CapabilityGapProfileTrack,
    PreliminaryPriority,
    TargetType,
    TargetUsageMode,
)
from app.capability_governance.definitions import (
    CapabilityDefinition,
    CapabilityDefinitionStatus,
    deprecate_capability_definition,
)
from app.capability_governance.errors import CapabilityNotActiveError
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
    SourceSemanticPin,
    build_source_semantic_pin,
    fingerprint_mapping_review,
)
from app.capability_governance.mapping_errors import MappingGovernanceError
from app.capability_governance.packs import (
    CapabilityGovernanceDecision,
    CapabilityGovernanceReview,
    CapabilityReleaseApproval,
    activate_capability_pack_release,
    build_capability_pack_release,
)
from app.capability_governance.target_adapter import (
    RequiredTargetFacet,
    TargetAdapterError,
    project_governed_recommendation_target,
)
from app.learning_need_profile.schemas import (
    LearnerContext,
    LearningNeedCompetency,
    LearningNeedCurrentState,
    LearningNeedEligibility,
    LearningNeedGap,
    LearningNeedProfile,
    LearningNeedProvenance,
    LearningNeedResolution,
    LearningNeedTargetState,
)
from app.matching.schemas import (
    CriterionDimension,
    RequirementClassification,
    RoleCompetencyProfile,
    RoleProfileStatus,
    RoleRequirement,
)


def source_ref(
    kind: SourceSemanticKind = SourceSemanticKind.ROLE_REQUIREMENT,
    *,
    namespace: str = "role_profile",
    source_id: str = "req-1",
    version: str | None = "role-v1",
) -> SourceSemanticRef:
    return SourceSemanticRef(
        source_namespace=namespace,
        entity_kind=kind,
        source_id=source_id,
        source_version=version,
    )


def pin(ref: SourceSemanticRef | None = None) -> SourceSemanticPin:
    return SourceSemanticPin(
        source_ref=ref or source_ref(),
        evidence_fingerprint="sha256:" + "a" * 64,
    )


def _active_release(version: str = "1.0"):
    draft = build_capability_pack_release(
        pack_id="test_core_pack",
        namespace_key="test_core",
        version=version,
        owner_ref="team:governance",
        definitions=(
            CapabilityDefinition(
                canonical_ref="capability:test_core:communication",
                label="Communication",
                definition="Communicate clearly in work contexts.",
                status=CapabilityDefinitionStatus.DRAFT,
            ),
            CapabilityDefinition(
                canonical_ref="capability:test_core:writing",
                label="Writing",
                definition="Write clear professional content.",
                status=CapabilityDefinitionStatus.DRAFT,
            ),
        ),
    )
    return activate_capability_pack_release(
        draft,
        review=CapabilityGovernanceReview(
            review_ref=f"review:test-core:{version}",
            reviewer_ref="actor:pack-reviewer",
            decision=CapabilityGovernanceDecision.APPROVE,
            collision_review_ref=f"collision:test-core:{version}",
        ),
        approval=CapabilityReleaseApproval(
            approval_ref=f"approval:test-core:{version}",
            approver_ref="actor:pack-approver",
            decision=CapabilityGovernanceDecision.APPROVE,
        ),
    )


def _mapped(
    source: SourceSemanticRef,
    release,
    target: str,
    scope: MappingScope,
    evidence_text: str | None = None,
):
    evidence = (
        SemanticEvidence(
            source_ref=source,
            source_locator=f"source:{source.source_id}",
            evidence_text=evidence_text or f"Evidence for {source.source_id}.",
            evidence_kind=SemanticEvidenceKind.SOURCE_TEXT,
        ),
    )
    proposal = CapabilityMappingProposal(
        proposal_id=f"proposal:{source.source_id}:{scope.value}:{target.rsplit(':', 1)[-1]}",
        source_ref=source,
        target_capability_ref=target,
        mapping_type=MappingType.EXACT,
        mapping_scope=scope,
        evidence=evidence,
        proposal_method=ProposalMethod.MANUAL,
        proposer_ref="actor:proposer",
    )
    review = CapabilityMappingReview(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
        reviewer_ref="actor:reviewer",
        decision=MappingDecision.APPROVE,
        rationale="Reviewed exact source mapping.",
    )
    from app.capability_governance.packs import CapabilityPackReleaseRef
    from app.capability_governance.resolution import CapabilityDefinitionPin

    definition = next(item for item in release.definitions if str(item.canonical_ref) == target)
    definition_pin = CapabilityDefinitionPin(
        capability_ref=definition.canonical_ref,
        pack_release_ref=CapabilityPackReleaseRef(
            pack_id=release.pack_id,
            version=release.version,
            checksum=release.content_checksum,
        ),
    )
    source_pin = build_source_semantic_pin(source, evidence)
    approval = MappingActivationApproval(
        approval_ref=f"approval:{proposal.proposal_id}",
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
        review_fingerprint=fingerprint_mapping_review(review),
        source_pin=source_pin,
        target_definition_pin=definition_pin,
        approver_ref="actor:approver",
    )
    mapping = activate_governed_mapping(
        mapping_id=f"mapping:{proposal.proposal_id}",
        proposal=proposal,
        review=review,
        current_source_pin=source_pin,
        activation_approval=approval,
        active_release_context=(release,),
    )
    return mapping, source_pin


def _inputs():
    requirement = RoleRequirement(
        id="req-1",
        criterion_dimension=CriterionDimension.SKILL,
        classification=RequirementClassification.TRAINABLE_MANDATORY,
        evidence_terms=["communication"],
        confidence_threshold=0.8,
        assessment_recommendation="Practice communication.",
        rubric_version="rubric-v1",
        priority="high",
        target_level="L3",
        observable_behaviors=["Explain decisions clearly"],
        evidence_constraints=["Use a work example"],
    )
    role = RoleCompetencyProfile(
        id="role-1",
        version="2",
        status=RoleProfileStatus.ACTIVE,
        source_jd_profile_id="jd-1",
        source_jd_profile_version=1,
        rule_set_version="rules-v1",
        policy_version="policy-v1",
        requirements=[requirement],
    )
    gap_profile = CapabilityGapProfile(
        id="analysis-1",
        cv_profile_id="cv-1",
        cv_profile_version=4,
        current_target_version="2",
        owner_actor_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        organization_id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        correlation_id="correlation-1",
        analysis_status=AnalysisStatus.READY,
        analysis_version=3,
        current_role=CapabilityGapProfileTrack(
            target_id="role-1",
            target_type=TargetType.CURRENT_ROLE,
            usage_mode=TargetUsageMode.OFFICIAL,
            entries=[
                CapabilityGapProfileEntry(
                    requirement_id="req-1",
                    matched_evidence_refs=["evidence:1"],
                    missing_signals=["clear explanations"],
                    rationale="Evidence remains incomplete.",
                    preliminary_priority=PreliminaryPriority.HIGH,
                    missing_priority_inputs=[],
                    evidence_status=AssessmentEvidenceStatus.INSUFFICIENT,
                    gap_id="gap-1",
                )
            ],
            warning_codes=["source_warning"],
        ),
    )
    need = LearningNeedProfile(
        id="need-record-1",
        candidate_reference=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        target_reference="role-1@2",
        learner_context=LearnerContext(role=None, experience_level=None),
        competency=LearningNeedCompetency(id="req-1", name=None, description=None),
        current_state=LearningNeedCurrentState(level="L1", evidence_refs=["evidence:1"]),
        target_state=LearningNeedTargetState(
            level="L3", expected_behaviors=["Explain decisions clearly"]
        ),
        gap=LearningNeedGap(type="skill_gap", description="Improve communication."),
        missing_knowledge=["clear explanations"],
        learning_constraints={"hours_per_week": 2},
        priority=PreliminaryPriority.HIGH,
        source_gap_refs=["gap-1"],
        provenance=LearningNeedProvenance(
            analysis_id="analysis-1",
            analysis_version=3,
            target_id="role-1",
            target_version="2",
            source_profile_id="cv-1",
            source_profile_version=4,
            evidence_refs=["evidence:1"],
            transformation="learning-need-profile-v1",
        ),
        requirement_reference="req-1",
        learning_eligibility=LearningNeedEligibility.READY_FOR_LEARNING,
        resolution_type=LearningNeedResolution.LEARNING,
        usage_mode="official",
        warning_codes=["need_warning"],
    )
    role_ref = source_ref(version=role.version)
    need_ref = source_ref(
        SourceSemanticKind.LEARNING_NEED_COMPETENCY,
        namespace="learning_need",
        source_id="req-1",
        version=None,
    )
    role_evidence = (
        SemanticEvidence(
            source_ref=role_ref,
            source_locator="source:req-1",
            evidence_text="Explain decisions clearly.",
            evidence_kind=SemanticEvidenceKind.SOURCE_TEXT,
        ),
    )
    need_evidence = (
        SemanticEvidence(
            source_ref=need_ref,
            source_locator="source:req-1",
            evidence_text="Improve communication.",
            evidence_kind=SemanticEvidenceKind.SOURCE_TEXT,
        ),
    )
    role_pin = build_source_semantic_pin(role_ref, role_evidence)
    need_pin = build_source_semantic_pin(need_ref, need_evidence)
    return role, gap_profile, need, role_pin, need_pin


def _project(role, gap_profile, need, facets, mappings=(), releases=()):
    return project_governed_recommendation_target(
        role_profile=role,
        gap_profile=gap_profile,
        learning_need=need,
        required_facets=tuple(facets),
        governed_mappings=tuple(mappings),
        active_release_context=tuple(releases),
        source_learning_path_ref="path:1",
        source_path_step_ref="step:2",
    )


def test_required_facet_requires_explicit_bounded_identity_and_is_frozen() -> None:
    facet = RequiredTargetFacet(facet_id="role:communication", source_pin=pin())

    assert facet.facet_id == "role:communication"
    with pytest.raises(ValidationError):
        facet.facet_id = "other"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        RequiredTargetFacet(facet_id="   ", source_pin=pin())
    with pytest.raises(ValidationError):
        RequiredTargetFacet(facet_id="x" * 257, source_pin=pin())


@pytest.mark.parametrize(
    ("ref",),
    [
        (
            source_ref(
                SourceSemanticKind.COURSE_LEARNING_OUTCOME,
                namespace="skillscommons",
                source_id="course:outcome",
            ),
        ),
        (
            source_ref(
                SourceSemanticKind.ROLE_REQUIREMENT, namespace="learning_need", source_id="req-1"
            ),
        ),
    ],
)
def test_required_facet_rejects_source_kinds_or_namespaces_outside_role_need_contract(
    ref: SourceSemanticRef,
) -> None:
    with pytest.raises(ValidationError):
        RequiredTargetFacet(facet_id="facet:1", source_pin=pin(ref))


def test_target_adapter_error_has_stable_code() -> None:
    error = TargetAdapterError("TARGET_LINEAGE_MISMATCH", "lineage mismatch")

    assert error.code == "TARGET_LINEAGE_MISMATCH"
    assert str(error) == "lineage mismatch"


def test_target_ref_and_learning_need_trace_preserve_distinct_identities() -> None:
    role, gaps, need, role_pin, _ = _inputs()
    release = _active_release()
    mapping, _ = _mapped(
        role_pin.source_ref,
        release,
        "capability:test_core:communication",
        MappingScope.CAPABILITY_FACET,
        "Explain decisions clearly.",
    )

    result = _project(
        role,
        gaps,
        need,
        [RequiredTargetFacet(facet_id="required:communication", source_pin=role_pin)],
        mappings=[mapping],
        releases=[release],
    )

    assert result.recommendation_target.target_ref == "role-1@2"
    assert result.recommendation_target.source_learning_need_ref == "need-record-1"
    assert (
        result.recommendation_target.target_ref
        != result.recommendation_target.source_learning_need_ref
    )
    assert result.recommendation_target.target_capability_refs == [
        "capability:test_core:communication"
    ]
    assert result.recommendation_target.target_level == "L3"
    assert result.recommendation_target.source_path_step_ref == "step:2"
    assert result.role_requirement.observable_behaviors == ["Explain decisions clearly"]
    assert result.learning_need.learning_constraints == {"hours_per_week": 2}
    assert result.warning_codes == ("need_warning", "source_warning")
    assert [entry.gap_id for entry in result.gap_entries] == ["gap-1"]
    assert result.mapping_provenance[0].mapping_fingerprint == mapping.mapping_fingerprint
    assert result.bindings[0].resolution_mode.value == "current"


def test_unrelated_mapping_context_is_ignored_deterministically() -> None:
    role, gaps, need, role_pin, _ = _inputs()
    release = _active_release()
    evidence = SemanticEvidence(
        source_ref=role_pin.source_ref,
        source_locator="source:req-1",
        evidence_text="Explain decisions clearly.",
        evidence_kind=SemanticEvidenceKind.SOURCE_TEXT,
    )
    relevant, _ = _mapped(
        role_pin.source_ref,
        release,
        "capability:test_core:communication",
        MappingScope.CAPABILITY_FACET,
        evidence.evidence_text,
    )
    other_ref = source_ref(source_id="other-requirement")
    other, _ = _mapped(
        other_ref,
        release,
        "capability:test_core:writing",
        MappingScope.CAPABILITY_FACET,
        "Unrelated semantic.",
    )

    result = _project(
        role,
        gaps,
        need,
        [RequiredTargetFacet(facet_id="required:communication", source_pin=role_pin)],
        mappings=[other, relevant],
        releases=[release],
    )

    assert result.recommendation_target.target_capability_refs == [
        "capability:test_core:communication"
    ]
    assert [item.mapping_id for item in result.bindings] == [relevant.mapping_id]


def test_stale_mapping_for_required_source_fails_closed() -> None:
    role, gaps, need, role_pin, _ = _inputs()
    release = _active_release()
    stale_evidence = SemanticEvidence(
        source_ref=role_pin.source_ref,
        source_locator="source:req-1",
        evidence_text="Old wording for the requirement.",
        evidence_kind=SemanticEvidenceKind.SOURCE_TEXT,
    )
    mapping, _ = _mapped(
        role_pin.source_ref,
        release,
        "capability:test_core:communication",
        MappingScope.CAPABILITY_FACET,
        stale_evidence.evidence_text,
    )

    with pytest.raises(MappingGovernanceError) as error:
        _project(
            role,
            gaps,
            need,
            [RequiredTargetFacet(facet_id="required:communication", source_pin=role_pin)],
            mappings=[mapping],
            releases=[release],
        )
    assert error.value.code == "stale_source"


def test_stale_same_source_candidate_is_not_hidden_by_an_exact_pin_candidate() -> None:
    role, gaps, need, role_pin, _ = _inputs()
    release = _active_release()
    current_mapping, _ = _mapped(
        role_pin.source_ref,
        release,
        "capability:test_core:communication",
        MappingScope.CAPABILITY_FACET,
        "Explain decisions clearly.",
    )
    stale_mapping, _ = _mapped(
        role_pin.source_ref,
        release,
        "capability:test_core:communication",
        MappingScope.CAPABILITY_FACET,
        "Superseded requirement wording.",
    )

    with pytest.raises(MappingGovernanceError) as error:
        _project(
            role,
            gaps,
            need,
            [RequiredTargetFacet(facet_id="required:communication", source_pin=role_pin)],
            mappings=[current_mapping, stale_mapping],
            releases=[release],
        )
    assert error.value.code == "stale_source"


def test_non_learning_need_is_rejected_under_existing_policy() -> None:
    role, gaps, need, role_pin, _ = _inputs()
    ineligible = need.model_copy(update={"resolution_type": LearningNeedResolution.VERIFICATION})

    with pytest.raises(TargetAdapterError) as error:
        _project(
            role,
            gaps,
            ineligible,
            [RequiredTargetFacet(facet_id="required:communication", source_pin=role_pin)],
        )
    assert error.value.code == "TARGET_NEED_NOT_LEARNING_ELIGIBLE"


def test_missing_need_requirement_reference_fails_exact_lineage_validation() -> None:
    role, gaps, need, role_pin, _ = _inputs()
    missing = need.model_copy(update={"requirement_reference": None})

    with pytest.raises(TargetAdapterError) as error:
        _project(
            role,
            gaps,
            missing,
            [RequiredTargetFacet(facet_id="required:communication", source_pin=role_pin)],
        )
    assert error.value.code == "TARGET_LINEAGE_MISMATCH"


def test_shared_facet_id_requires_role_and_need_mappings_to_agree() -> None:
    role, gaps, need, role_pin, need_pin = _inputs()
    release = _active_release()
    role_evidence = SemanticEvidence(
        source_ref=role_pin.source_ref,
        source_locator="source:req-1",
        evidence_text="Explain decisions clearly.",
        evidence_kind=SemanticEvidenceKind.SOURCE_TEXT,
    )
    need_evidence = SemanticEvidence(
        source_ref=need_pin.source_ref,
        source_locator="need:competency:req-1",
        evidence_text="Improve communication.",
        evidence_kind=SemanticEvidenceKind.SOURCE_TEXT,
    )
    role_mapping, _ = _mapped(
        role_pin.source_ref,
        release,
        "capability:test_core:communication",
        MappingScope.CAPABILITY_FACET,
        role_evidence.evidence_text,
    )
    need_mapping, _ = _mapped(
        need_pin.source_ref,
        release,
        "capability:test_core:writing",
        MappingScope.DIRECT_CAPABILITY_CLAIM,
        need_evidence.evidence_text,
    )

    with pytest.raises(TargetAdapterError) as error:
        _project(
            role,
            gaps,
            need,
            [
                RequiredTargetFacet(facet_id="same-declared-target", source_pin=role_pin),
                RequiredTargetFacet(facet_id="same-declared-target", source_pin=need_pin),
            ],
            mappings=[role_mapping, need_mapping],
            releases=[release],
        )
    assert error.value.code == "TARGET_CANONICAL_BINDING_CONFLICT"


def test_role_and_need_facets_with_distinct_ids_resolve_independently_and_deduplicate_exact_pin() -> (
    None
):
    role, gaps, need, role_pin, need_pin = _inputs()
    release = _active_release()
    role_mapping, _ = _mapped(
        role_pin.source_ref,
        release,
        "capability:test_core:communication",
        MappingScope.CAPABILITY_FACET,
        "Explain decisions clearly.",
    )
    need_mapping, _ = _mapped(
        need_pin.source_ref,
        release,
        "capability:test_core:communication",
        MappingScope.DIRECT_CAPABILITY_CLAIM,
        "Improve communication.",
    )

    result = _project(
        role,
        gaps,
        need,
        [
            RequiredTargetFacet(facet_id="role-facet", source_pin=role_pin),
            RequiredTargetFacet(facet_id="need-facet", source_pin=need_pin),
        ],
        mappings=[role_mapping, need_mapping],
        releases=[release],
    )

    assert result.recommendation_target.target_capability_refs == [
        "capability:test_core:communication"
    ]
    assert len(result.mapping_provenance) == 2
    assert len(result.definition_pins) == 1


def test_missing_required_mapping_fails_without_dropping_facet() -> None:
    role, gaps, need, role_pin, _ = _inputs()

    with pytest.raises(TargetAdapterError) as error:
        _project(
            role,
            gaps,
            need,
            [RequiredTargetFacet(facet_id="required:communication", source_pin=role_pin)],
        )
    assert error.value.code == "TARGET_CAPABILITY_UNRESOLVED"


def test_role_facet_source_identity_must_match_exact_requirement_and_profile_version() -> None:
    role, gaps, need, _, _ = _inputs()
    wrong_ref = source_ref(source_id="another-requirement", version=role.version)
    wrong_pin = pin(wrong_ref)

    with pytest.raises(TargetAdapterError) as error:
        _project(
            role,
            gaps,
            need,
            [RequiredTargetFacet(facet_id="required:communication", source_pin=wrong_pin)],
        )
    assert error.value.code == "TARGET_FACET_INVALID"


def test_target_capabilities_are_sorted_and_explicit_unavailable_level_stays_none() -> None:
    role, gaps, need, role_pin, need_pin = _inputs()
    no_level_requirement = role.requirements[0].model_copy(update={"target_level": None})
    no_level_role = role.model_copy(update={"requirements": [no_level_requirement]})
    no_level_need = need.model_copy(
        update={"target_state": need.target_state.model_copy(update={"level": None})}
    )
    release = _active_release()
    role_mapping, _ = _mapped(
        role_pin.source_ref,
        release,
        "capability:test_core:writing",
        MappingScope.CAPABILITY_FACET,
        "Explain decisions clearly.",
    )
    need_mapping, _ = _mapped(
        need_pin.source_ref,
        release,
        "capability:test_core:communication",
        MappingScope.DIRECT_CAPABILITY_CLAIM,
        "Improve communication.",
    )

    result = _project(
        no_level_role,
        gaps,
        no_level_need,
        [
            RequiredTargetFacet(facet_id="writing", source_pin=role_pin),
            RequiredTargetFacet(facet_id="communication", source_pin=need_pin),
        ],
        mappings=[role_mapping, need_mapping],
        releases=[release],
    )

    assert result.recommendation_target.target_capability_refs == [
        "capability:test_core:communication",
        "capability:test_core:writing",
    ]
    assert result.recommendation_target.target_level is None


def test_conflicting_explicit_role_and_need_target_levels_fail() -> None:
    role, gaps, need, role_pin, _ = _inputs()
    changed_need = need.model_copy(
        update={"target_state": need.target_state.model_copy(update={"level": "L4"})}
    )
    release = _active_release()
    mapping, _ = _mapped(
        role_pin.source_ref,
        release,
        "capability:test_core:communication",
        MappingScope.CAPABILITY_FACET,
        "Explain decisions clearly.",
    )

    with pytest.raises(TargetAdapterError) as error:
        _project(
            role,
            gaps,
            changed_need,
            [RequiredTargetFacet(facet_id="required:communication", source_pin=role_pin)],
            mappings=[mapping],
            releases=[release],
        )
    assert error.value.code == "TARGET_LEVEL_CONFLICT"


def test_deprecated_mapping_is_not_usable_for_current_target() -> None:
    role, gaps, need, role_pin, _ = _inputs()
    release = _active_release()
    mapping, _ = _mapped(
        role_pin.source_ref,
        release,
        "capability:test_core:communication",
        MappingScope.CAPABILITY_FACET,
        "Explain decisions clearly.",
    )
    deprecated = deprecate_governed_mapping(
        mapping, actor_ref="actor:deprecator", reason="No longer current."
    )

    with pytest.raises(MappingGovernanceError) as error:
        _project(
            role,
            gaps,
            need,
            [RequiredTargetFacet(facet_id="required:communication", source_pin=role_pin)],
            mappings=[deprecated],
            releases=[release],
        )
    assert error.value.code == "mapping_deprecated"


def test_mapping_is_not_re_pinned_to_a_different_active_release() -> None:
    role, gaps, need, role_pin, _ = _inputs()
    pinned_release = _active_release("1.0")
    newer_release = _active_release("2.0")
    mapping, _ = _mapped(
        role_pin.source_ref,
        pinned_release,
        "capability:test_core:communication",
        MappingScope.CAPABILITY_FACET,
        "Explain decisions clearly.",
    )

    with pytest.raises(MappingGovernanceError) as error:
        _project(
            role,
            gaps,
            need,
            [RequiredTargetFacet(facet_id="required:communication", source_pin=role_pin)],
            mappings=[mapping],
            releases=[newer_release],
        )
    assert error.value.code == "target_pin_mismatch"


def test_inactive_canonical_definition_is_rejected_by_current_use_resolver() -> None:
    role, gaps, need, role_pin, _ = _inputs()
    release = _active_release()
    mapping, _ = _mapped(
        role_pin.source_ref,
        release,
        "capability:test_core:communication",
        MappingScope.CAPABILITY_FACET,
        "Explain decisions clearly.",
    )
    inactive_definition = deprecate_capability_definition(
        release.definitions[0], actor_ref="actor:deprecator", reason="Retired."
    )
    inactive_release = release.model_copy(
        update={"definitions": (inactive_definition, *release.definitions[1:])}
    )

    with pytest.raises(CapabilityNotActiveError):
        _project(
            role,
            gaps,
            need,
            [RequiredTargetFacet(facet_id="required:communication", source_pin=role_pin)],
            mappings=[mapping],
            releases=[inactive_release],
        )


def test_projection_does_not_mutate_role_need_or_gap_inputs() -> None:
    role, gaps, need, role_pin, _ = _inputs()
    role_before = role.model_dump(mode="json")
    need_before = need.model_dump(mode="json")
    gaps_before = gaps.model_dump(mode="json")
    release = _active_release()
    mapping, _ = _mapped(
        role_pin.source_ref,
        release,
        "capability:test_core:communication",
        MappingScope.CAPABILITY_FACET,
        "Explain decisions clearly.",
    )

    result = _project(
        role,
        gaps,
        need,
        [RequiredTargetFacet(facet_id="required:communication", source_pin=role_pin)],
        mappings=[mapping],
        releases=[release],
    )

    assert result.recommendation_target.source_role_requirement_refs == ["req-1"]
    assert result.recommendation_target.source_gap_refs == ["gap-1"]
    assert role.model_dump(mode="json") == role_before
    assert need.model_dump(mode="json") == need_before
    assert gaps.model_dump(mode="json") == gaps_before
