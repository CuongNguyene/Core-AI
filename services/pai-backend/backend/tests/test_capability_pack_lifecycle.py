import pytest
from pydantic import ValidationError

from app.capability_governance.definitions import (
    CapabilityDefinition,
    CapabilityDefinitionStatus,
)
from app.capability_governance.errors import (
    ChecksumMismatchError,
    DependencyCycleError,
    DependencyNotActiveError,
    DuplicateCapabilityError,
    NamespaceConflictError,
)
from app.capability_governance.identity import CanonicalCapabilityRef
from app.capability_governance.packs import (
    CapabilityGovernanceDecision,
    CapabilityGovernanceReview,
    CapabilityPackDependency,
    CapabilityPackId,
    CapabilityPackRelease,
    CapabilityPackReleaseRef,
    CapabilityPackStatus,
    CapabilityReleaseApproval,
    activate_capability_pack_release,
    build_capability_pack_release,
    compute_release_checksum,
    deprecate_capability_pack_release,
)


def _definition(
    key: str = "project_management",
    *,
    namespace: str = "test_core",
    status: CapabilityDefinitionStatus = CapabilityDefinitionStatus.DRAFT,
    label: str = "Project Management",
    body: str = "Plan and coordinate project delivery.",
) -> CapabilityDefinition:
    return CapabilityDefinition(
        canonical_ref=CanonicalCapabilityRef.parse(f"capability:{namespace}:{key}"),
        label=label,
        definition=body,
        status=status,
        **(
            {
                "deprecation": {
                    "actor_ref": "actor:owner",
                    "reason": "No longer offered for new bindings.",
                }
            }
            if status is CapabilityDefinitionStatus.DEPRECATED
            else {}
        ),
    )


def _draft(
    *,
    pack_id: str = "test_core_pack",
    namespace: str = "test_core",
    version: str = "1.0",
    definitions: tuple[CapabilityDefinition, ...] | None = None,
    dependencies: tuple[CapabilityPackDependency, ...] = (),
) -> CapabilityPackRelease:
    return build_capability_pack_release(
        pack_id=pack_id,
        namespace_key=namespace,
        version=version,
        owner_ref="team:capability-governance",
        definitions=(
            definitions if definitions is not None else (_definition(namespace=namespace),)
        ),
        dependencies=dependencies,
    )


def _review(
    *,
    reviewer: str = "actor:independent-reviewer",
    decision: CapabilityGovernanceDecision = CapabilityGovernanceDecision.APPROVE,
) -> CapabilityGovernanceReview:
    return CapabilityGovernanceReview(
        review_ref="review:release-17",
        reviewer_ref=reviewer,
        decision=decision,
        collision_review_ref="collision-review:release-17",
    )


def _approval(
    *, decision: CapabilityGovernanceDecision = CapabilityGovernanceDecision.APPROVE
) -> CapabilityReleaseApproval:
    return CapabilityReleaseApproval(
        approval_ref="approval:release-17",
        approver_ref="actor:release-approver",
        decision=decision,
    )


def _activate(
    release: CapabilityPackRelease,
    *,
    existing: tuple[CapabilityPackRelease, ...] = (),
) -> CapabilityPackRelease:
    return activate_capability_pack_release(
        release,
        review=_review(),
        approval=_approval(),
        existing_releases=existing,
    )


def test_pack_id_is_stable_and_release_version_is_separate() -> None:
    pack_id = CapabilityPackId("test_core_pack")
    release = _draft(version="release-2026.1")

    assert str(pack_id) == "test_core_pack"
    assert release.pack_id == pack_id
    assert release.version == "release-2026.1"
    assert "release-2026.1" not in str(release.definitions[0].canonical_ref)


@pytest.mark.parametrize("value", ["", "Test_Pack", "a", "bad-pack", "test.pack"])
def test_pack_id_rejects_invalid_keys(value: str) -> None:
    with pytest.raises(ValidationError):
        CapabilityPackId(value)


@pytest.mark.parametrize("version", ["", "latest", "current", "1.*", ">=1.0", "^1.0"])
def test_release_version_rejects_latest_and_ranges(version: str) -> None:
    with pytest.raises(ValidationError):
        _draft(version=version)


def test_draft_release_requires_definitions_and_single_owned_namespace() -> None:
    with pytest.raises(ValidationError, match="definitions"):
        _draft(definitions=())

    with pytest.raises(ValidationError, match="namespace"):
        _draft(definitions=(_definition(namespace="other_core"),))


def test_deprecated_release_cannot_contain_draft_definitions() -> None:
    release = _draft()
    with pytest.raises(ValidationError, match="draft definitions"):
        CapabilityPackRelease.model_validate(
            {
                **release.model_dump(mode="python"),
                "status": CapabilityPackStatus.DEPRECATED,
                "deprecation": {"actor_ref": "actor:owner", "reason": "Superseded."},
            }
        )


def test_duplicate_capability_refs_within_release_are_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate capability"):
        _draft(definitions=(_definition(), _definition(label="Duplicate")))


def test_release_checksum_is_deterministic_and_order_independent() -> None:
    first = _definition("alpha_skill", label="Alpha", body="Do alpha work.")
    second = _definition("beta_skill", label="Beta", body="Do beta work.")
    a = _draft(definitions=(first, second))
    b = _draft(definitions=(second, first))

    assert a.content_checksum == b.content_checksum
    assert a.content_checksum == compute_release_checksum(
        pack_id=a.pack_id,
        namespace_key=a.namespace_key,
        version=a.version,
        definitions=a.definitions,
        dependencies=a.dependencies,
    )


def test_dependency_order_does_not_change_release_checksum() -> None:
    first_dependency = CapabilityPackDependency(
        release_ref=CapabilityPackReleaseRef(
            pack_id=CapabilityPackId("dependency_one"),
            version="1.0",
            checksum="sha256:" + "1" * 64,
        )
    )
    second_dependency = CapabilityPackDependency(
        release_ref=CapabilityPackReleaseRef(
            pack_id=CapabilityPackId("dependency_two"),
            version="2.0",
            checksum="sha256:" + "2" * 64,
        )
    )

    first = _draft(dependencies=(first_dependency, second_dependency))
    second = _draft(dependencies=(second_dependency, first_dependency))

    assert first.content_checksum == second.content_checksum


def test_semantic_payload_change_changes_checksum_but_lifecycle_does_not() -> None:
    base = _draft()
    changed = _draft(definitions=(_definition(body="Coordinate a portfolio."),))
    active = _activate(base)

    assert changed.content_checksum != base.content_checksum
    assert active.content_checksum == base.content_checksum


def test_label_change_changes_payload_digest_without_changing_capability_identity() -> None:
    original = _draft()
    renamed = _draft(definitions=(_definition(label="Project Delivery"),))

    assert original.definitions[0].canonical_ref == renamed.definitions[0].canonical_ref
    assert original.content_checksum != renamed.content_checksum


def test_release_reference_pins_exact_pack_version_and_checksum() -> None:
    release = _draft()
    reference = CapabilityPackReleaseRef(
        pack_id=release.pack_id,
        version=release.version,
        checksum=release.content_checksum,
    )

    assert reference.pack_id == release.pack_id
    assert reference.version == "1.0"
    assert reference.checksum == release.content_checksum


def test_dependency_rejects_non_exact_or_latest_release_refs() -> None:
    with pytest.raises(ValidationError):
        CapabilityPackReleaseRef(
            pack_id=CapabilityPackId("test_core_pack"),
            version="latest",
            checksum="sha256:" + "a" * 64,
        )


def test_exact_active_dependency_allows_activation() -> None:
    dependency_release = _activate(_draft(pack_id="dependency_pack", namespace="dependency_core"))
    dependency = CapabilityPackDependency(
        release_ref=CapabilityPackReleaseRef(
            pack_id=dependency_release.pack_id,
            version=dependency_release.version,
            checksum=dependency_release.content_checksum,
        )
    )
    release = _draft(
        pack_id="dependent_pack",
        namespace="dependent_core",
        dependencies=(dependency,),
    )

    active = _activate(release, existing=(dependency_release,))

    assert active.status is CapabilityPackStatus.ACTIVE


def test_dependency_must_resolve_the_exact_requested_version() -> None:
    available = _activate(
        _draft(pack_id="dependency_pack", namespace="dependency_core", version="1.0")
    )
    dependency = CapabilityPackDependency(
        release_ref=CapabilityPackReleaseRef(
            pack_id=available.pack_id,
            version="2.0",
            checksum=available.content_checksum,
        )
    )

    with pytest.raises(DependencyNotActiveError):
        _activate(
            _draft(dependencies=(dependency,)),
            existing=(available,),
        )


def test_missing_dependency_fails_activation() -> None:
    dependency = CapabilityPackDependency(
        release_ref=CapabilityPackReleaseRef(
            pack_id=CapabilityPackId("missing_pack"),
            version="1.0",
            checksum="sha256:" + "a" * 64,
        )
    )

    with pytest.raises(DependencyNotActiveError):
        _activate(_draft(dependencies=(dependency,)))


def test_inactive_dependency_fails_activation() -> None:
    dependency_release = _draft(pack_id="dependency_pack", namespace="dependency_core")
    dependency = CapabilityPackDependency(
        release_ref=CapabilityPackReleaseRef(
            pack_id=dependency_release.pack_id,
            version=dependency_release.version,
            checksum=dependency_release.content_checksum,
        )
    )

    with pytest.raises(DependencyNotActiveError):
        _activate(
            _draft(dependencies=(dependency,)),
            existing=(dependency_release,),
        )


def test_dependency_checksum_mismatch_fails_activation() -> None:
    dependency_release = _activate(_draft(pack_id="dependency_pack", namespace="dependency_core"))
    dependency = CapabilityPackDependency(
        release_ref=CapabilityPackReleaseRef(
            pack_id=dependency_release.pack_id,
            version=dependency_release.version,
            checksum="sha256:" + "b" * 64,
        )
    )

    with pytest.raises(ChecksumMismatchError):
        _activate(
            _draft(dependencies=(dependency,)),
            existing=(dependency_release,),
        )


def test_self_dependency_cycle_is_rejected() -> None:
    dependency = CapabilityPackDependency(
        release_ref=CapabilityPackReleaseRef(
            pack_id=CapabilityPackId("test_core_pack"),
            version="1.0",
            checksum="sha256:" + "0" * 64,
        )
    )

    with pytest.raises(DependencyCycleError):
        _activate(_draft(dependencies=(dependency,)))


def test_multi_pack_dependency_cycle_is_rejected() -> None:
    b_to_a = CapabilityPackDependency(
        release_ref=CapabilityPackReleaseRef(
            pack_id=CapabilityPackId("pack_a"),
            version="1.0",
            checksum="sha256:" + "a" * 64,
        )
    )
    pack_b = _draft(pack_id="pack_b", namespace="test_core_b", dependencies=(b_to_a,))
    a_to_b = CapabilityPackDependency(
        release_ref=CapabilityPackReleaseRef(
            pack_id=CapabilityPackId("pack_b"),
            version="1.0",
            checksum="sha256:" + "b" * 64,
        )
    )
    pack_a = _draft(pack_id="pack_a", namespace="test_core_a", dependencies=(a_to_b,))

    with pytest.raises(DependencyCycleError):
        _activate(pack_a, existing=(pack_b,))


def test_duplicate_dependencies_are_rejected() -> None:
    dependency_release = _activate(_draft(pack_id="dependency_pack", namespace="dependency_core"))
    reference = CapabilityPackReleaseRef(
        pack_id=dependency_release.pack_id,
        version=dependency_release.version,
        checksum=dependency_release.content_checksum,
    )

    with pytest.raises(ValidationError, match="duplicate dependency"):
        _draft(
            dependencies=(
                CapabilityPackDependency(release_ref=reference),
                CapabilityPackDependency(release_ref=reference),
            )
        )


def test_activation_requires_an_independent_approving_reviewer() -> None:
    release = _draft()

    with pytest.raises(ValueError, match="reviewer_must_be_independent"):
        activate_capability_pack_release(
            release,
            review=_review(reviewer=release.owner_ref),
            approval=_approval(),
        )


def test_approver_may_equal_reviewer_because_separation_is_not_required() -> None:
    release = _draft()
    review = _review(reviewer="actor:release-approver")
    approval = _approval()

    active = activate_capability_pack_release(release, review=review, approval=approval)

    assert active.review is not None
    assert active.approval is not None
    assert active.review.reviewer_ref == active.approval.approver_ref


@pytest.mark.parametrize(
    ("review", "approval"),
    [
        (None, _approval()),
        (_review(decision=CapabilityGovernanceDecision.REJECT), _approval()),
        (_review(), None),
        (_review(), _approval(decision=CapabilityGovernanceDecision.REJECT)),
    ],
)
def test_activation_requires_approved_review_and_explicit_approval(
    review: CapabilityGovernanceReview | None,
    approval: CapabilityReleaseApproval | None,
) -> None:
    with pytest.raises(ValueError):
        activate_capability_pack_release(_draft(), review=review, approval=approval)


def test_rejected_review_leaves_release_draft() -> None:
    draft = _draft()

    with pytest.raises(ValueError):
        activate_capability_pack_release(
            draft,
            review=_review(decision=CapabilityGovernanceDecision.REJECT),
            approval=_approval(),
        )

    assert draft.status is CapabilityPackStatus.DRAFT


def test_collision_review_evidence_is_required_for_activation() -> None:
    release = _draft()
    with pytest.raises(ValidationError):
        review = CapabilityGovernanceReview(
            review_ref="review:release-17",
            reviewer_ref="actor:independent-reviewer",
            decision=CapabilityGovernanceDecision.APPROVE,
            collision_review_ref="",
        )
        activate_capability_pack_release(release, review=review, approval=_approval())


def test_governance_actor_and_evidence_refs_must_be_non_blank() -> None:
    with pytest.raises(ValidationError):
        CapabilityGovernanceReview(
            review_ref="review:1",
            reviewer_ref=" ",
            decision=CapabilityGovernanceDecision.APPROVE,
            collision_review_ref="collision:1",
        )

    with pytest.raises(ValidationError):
        CapabilityReleaseApproval(
            approval_ref="approval:1",
            approver_ref=" ",
            decision=CapabilityGovernanceDecision.APPROVE,
        )


def test_activation_transitions_release_and_definitions_without_changing_checksum() -> None:
    draft = _draft()

    active = _activate(draft)

    assert draft.status is CapabilityPackStatus.DRAFT
    assert active.status is CapabilityPackStatus.ACTIVE
    assert active.definitions[0].status is CapabilityDefinitionStatus.ACTIVE
    assert active.content_checksum == draft.content_checksum
    assert active.approval is not None
    assert active.review is not None


def test_definition_lifecycle_and_governance_metadata_are_excluded_from_checksum() -> None:
    active = _activate(_draft())
    changed_lifecycle_record = active.model_copy(
        update={
            "review": active.review.model_copy(update={"review_ref": "review:updated"}),
            "approval": active.approval.model_copy(update={"approval_ref": "approval:updated"}),
        }
    )

    assert changed_lifecycle_record.content_checksum == active.content_checksum


def test_activation_rejects_non_draft_release() -> None:
    with pytest.raises(ValueError, match="release_must_be_draft"):
        _activate(_activate(_draft()))


def test_activation_rejects_duplicate_namespace_owner() -> None:
    first = _activate(_draft(pack_id="first_pack"))
    second = _draft(pack_id="second_pack")

    with pytest.raises(NamespaceConflictError):
        _activate(second, existing=(first,))


def test_same_pack_identity_may_own_namespace_across_releases() -> None:
    first = _activate(_draft(version="1.0"))
    second = _activate(
        _draft(
            version="2.0",
            definitions=(_definition("delivery_planning"),),
        ),
        existing=(first,),
    )

    assert first.pack_id == second.pack_id
    assert first.namespace_key == second.namespace_key


def test_pack_cannot_change_its_namespace_between_releases() -> None:
    first = _activate(_draft(version="1.0"))
    changed_namespace = build_capability_pack_release(
        pack_id="test_core_pack",
        namespace_key="other_core",
        version="2.0",
        owner_ref="team:capability-governance",
        definitions=(_definition("new_concept", namespace="other_core"),),
    )

    with pytest.raises(NamespaceConflictError):
        _activate(changed_namespace, existing=(first,))


def test_deprecated_namespace_cannot_be_claimed_by_an_independent_pack() -> None:
    deprecated = deprecate_capability_pack_release(
        _activate(_draft()),
        actor_ref="actor:owner",
        reason="No automatic namespace transfer.",
    )

    with pytest.raises(NamespaceConflictError):
        _activate(_draft(pack_id="new_owner_pack"), existing=(deprecated,))


def test_activation_rejects_same_canonical_ref_in_two_active_releases() -> None:
    first = _activate(_draft(version="1.0"))

    with pytest.raises(DuplicateCapabilityError):
        _activate(_draft(version="2.0"), existing=(first,))


def test_deprecation_is_active_to_deprecated_only_and_keeps_release_identity() -> None:
    active = _activate(_draft())

    deprecated = deprecate_capability_pack_release(
        active,
        actor_ref="actor:pack-owner",
        reason="Replaced by a newly reviewed release.",
    )

    assert deprecated.status is CapabilityPackStatus.DEPRECATED
    assert deprecated.pack_id == active.pack_id
    assert deprecated.version == active.version
    assert deprecated.content_checksum == active.content_checksum
    assert deprecated.definitions == active.definitions
    with pytest.raises(ValueError, match="invalid_release_transition"):
        deprecate_capability_pack_release(deprecated, actor_ref="actor:pack-owner", reason="again")


def test_deprecated_release_cannot_be_reactivated() -> None:
    deprecated = deprecate_capability_pack_release(
        _activate(_draft()),
        actor_ref="actor:pack-owner",
        reason="Retain history.",
    )

    with pytest.raises(ValueError, match="release_must_be_draft"):
        _activate(deprecated)


def test_release_is_frozen_and_checksum_changes_are_rejected() -> None:
    release = _draft()

    with pytest.raises(ValidationError):
        release.version = "2.0"  # type: ignore[misc]

    with pytest.raises(ValidationError):
        CapabilityPackRelease.model_validate(
            {**release.model_dump(mode="python"), "content_checksum": "sha256:" + "f" * 64}
        )
