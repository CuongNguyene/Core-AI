import pytest
from pydantic import ValidationError

from app.capability_governance.identity import (
    CanonicalCapabilityRef,
    CapabilityIdentityPair,
    SourceSemanticKind,
    SourceSemanticRef,
)


def test_canonical_ref_round_trips_as_one_stable_string() -> None:
    ref = CanonicalCapabilityRef.parse("capability:software:programming_fundamentals")

    assert ref.namespace_key == "software"
    assert ref.semantic_key == "programming_fundamentals"
    assert str(ref) == "capability:software:programming_fundamentals"
    assert ref.model_dump() == "capability:software:programming_fundamentals"
    assert CanonicalCapabilityRef.parse(str(ref)) == ref
    assert hash(ref) == hash(CanonicalCapabilityRef.parse(str(ref)))


@pytest.mark.parametrize(
    "value",
    [
        "project_management",
        "Capability:software:programming",
        "capability:software",
        "capability::programming",
        "capability:software:programming:extra",
        " capability:software:programming",
        "capability:software:programming ",
        "capability:soft ware:programming",
        "capability:Software:programming",
        "capability:software:Programming",
        "capability:software:project-management",
        "capability:software:../python",
        "capability:software:programming@2",
        "capability:software@1:programming",
        "capability:a:programming",
        "capability:software:a",
        "",
    ],
)
def test_canonical_ref_rejects_malformed_or_versioned_values(value: str) -> None:
    with pytest.raises(ValidationError):
        CanonicalCapabilityRef.parse(value)


def test_canonical_ref_rejects_overlong_namespace_and_semantic_key() -> None:
    with pytest.raises(ValidationError):
        CanonicalCapabilityRef.parse(f"capability:{'n' * 65}:valid_key")

    with pytest.raises(ValidationError):
        CanonicalCapabilityRef.parse(f"capability:valid_ns:{'k' * 129}")


def test_canonical_ref_accepts_documented_maximum_lengths() -> None:
    ref = CanonicalCapabilityRef.parse(f"capability:{'n' * 64}:{'k' * 128}")

    assert len(ref.namespace_key) == 64
    assert len(ref.semantic_key) == 128


def test_syntactically_valid_unknown_namespace_is_allowed() -> None:
    ref = CanonicalCapabilityRef.parse("capability:future_domain:valid_concept")

    assert ref.namespace_key == "future_domain"


def test_source_semantic_ref_preserves_role_requirement_identity() -> None:
    source_ref = SourceSemanticRef(
        source_namespace="role_profile",
        entity_kind=SourceSemanticKind.ROLE_REQUIREMENT,
        source_id="req-123",
        source_version="profile-v4",
    )

    assert source_ref.source_id == "req-123"
    assert source_ref.entity_kind is SourceSemanticKind.ROLE_REQUIREMENT
    with pytest.raises(ValidationError):
        CanonicalCapabilityRef.parse(source_ref.source_id)


def test_role_requirement_id_remains_source_owned_identity() -> None:
    from app.matching.schemas import RequirementClassification, RoleRequirement

    requirement = RoleRequirement(
        id="req-123",
        classification=RequirementClassification.ROLE_CRITICAL,
        evidence_terms=["project coordination"],
        confidence_threshold=0.7,
        assessment_recommendation="review evidence",
        rubric_version="1",
    )
    source_ref = SourceSemanticRef(
        source_namespace="role_profile",
        entity_kind=SourceSemanticKind.ROLE_REQUIREMENT,
        source_id=requirement.id,
    )
    identity_pair = CapabilityIdentityPair(source_ref=source_ref)

    assert requirement.id == identity_pair.source_ref.source_id == "req-123"
    assert identity_pair.canonical_capability_ref is None


def test_learning_need_competency_id_is_preserved_as_source_lineage() -> None:
    from app.learning_need_profile.schemas import LearningNeedCompetency

    competency = LearningNeedCompetency(id="req-123", name="Project coordination", description=None)
    identity_pair = CapabilityIdentityPair(
        source_ref=SourceSemanticRef(
            source_namespace="learning_need",
            entity_kind=SourceSemanticKind.LEARNING_NEED_COMPETENCY,
            source_id=competency.id,
        )
    )

    assert competency.id == identity_pair.source_ref.source_id == "req-123"
    assert identity_pair.canonical_capability_ref is None


def test_course_ref_remains_distinct_from_canonical_capability_ref() -> None:
    course_ref = "skillscommons:course-7"
    source_ref = SourceSemanticRef(
        source_namespace="skillscommons",
        entity_kind=SourceSemanticKind.COURSE_LEARNING_OUTCOME,
        source_id="course-7/outcome/1",
    )

    assert source_ref.source_id != course_ref
    with pytest.raises(ValidationError):
        CanonicalCapabilityRef.parse(course_ref)


def test_source_semantic_ref_represents_course_outcomes_and_provider_values() -> None:
    outcome = SourceSemanticRef(
        source_namespace="skillscommons",
        entity_kind=SourceSemanticKind.COURSE_LEARNING_OUTCOME,
        source_id="course-uuid/outcome/1",
    )
    provider_subject = SourceSemanticRef(
        source_namespace="skillscommons",
        entity_kind=SourceSemanticKind.PROVIDER_CLASSIFICATION,
        source_id="dc.subject:project management",
    )

    assert outcome.source_id == "course-uuid/outcome/1"
    assert provider_subject.source_id == "dc.subject:project management"


def test_source_semantic_ref_rejects_empty_or_ambiguous_identity_parts() -> None:
    with pytest.raises(ValidationError):
        SourceSemanticRef(
            source_namespace="role profile",
            entity_kind=SourceSemanticKind.ROLE_REQUIREMENT,
            source_id="req-123",
        )

    with pytest.raises(ValidationError):
        SourceSemanticRef(
            source_namespace="role_profile",
            entity_kind=SourceSemanticKind.ROLE_REQUIREMENT,
            source_id=" req-123",
        )


@pytest.mark.parametrize(
    ("source_namespace", "source_id"),
    [
        ("provider", "Project Management"),
        ("provider", "dc.subject:project management"),
        ("taxonomy", "professional_capability_core@0.1"),
        ("course", "skillscommons:course-7"),
    ],
)
def test_source_and_display_values_are_not_canonical_capability_refs(
    source_namespace: str, source_id: str
) -> None:
    source_ref = SourceSemanticRef(
        source_namespace=source_namespace,
        entity_kind=SourceSemanticKind.PROVIDER_CLASSIFICATION,
        source_id=source_id,
    )

    assert source_ref.source_id == source_id
    with pytest.raises(ValidationError):
        CanonicalCapabilityRef.parse(source_ref.source_id)


def test_dual_identity_allows_unmapped_source_without_fabricated_capability() -> None:
    source_ref = SourceSemanticRef(
        source_namespace="role_profile",
        entity_kind=SourceSemanticKind.ROLE_REQUIREMENT,
        source_id="req-123",
    )
    pair = CapabilityIdentityPair(source_ref=source_ref)

    assert pair.source_ref == source_ref
    assert pair.canonical_capability_ref is None


def test_dual_identity_keeps_source_and_canonical_refs_as_distinct_types() -> None:
    pair = CapabilityIdentityPair(
        source_ref=SourceSemanticRef(
            source_namespace="course",
            entity_kind=SourceSemanticKind.COURSE_DIRECT_CLAIM,
            source_id="skillscommons:course-7/claim/2",
        ),
        canonical_capability_ref=CanonicalCapabilityRef.parse(
            "capability:project:project_management"
        ),
    )

    assert pair.model_dump(mode="json") == {
        "source_ref": {
            "source_namespace": "course",
            "entity_kind": "course_direct_claim",
            "source_id": "skillscommons:course-7/claim/2",
            "source_version": None,
        },
        "canonical_capability_ref": "capability:project:project_management",
    }

    with pytest.raises(ValidationError):
        CapabilityIdentityPair(
            source_ref="req-123",  # type: ignore[arg-type]
            canonical_capability_ref="capability:project:project_management",  # type: ignore[arg-type]
        )


def test_identity_contracts_are_immutable_and_do_not_change_existing_catalog_schema() -> None:
    ref = CanonicalCapabilityRef.parse("capability:software:programming_fundamentals")

    with pytest.raises(ValidationError):
        ref.root = "capability:software:other"  # type: ignore[misc]

    with pytest.raises(ValidationError):
        SourceSemanticRef(
            source_namespace="provider",
            entity_kind="provider_classification",  # type: ignore[arg-type]
            source_id="dc.subject:finance",
        )


def test_course_profile_legacy_opaque_capability_ref_remains_accepted() -> None:
    from app.course_catalog.schemas import (
        CourseAvailability,
        CourseCapability,
        CourseCapabilityProfile,
        CourseProfileStatus,
        CourseProvenance,
        CourseSourceType,
        CoverageType,
    )

    profile = CourseCapabilityProfile(
        id="legacy-profile",
        version=1,
        course_ref="internal:course-1",
        source_type=CourseSourceType.INTERNAL,
        source_system="test",
        title_snapshot="Existing Course",
        capabilities=[
            CourseCapability(
                capability_ref="project_management",
                coverage_type=CoverageType.DIRECT,
                provenance=[
                    CourseProvenance(
                        kind="manual",
                        source_ref="course:course-1",
                        method="human_review",
                    )
                ],
            )
        ],
        status=CourseProfileStatus.DRAFT,
        availability=CourseAvailability.UNKNOWN,
        provenance=[
            CourseProvenance(
                kind="catalog",
                source_ref="internal:course-1",
                method="fixture",
            )
        ],
    )

    assert profile.capabilities[0].capability_ref == "project_management"
