import pytest
from pydantic import ValidationError

from app.capability_governance.definitions import CapabilityDefinition, CapabilityDefinitionStatus
from app.capability_governance.errors import (
    PackNotActiveError,
    UnknownCapabilityError,
    UnknownNamespaceError,
)
from app.capability_governance.evidence import SemanticEvidence, SemanticEvidenceKind
from app.capability_governance.governed_mapping import (
    GovernedCapabilityMapping,
    GovernedMappingStatus,
    MappingDeprecationRecord,
    activate_governed_mapping,
    deprecate_governed_mapping,
)
from app.capability_governance.identity import (
    CanonicalCapabilityRef,
    SourceSemanticKind,
    SourceSemanticRef,
)
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
from app.capability_governance.mapping_resolution import (
    BindingResolutionMode,
    resolve_governed_mapping_for_use,
    resolve_governed_mapping_historical,
)
from app.capability_governance.packs import (
    CapabilityGovernanceDecision,
    CapabilityGovernanceReview,
    CapabilityPackId,
    CapabilityPackRelease,
    CapabilityPackReleaseRef,
    CapabilityReleaseApproval,
    activate_capability_pack_release,
    build_capability_pack_release,
    deprecate_capability_pack_release,
)
from app.capability_governance.resolution import CapabilityDefinitionPin


def source_ref(version: str | None = "catalog-v1") -> SourceSemanticRef:
    return SourceSemanticRef(
        source_namespace="test_catalog",
        entity_kind=SourceSemanticKind.COURSE_LEARNING_OUTCOME,
        source_id="course-7#outcome-1",
        source_version=version,
    )


def evidence(
    *,
    source: SourceSemanticRef | None = None,
    locator: str = "course-7:outcome-1",
    text: str = "Explain deterministic source pinning.",
) -> SemanticEvidence:
    return SemanticEvidence(
        source_ref=source or source_ref(),
        source_locator=locator,
        evidence_text=text,
        evidence_kind=SemanticEvidenceKind.EXPLICIT_OUTCOME,
    )


def review(
    *,
    reviewer: str = "actor:reviewer-1",
    decision: MappingDecision = MappingDecision.APPROVE,
    rationale: str = "Reviewed the exact semantic proposal.",
    proposal_fingerprint: str = "sha256:" + "a" * 64,
) -> CapabilityMappingReview:
    return CapabilityMappingReview(
        proposal_id="proposal:course-7:outcome-1",
        proposal_fingerprint=proposal_fingerprint,
        reviewer_ref=reviewer,
        decision=decision,
        rationale=rationale,
    )


def target_pin() -> CapabilityDefinitionPin:
    ref = CanonicalCapabilityRef.parse("capability:test_core:project_management")
    return CapabilityDefinitionPin(
        capability_ref=ref,
        pack_release_ref=CapabilityPackReleaseRef(
            pack_id=CapabilityPackId("test_core_pack"),
            version="1.0",
            checksum="sha256:" + "b" * 64,
        ),
    )


def active_release(version: str = "1.0", *, include_second: bool = False) -> CapabilityPackRelease:
    definitions = [
        CapabilityDefinition(
            canonical_ref=CanonicalCapabilityRef.parse("capability:test_core:project_management"),
            label="Project Management",
            definition="Plan and coordinate project delivery.",
            status=CapabilityDefinitionStatus.DRAFT,
        )
    ]
    if include_second:
        definitions.append(
            CapabilityDefinition(
                canonical_ref=CanonicalCapabilityRef.parse("capability:test_core:delivery"),
                label="Delivery",
                definition="Deliver agreed work outcomes.",
                status=CapabilityDefinitionStatus.DRAFT,
            )
        )
    draft = build_capability_pack_release(
        pack_id="test_core_pack",
        namespace_key="test_core",
        version=version,
        owner_ref="team:capability-governance",
        definitions=tuple(definitions),
    )
    return activate_capability_pack_release(
        draft,
        review=CapabilityGovernanceReview(
            review_ref=f"review:{version}",
            reviewer_ref="actor:pack-reviewer",
            decision=CapabilityGovernanceDecision.APPROVE,
            collision_review_ref=f"collision:{version}",
        ),
        approval=CapabilityReleaseApproval(
            approval_ref=f"pack-approval:{version}",
            approver_ref="actor:pack-approver",
            decision=CapabilityGovernanceDecision.APPROVE,
        ),
    )


def proposal(
    *,
    target: str = "capability:test_core:project_management",
    method: ProposalMethod = ProposalMethod.MANUAL,
    source: SourceSemanticRef | None = None,
    statement: str = "Explain deterministic source pinning.",
) -> CapabilityMappingProposal:
    source = source or source_ref()
    return CapabilityMappingProposal(
        proposal_id="proposal:course-7:outcome-1",
        source_ref=source,
        target_capability_ref=CanonicalCapabilityRef.parse(target),
        mapping_type=MappingType.EXACT,
        mapping_scope=MappingScope.OUTCOME_CAPABILITY_FACET,
        evidence=(evidence(source=source, text=statement),),
        proposal_method=method,
        proposer_ref="actor:proposer-1",
    )


def proposal_review(
    item: CapabilityMappingProposal,
    *,
    decision: MappingDecision = MappingDecision.APPROVE,
    reviewer: str = "actor:reviewer-1",
) -> CapabilityMappingReview:
    return CapabilityMappingReview(
        proposal_id=item.proposal_id,
        proposal_fingerprint=item.proposal_fingerprint,
        reviewer_ref=reviewer,
        decision=decision,
        rationale="Reviewed the exact semantic proposal.",
    )


def activation_approval(
    item: CapabilityMappingProposal,
    item_review: CapabilityMappingReview,
    pin: CapabilityDefinitionPin,
    *,
    approval_ref: str = "approval:mapping-1",
    source_pin: SourceSemanticPin | None = None,
    target_pin_override: CapabilityDefinitionPin | None = None,
) -> MappingActivationApproval:
    return MappingActivationApproval(
        approval_ref=approval_ref,
        proposal_id=item.proposal_id,
        proposal_fingerprint=item.proposal_fingerprint,
        review_fingerprint=fingerprint_mapping_review(item_review),
        source_pin=source_pin or build_source_semantic_pin(item.source_ref, item.evidence),
        target_definition_pin=target_pin_override or pin,
        approver_ref="actor:approver-1",
    )


def activate(
    item=None,
    item_review=None,
    *,
    release=None,
    approval=None,
    mapping_id="mapping:course-7:outcome-1",
    existing_mappings=(),
):
    item = item or proposal()
    item_review = item_review or proposal_review(item)
    release = release or active_release()
    pin = CapabilityDefinitionPin(
        capability_ref=item.target_capability_ref,
        pack_release_ref=CapabilityPackReleaseRef(
            pack_id=release.pack_id,
            version=release.version,
            checksum=release.content_checksum,
        ),
    )
    approval = approval or activation_approval(item, item_review, pin)
    return activate_governed_mapping(
        mapping_id=mapping_id,
        proposal=item,
        review=item_review,
        activation_approval=approval,
        current_source_pin=build_source_semantic_pin(item.source_ref, item.evidence),
        active_release_context=(release,),
        existing_mappings=existing_mappings,
    )


def test_source_semantic_pin_is_deterministic_and_order_independent() -> None:
    source = source_ref()
    first = evidence(source=source, locator="course:objective:1", text="Outcome one.")
    second = evidence(source=source, locator="course:objective:2", text="Outcome two.")

    pin = build_source_semantic_pin(source, (first, second))
    reversed_pin = build_source_semantic_pin(source, (second, first))

    assert pin == reversed_pin
    assert pin.source_ref == source
    assert pin.evidence_fingerprint.startswith("sha256:")


def test_source_pin_changes_when_source_version_changes() -> None:
    old_source = source_ref("catalog-v1")
    new_source = source_ref("catalog-v2")
    old = build_source_semantic_pin(old_source, (evidence(source=old_source),))
    new = build_source_semantic_pin(new_source, (evidence(source=new_source),))

    assert old != new


def test_source_pin_changes_when_evidence_content_changes() -> None:
    source = source_ref()
    original = build_source_semantic_pin(source, (evidence(source=source),))
    changed = build_source_semantic_pin(
        source,
        (evidence(source=source, text="A changed source statement."),),
    )

    assert original != changed


def test_source_pin_rejects_evidence_from_another_source_identity() -> None:
    source = source_ref()
    unrelated = evidence(source=source_ref("catalog-v2"))

    with pytest.raises(MappingGovernanceError) as exc_info:
        build_source_semantic_pin(source, (unrelated,))

    assert exc_info.value.code == "source_pin_mismatch"


def test_source_pin_rejects_empty_evidence() -> None:
    with pytest.raises(MappingGovernanceError) as exc_info:
        build_source_semantic_pin(source_ref(), ())

    assert exc_info.value.code == "source_pin_mismatch"


def test_source_semantic_pin_rejects_malformed_evidence_fingerprint() -> None:
    with pytest.raises(ValidationError):
        SourceSemanticPin(source_ref=source_ref(), evidence_fingerprint="not-a-digest")


def test_review_fingerprint_is_stable_and_covers_semantic_review_fields() -> None:
    original = review()
    assert fingerprint_mapping_review(original) == fingerprint_mapping_review(review())

    changed_reviews = (
        review(reviewer="actor:reviewer-2"),
        review(decision=MappingDecision.REJECT),
        review(rationale="Different rationale."),
        review(proposal_fingerprint="sha256:" + "c" * 64),
    )
    assert all(
        fingerprint_mapping_review(item) != fingerprint_mapping_review(original)
        for item in changed_reviews
    )


def test_mapping_activation_approval_requires_complete_exact_pins_and_actor() -> None:
    pin = build_source_semantic_pin(source_ref(), (evidence(),))
    approval = MappingActivationApproval(
        approval_ref="approval:mapping-1",
        proposal_id="proposal:course-7:outcome-1",
        proposal_fingerprint="sha256:" + "a" * 64,
        review_fingerprint=fingerprint_mapping_review(review()),
        source_pin=pin,
        target_definition_pin=target_pin(),
        approver_ref="actor:approver-1",
    )

    assert approval.target_definition_pin == target_pin()
    assert approval.source_pin == pin
    with pytest.raises(ValidationError):
        approval.approver_ref = "actor:another"


def test_mapping_activation_approval_bounds_actor_and_references() -> None:
    pin = build_source_semantic_pin(source_ref(), (evidence(),))
    payload = {
        "approval_ref": "approval:mapping-1",
        "proposal_id": "proposal:course-7:outcome-1",
        "proposal_fingerprint": "sha256:" + "a" * 64,
        "review_fingerprint": fingerprint_mapping_review(review()),
        "source_pin": pin,
        "target_definition_pin": target_pin(),
        "approver_ref": "actor:approver-1",
    }
    for field in ("approval_ref", "proposal_id", "approver_ref"):
        with pytest.raises(ValidationError):
            MappingActivationApproval.model_validate({**payload, field: "x" * 257})


def test_mapping_activation_approval_rejects_invalid_pin_fingerprints() -> None:
    pin = build_source_semantic_pin(source_ref(), (evidence(),))
    payload = {
        "approval_ref": "approval:mapping-1",
        "proposal_id": "proposal:course-7:outcome-1",
        "proposal_fingerprint": "sha256:" + "a" * 64,
        "review_fingerprint": fingerprint_mapping_review(review()),
        "source_pin": pin,
        "target_definition_pin": target_pin(),
        "approver_ref": "actor:approver-1",
    }
    for field in ("proposal_fingerprint", "review_fingerprint"):
        with pytest.raises(ValidationError):
            MappingActivationApproval.model_validate({**payload, field: "invalid"})


def test_activation_requires_exact_review_and_review_decision() -> None:
    item = proposal()
    with pytest.raises(MappingGovernanceError, match="proposal_review_mismatch"):
        activate(item, proposal_review(item, reviewer=item.proposer_ref))
    with pytest.raises(MappingGovernanceError) as rejected:
        activate(item, proposal_review(item, decision=MappingDecision.REJECT))
    assert rejected.value.code == "mapping_review_rejected"
    with pytest.raises(MappingGovernanceError) as uncertain:
        activate(item, proposal_review(item, decision=MappingDecision.UNCERTAIN))
    assert uncertain.value.code == "mapping_review_uncertain"


def test_activation_rejects_review_of_old_proposal_fingerprint() -> None:
    original = proposal()
    reviewed = proposal_review(original)
    changed = proposal(statement="Changed source meaning.")

    with pytest.raises(MappingGovernanceError) as exc_info:
        activate(changed, reviewed)

    assert exc_info.value.code == "proposal_review_mismatch"


def test_activation_requires_current_source_pin_and_exact_approval_pins() -> None:
    item = proposal()
    item_review = proposal_review(item)
    release = active_release()
    pin = CapabilityDefinitionPin(
        capability_ref=item.target_capability_ref,
        pack_release_ref=CapabilityPackReleaseRef(
            pack_id=release.pack_id,
            version=release.version,
            checksum=release.content_checksum,
        ),
    )
    approval = activation_approval(item, item_review, pin)
    changed_source = build_source_semantic_pin(
        item.source_ref, (evidence(source=item.source_ref, text="New source version."),)
    )
    with pytest.raises(MappingGovernanceError) as stale:
        activate_governed_mapping(
            mapping_id="mapping:course-7:outcome-1",
            proposal=item,
            review=item_review,
            activation_approval=approval,
            current_source_pin=changed_source,
            active_release_context=(release,),
        )
    assert stale.value.code == "stale_source"

    bad_approval = activation_approval(
        item,
        item_review,
        pin,
        target_pin_override=target_pin(),
    )
    with pytest.raises(MappingGovernanceError) as mismatch:
        activate(item, item_review, release=release, approval=bad_approval)
    assert mismatch.value.code == "activation_approval_mismatch"


def test_review_and_active_target_without_activation_approval_are_not_authority() -> None:
    item = proposal()
    item_review = proposal_review(item)
    release = active_release()
    with pytest.raises(MappingGovernanceError) as exc_info:
        activate_governed_mapping(
            mapping_id="mapping:course-7:outcome-1",
            proposal=item,
            review=item_review,
            current_source_pin=build_source_semantic_pin(item.source_ref, item.evidence),
            activation_approval=None,
            active_release_context=(release,),
        )
    assert exc_info.value.code == "activation_approval_required"


def test_activation_approval_must_pin_source_and_exact_review_fingerprint() -> None:
    item = proposal()
    item_review = proposal_review(item)
    release = active_release()
    pin = CapabilityDefinitionPin(
        capability_ref=item.target_capability_ref,
        pack_release_ref=CapabilityPackReleaseRef(
            pack_id=release.pack_id,
            version=release.version,
            checksum=release.content_checksum,
        ),
    )
    base = activation_approval(item, item_review, pin)
    for altered in (
        base.model_copy(
            update={
                "source_pin": build_source_semantic_pin(
                    source_ref("catalog-v2"), (evidence(source=source_ref("catalog-v2")),)
                )
            }
        ),
        base.model_copy(update={"review_fingerprint": "sha256:" + "d" * 64}),
        base.model_copy(update={"proposal_id": "proposal:another"}),
        base.model_copy(update={"proposal_fingerprint": "sha256:" + "e" * 64}),
    ):
        with pytest.raises(MappingGovernanceError) as exc_info:
            activate(item, item_review, release=release, approval=altered)
        assert exc_info.value.code == "activation_approval_mismatch"


@pytest.mark.parametrize(
    ("target", "release_factory", "expected_error"),
    [
        ("capability:unregistered:synthetic_capability", active_release, UnknownNamespaceError),
        ("capability:test_core:synthetic_capability", active_release, UnknownCapabilityError),
    ],
)
def test_activation_requires_registered_active_target_without_inference(
    target, release_factory, expected_error
) -> None:
    with pytest.raises(expected_error):
        activate(proposal(target=target), release=release_factory())


def test_activation_rejects_draft_target_release() -> None:
    draft = build_capability_pack_release(
        pack_id="test_core_pack",
        namespace_key="test_core",
        version="1.0",
        owner_ref="team:capability-governance",
        definitions=(
            CapabilityDefinition(
                canonical_ref=CanonicalCapabilityRef.parse(
                    "capability:test_core:project_management"
                ),
                label="Project Management",
                definition="Plan and coordinate project delivery.",
            ),
        ),
    )
    with pytest.raises(PackNotActiveError):
        activate(proposal(), release=draft)


def test_activation_retains_exact_target_pin_and_does_not_redirect() -> None:
    release = active_release()
    item = proposal()
    governed = activate(item, release=release)

    assert governed.target_definition_pin.pack_release_ref.version == release.version
    assert governed.target_definition_pin.pack_release_ref.checksum == release.content_checksum
    assert governed.target_definition_pin.capability_ref == item.target_capability_ref


def test_ai_assisted_proposal_needs_the_same_human_review_and_activation() -> None:
    item = proposal(method=ProposalMethod.AI_ASSISTED)
    governed = activate(item)

    assert governed.proposal_fingerprint == item.proposal_fingerprint
    assert governed.status is GovernedMappingStatus.ACTIVE


def test_mapping_identity_is_distinct_and_approver_may_equal_reviewer() -> None:
    item = proposal()
    item_review = proposal_review(item, reviewer="actor:approver-1")
    governed = activate(item, item_review)

    assert governed.mapping_id not in {
        governed.proposal_id,
        str(governed.source_pin.source_ref),
        str(governed.target_definition_pin.capability_ref),
    }
    assert governed.approver_ref == item_review.reviewer_ref


def test_identical_active_mapping_activation_is_idempotent() -> None:
    first = activate()
    second = activate(existing_mappings=(first,))

    assert second == first


def test_mapping_id_cannot_be_reused_for_different_authority_payload() -> None:
    first = activate()
    changed_proposal = proposal(statement="Different evidence, same source identity.")

    with pytest.raises(MappingGovernanceError) as exc_info:
        activate(changed_proposal, existing_mappings=(first,))

    assert exc_info.value.code == "mapping_id_conflict"


def test_same_semantic_facet_cannot_be_activated_for_two_targets() -> None:
    release = active_release(include_second=True)
    first = activate(release=release)
    second_proposal = proposal(target="capability:test_core:delivery")

    with pytest.raises(MappingGovernanceError) as exc_info:
        activate(
            second_proposal,
            release=release,
            mapping_id="mapping:course-7:outcome-1:other-target",
            existing_mappings=(first,),
        )

    assert exc_info.value.code == "mapping_conflict"


def test_distinct_semantic_facets_in_same_course_do_not_conflict() -> None:
    release = active_release(include_second=True)
    first = activate(release=release)
    other_source = SourceSemanticRef(
        source_namespace="test_catalog",
        entity_kind=SourceSemanticKind.COURSE_LEARNING_OUTCOME,
        source_id="course-7#outcome-2",
        source_version="catalog-v1",
    )
    second_proposal = proposal(target="capability:test_core:delivery", source=other_source)

    result = activate(
        second_proposal,
        release=release,
        mapping_id="mapping:course-7:outcome-2",
        existing_mappings=(first,),
    )

    assert result.source_pin.source_ref != first.source_pin.source_ref


def test_conflict_check_does_not_infer_similarity_from_free_text() -> None:
    release = active_release(include_second=True)
    first = activate(release=release)
    similar_but_not_identical = proposal(
        statement="Explain deterministic source pinning and its evidence."
    )

    result = activate(
        similar_but_not_identical,
        release=release,
        mapping_id="mapping:course-7:similar-evidence",
        existing_mappings=(first,),
    )

    assert result.source_pin.evidence_fingerprint != first.source_pin.evidence_fingerprint


def test_deprecated_mapping_does_not_block_new_active_mapping_conflict_key() -> None:
    release = active_release(include_second=True)
    deprecated = deprecate_governed_mapping(
        activate(release=release), actor_ref="actor:owner", reason="Retire old mapping."
    )
    replacement_proposal = proposal(target="capability:test_core:delivery")

    result = activate(
        replacement_proposal,
        release=release,
        mapping_id="mapping:course-7:replacement",
        existing_mappings=(deprecated,),
    )

    assert result.status is GovernedMappingStatus.ACTIVE


def test_deprecation_is_one_way_and_preserves_authority_fingerprint() -> None:
    active = activate()
    deprecated = deprecate_governed_mapping(
        active, actor_ref="actor:owner", reason="Source evidence has been superseded."
    )

    assert deprecated is not active
    assert deprecated.status is GovernedMappingStatus.DEPRECATED
    assert deprecated.mapping_fingerprint == active.mapping_fingerprint
    with pytest.raises(MappingGovernanceError) as exc_info:
        deprecate_governed_mapping(deprecated, actor_ref="actor:owner", reason="Again.")
    assert exc_info.value.code == "mapping_not_active"


def test_current_resolution_returns_exact_active_binding() -> None:
    governed = activate()
    binding = resolve_governed_mapping_for_use(
        governed,
        current_source_pin=governed.source_pin,
        active_release_context=(active_release(),),
    )

    assert binding.resolution_mode is BindingResolutionMode.CURRENT
    assert binding.mapping_id == governed.mapping_id
    assert binding.target_definition_pin == governed.target_definition_pin


def test_current_resolution_rejects_stale_source_identity_version_or_evidence() -> None:
    governed = activate()
    sources = (
        source_ref("catalog-v2"),
        SourceSemanticRef(
            source_namespace="test_catalog",
            entity_kind=SourceSemanticKind.COURSE_LEARNING_OUTCOME,
            source_id="course-7#outcome-2",
            source_version="catalog-v1",
        ),
    )
    for source in sources:
        with pytest.raises(MappingGovernanceError) as exc_info:
            resolve_governed_mapping_for_use(
                governed,
                current_source_pin=build_source_semantic_pin(source, (evidence(source=source),)),
                active_release_context=(active_release(),),
            )
        assert exc_info.value.code == "stale_source"

    changed_evidence_pin = build_source_semantic_pin(
        governed.source_pin.source_ref,
        (evidence(source=governed.source_pin.source_ref, text="Changed current meaning."),),
    )
    with pytest.raises(MappingGovernanceError, match="stale_source"):
        resolve_governed_mapping_for_use(
            governed,
            current_source_pin=changed_evidence_pin,
            active_release_context=(active_release(),),
        )


def test_current_resolution_never_repins_to_a_newer_active_release() -> None:
    governed = activate(release=active_release("1.0"))
    newer = active_release("2.0")

    with pytest.raises(MappingGovernanceError) as exc_info:
        resolve_governed_mapping_for_use(
            governed,
            current_source_pin=governed.source_pin,
            active_release_context=(newer,),
        )
    assert exc_info.value.code == "target_pin_mismatch"


def test_current_resolution_rejects_deprecated_mapping_and_conflicting_context() -> None:
    release = active_release(include_second=True)
    governed = activate(release=release)
    deprecated = deprecate_governed_mapping(
        governed, actor_ref="actor:owner", reason="No longer current."
    )
    with pytest.raises(MappingGovernanceError, match="mapping_deprecated"):
        resolve_governed_mapping_for_use(
            deprecated,
            current_source_pin=deprecated.source_pin,
            active_release_context=(release,),
        )

    other = activate(
        proposal(target="capability:test_core:delivery"),
        release=release,
        mapping_id="mapping:course-7:conflict",
    )
    with pytest.raises(MappingGovernanceError, match="mapping_conflict"):
        resolve_governed_mapping_for_use(
            governed,
            current_source_pin=governed.source_pin,
            active_release_context=(release,),
            mapping_context=(other,),
        )


def test_historical_resolution_accepts_deprecated_mapping_and_exact_target() -> None:
    release = active_release()
    governed = deprecate_governed_mapping(
        activate(release=release), actor_ref="actor:owner", reason="Retained for history."
    )
    deprecated_release = deprecate_capability_pack_release(
        release, actor_ref="actor:owner", reason="Retained for history."
    )

    result = resolve_governed_mapping_historical(
        governed,
        historical_source_pin=governed.source_pin,
        release_context=(deprecated_release,),
    )

    assert result.resolution_mode is BindingResolutionMode.HISTORICAL
    assert result.target_definition_pin == governed.target_definition_pin


def test_historical_resolution_rejects_stale_source_and_draft_target() -> None:
    release = active_release()
    governed = activate(release=release)
    stale = build_source_semantic_pin(
        source_ref("catalog-v2"), (evidence(source=source_ref("catalog-v2")),)
    )
    with pytest.raises(MappingGovernanceError, match="stale_source"):
        resolve_governed_mapping_historical(
            governed, historical_source_pin=stale, release_context=(release,)
        )

    draft = build_capability_pack_release(
        pack_id="test_core_pack",
        namespace_key="test_core",
        version="1.0",
        owner_ref="team:capability-governance",
        definitions=(
            CapabilityDefinition(
                canonical_ref=governed.target_definition_pin.capability_ref,
                label="Project Management",
                definition="Plan and coordinate project delivery.",
            ),
        ),
    )
    with pytest.raises(PackNotActiveError):
        resolve_governed_mapping_historical(
            governed,
            historical_source_pin=governed.source_pin,
            release_context=(draft,),
        )


def test_governed_mapping_is_complete_immutable_and_fingerprinted() -> None:
    governed = activate()
    assert governed.mapping_fingerprint.startswith("sha256:")
    assert governed.status is GovernedMappingStatus.ACTIVE
    with pytest.raises(ValidationError):
        governed.status = GovernedMappingStatus.DEPRECATED
    assert MappingDeprecationRecord(actor_ref="actor:owner", reason="Retire mapping.")


def test_direct_incomplete_mapping_construction_is_rejected() -> None:
    with pytest.raises(ValidationError):
        GovernedCapabilityMapping.model_validate(
            {
                "mapping_id": "mapping:incomplete",
                "status": GovernedMappingStatus.ACTIVE,
                "mapping_fingerprint": "sha256:" + "a" * 64,
            }
        )


def test_current_resolution_rejects_tampered_mapping_fingerprint() -> None:
    governed = activate()
    tampered = governed.model_copy(update={"mapping_fingerprint": "sha256:" + "f" * 64})

    with pytest.raises(MappingGovernanceError, match="mapping_fingerprint_mismatch"):
        resolve_governed_mapping_for_use(
            tampered,
            current_source_pin=governed.source_pin,
            active_release_context=(active_release(),),
        )
