import pytest

from app.capability_governance.definitions import (
    CapabilityDefinition,
    CapabilityDefinitionStatus,
    CapabilityDeprecationRecord,
    deprecate_capability_definition,
)
from app.capability_governance.errors import (
    CapabilityNotActiveError,
    ChecksumMismatchError,
    DependencyNotActiveError,
    DuplicateCapabilityError,
    NamespaceConflictError,
    PackNotActiveError,
    ReleaseNotFoundError,
    UnknownCapabilityError,
    UnknownNamespaceError,
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
    deprecate_capability_pack_release,
)
from app.capability_governance.resolution import (
    CapabilityDefinitionPin,
    resolve_for_new_binding,
    resolve_historical,
)


def _definition(
    key: str = "project_management",
    *,
    status: CapabilityDefinitionStatus = CapabilityDefinitionStatus.DRAFT,
    label: str = "Project Management",
    body: str = "Plan and coordinate project delivery.",
) -> CapabilityDefinition:
    return CapabilityDefinition(
        canonical_ref=CanonicalCapabilityRef.parse(f"capability:test_core:{key}"),
        label=label,
        definition=body,
        status=status,
        **(
            {
                "deprecation": CapabilityDeprecationRecord(
                    actor_ref="actor:owner", reason="Retained for historical resolution."
                )
            }
            if status is CapabilityDefinitionStatus.DEPRECATED
            else {}
        ),
    )


def _draft(
    *,
    pack_id: str = "test_core_pack",
    version: str = "1.0",
    definition: CapabilityDefinition | None = None,
) -> CapabilityPackRelease:
    return build_capability_pack_release(
        pack_id=pack_id,
        namespace_key="test_core",
        version=version,
        owner_ref="team:capability-governance",
        definitions=(definition or _definition(),),
    )


def _active(
    release: CapabilityPackRelease,
    *,
    existing: tuple[CapabilityPackRelease, ...] = (),
) -> CapabilityPackRelease:
    return activate_capability_pack_release(
        release,
        review=CapabilityGovernanceReview(
            review_ref=f"review:{release.version}",
            reviewer_ref="actor:independent-reviewer",
            decision=CapabilityGovernanceDecision.APPROVE,
            collision_review_ref=f"collision:{release.version}",
        ),
        approval=CapabilityReleaseApproval(
            approval_ref=f"approval:{release.version}",
            approver_ref="actor:approver",
            decision=CapabilityGovernanceDecision.APPROVE,
        ),
        existing_releases=existing,
    )


def _pin(release: CapabilityPackRelease, ref: str) -> CapabilityDefinitionPin:
    return CapabilityDefinitionPin(
        capability_ref=CanonicalCapabilityRef.parse(ref),
        pack_release_ref=CapabilityPackReleaseRef(
            pack_id=release.pack_id,
            version=release.version,
            checksum=release.content_checksum,
        ),
    )


def test_active_resolution_returns_exact_definition_pin() -> None:
    active = _active(_draft())

    pin = resolve_for_new_binding(
        CanonicalCapabilityRef.parse("capability:test_core:project_management"),
        (active,),
    )

    assert pin.pack_release_ref.version == "1.0"
    assert pin.pack_release_ref.checksum == active.content_checksum


def test_syntactically_valid_unknown_namespace_is_not_authority() -> None:
    with pytest.raises(UnknownNamespaceError):
        resolve_for_new_binding(CanonicalCapabilityRef.parse("capability:unknown_core:concept"), ())


def test_unknown_capability_in_registered_namespace_is_distinguished() -> None:
    active = _active(_draft())

    with pytest.raises(UnknownCapabilityError):
        resolve_for_new_binding(
            CanonicalCapabilityRef.parse("capability:test_core:unknown_concept"),
            (active,),
        )


def test_draft_pack_is_not_authority_for_new_bindings() -> None:
    with pytest.raises(PackNotActiveError):
        resolve_for_new_binding(
            CanonicalCapabilityRef.parse("capability:test_core:project_management"),
            (_draft(),),
        )


def test_deprecated_pack_is_not_authority_for_new_bindings() -> None:
    active = _active(_draft())
    deprecated = deprecate_capability_pack_release(
        active, actor_ref="actor:owner", reason="Retain historical use."
    )

    with pytest.raises(PackNotActiveError):
        resolve_for_new_binding(
            CanonicalCapabilityRef.parse("capability:test_core:project_management"),
            (deprecated,),
        )


def test_deprecated_definition_is_not_authority_for_new_bindings() -> None:
    active = _active(_draft())
    deprecated_definition = deprecate_capability_definition(
        active.definitions[0],
        actor_ref="actor:owner",
        reason="No longer eligible for new bindings.",
    )
    deprecated_release = CapabilityPackRelease.model_validate(
        {
            **active.model_dump(mode="python"),
            "definitions": (deprecated_definition,),
        }
    )

    with pytest.raises(CapabilityNotActiveError):
        resolve_for_new_binding(deprecated_definition.canonical_ref, (deprecated_release,))


def test_historical_resolution_accepts_exact_deprecated_release() -> None:
    active = _active(_draft())
    pin = _pin(active, "capability:test_core:project_management")
    deprecated = deprecate_capability_pack_release(
        active, actor_ref="actor:owner", reason="Retain history."
    )

    resolved = resolve_historical(pin, (deprecated,))

    assert resolved == pin
    assert deprecated.status is CapabilityPackStatus.DEPRECATED


def test_historical_resolution_accepts_deprecated_definition_and_no_redirect() -> None:
    active = _active(_draft())
    pin = _pin(active, "capability:test_core:project_management")
    deprecated_definition = deprecate_capability_definition(
        active.definitions[0],
        actor_ref="actor:owner",
        reason="Use replacement only for new bindings.",
        replacement_ref=CanonicalCapabilityRef.parse("capability:test_core:delivery_planning"),
    )
    historical_release = CapabilityPackRelease.model_validate(
        {
            **active.model_dump(mode="python"),
            "definitions": (deprecated_definition,),
        }
    )

    assert resolve_historical(pin, (historical_release,)) == pin
    with pytest.raises(CapabilityNotActiveError):
        resolve_for_new_binding(pin.capability_ref, (historical_release,))


def test_historical_resolution_rejects_draft_release() -> None:
    draft = _draft()
    with pytest.raises(PackNotActiveError):
        resolve_historical(_pin(draft, "capability:test_core:project_management"), (draft,))


def test_historical_resolution_distinguishes_missing_release_and_checksum_mismatch() -> None:
    active = _active(_draft())
    pin = _pin(active, "capability:test_core:project_management")
    missing = CapabilityDefinitionPin(
        capability_ref=pin.capability_ref,
        pack_release_ref=CapabilityPackReleaseRef(
            pack_id=CapabilityPackId("test_core_pack"),
            version="9.0",
            checksum="sha256:" + "a" * 64,
        ),
    )
    bad_checksum = CapabilityDefinitionPin(
        capability_ref=pin.capability_ref,
        pack_release_ref=CapabilityPackReleaseRef(
            pack_id=active.pack_id,
            version=active.version,
            checksum="sha256:" + "b" * 64,
        ),
    )

    with pytest.raises(ReleaseNotFoundError):
        resolve_historical(missing, (active,))
    with pytest.raises(ChecksumMismatchError):
        resolve_historical(bad_checksum, (active,))


def test_historical_resolution_rejects_capability_absent_from_exact_release() -> None:
    active = _active(_draft())
    wrong_pin = _pin(active, "capability:test_core:another_capability")

    with pytest.raises(UnknownCapabilityError):
        resolve_historical(wrong_pin, (active,))


def test_stable_capability_identity_resolves_to_a_later_exact_release() -> None:
    first = _active(_draft(version="1.0"))
    first_pin = _pin(first, "capability:test_core:project_management")
    deprecated_first = deprecate_capability_pack_release(
        first,
        actor_ref="actor:owner",
        reason="Move new bindings to the successor release.",
    )
    second = _active(
        _draft(
            version="2.0",
            definition=_definition(
                label="Project Delivery", body="Coordinate planned project outcomes."
            ),
        ),
        existing=(deprecated_first,),
    )

    second_pin = resolve_for_new_binding(first_pin.capability_ref, (deprecated_first, second))
    historical = resolve_historical(first_pin, (deprecated_first, second))

    assert second_pin.capability_ref == first_pin.capability_ref
    assert second_pin.pack_release_ref.version == "2.0"
    assert historical.pack_release_ref.version == "1.0"


def test_namespace_collision_between_active_pack_owners_fails_closed() -> None:
    first = _active(_draft(pack_id="owner_a"))
    second = _active(_draft(pack_id="owner_b"))

    with pytest.raises(NamespaceConflictError):
        resolve_for_new_binding(
            CanonicalCapabilityRef.parse("capability:test_core:project_management"),
            (first, second),
        )


def test_duplicate_active_canonical_refs_do_not_choose_an_arbitrary_release() -> None:
    first = _active(_draft(version="1.0"))
    second = _active(_draft(version="2.0"))

    with pytest.raises(DuplicateCapabilityError, match="multiple releases"):
        resolve_for_new_binding(
            CanonicalCapabilityRef.parse("capability:test_core:project_management"),
            (first, second),
        )


def test_similar_labels_do_not_cause_semantic_resolution_or_mapping() -> None:
    release = _active(
        _draft(
            definition=_definition(
                key="project_planning",
                label="Project Planning",
                body="Prepare a project schedule.",
            )
        )
    )

    pin = resolve_for_new_binding(
        CanonicalCapabilityRef.parse("capability:test_core:project_planning"),
        (release,),
    )

    assert pin.capability_ref.semantic_key == "project_planning"
    assert pin.capability_ref.semantic_key != "project_management"


def test_active_resolution_requires_dependency_closure_to_remain_active() -> None:
    dependency = _active(
        build_capability_pack_release(
            pack_id="dependency_pack",
            namespace_key="dependency_core",
            version="1.0",
            owner_ref="team:dependency",
            definitions=(
                CapabilityDefinition(
                    canonical_ref=CanonicalCapabilityRef.parse(
                        "capability:dependency_core:base_concept"
                    ),
                    label="Base Concept",
                    definition="A synthetic dependency definition.",
                ),
            ),
        )
    )
    dependency_edge = CapabilityPackDependency(
        release_ref=CapabilityPackReleaseRef(
            pack_id=dependency.pack_id,
            version=dependency.version,
            checksum=dependency.content_checksum,
        )
    )
    dependent = _active(
        build_capability_pack_release(
            pack_id="test_core_pack",
            namespace_key="test_core",
            version="1.0",
            owner_ref="team:capability-governance",
            definitions=(_definition(),),
            dependencies=(dependency_edge,),
        ),
        existing=(dependency,),
    )
    deprecated_dependency = deprecate_capability_pack_release(
        dependency, actor_ref="actor:owner", reason="No new dependent releases."
    )

    with pytest.raises(DependencyNotActiveError):
        resolve_for_new_binding(
            CanonicalCapabilityRef.parse("capability:test_core:project_management"),
            (dependent, deprecated_dependency),
        )

    dependent_pin = _pin(dependent, "capability:test_core:project_management")
    assert resolve_historical(dependent_pin, (dependent, deprecated_dependency)) == dependent_pin
