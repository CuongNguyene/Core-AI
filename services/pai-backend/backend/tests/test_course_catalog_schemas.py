import pytest
from pydantic import ValidationError

from app.course_catalog.schemas import (
    CourseAvailability,
    CourseCapability,
    CourseCapabilityProfile,
    CoursePrerequisite,
    CourseProfileStatus,
    CourseProvenance,
    CourseSourceType,
    CoverageType,
    ExternalCourse,
    NormalizedCourseCandidate,
)


def _provenance(kind: str = "manual_mapping") -> CourseProvenance:
    return CourseProvenance(
        kind=kind,
        source_ref="fixture:course-001",
        source_field="capabilities",
        method="fixture_authoring",
    )


def _capability(ref: str = "capability:feedback") -> CourseCapability:
    return CourseCapability(
        capability_ref=ref,
        coverage_type=CoverageType.DIRECT,
        target_level=None,
        provenance=[_provenance()],
    )


def _profile(source_type: CourseSourceType = CourseSourceType.INTERNAL) -> CourseCapabilityProfile:
    return CourseCapabilityProfile(
        id="course-profile:fixture-001",
        version=1,
        course_ref="frappe_lms:COURSE-001",
        source_type=source_type,
        source_system="frappe_lms" if source_type is CourseSourceType.INTERNAL else "mock_provider",
        provider_ref="mock_provider" if source_type is CourseSourceType.EXTERNAL else None,
        provider_course_id="external-001" if source_type is CourseSourceType.EXTERNAL else None,
        title_snapshot="Feedback Fundamentals",
        capabilities=[_capability()],
        prerequisites=[CoursePrerequisite(kind="capability", ref="capability:active-listening")],
        duration_minutes=90,
        delivery_mode="self_paced",
        language="en",
        availability=CourseAvailability.AVAILABLE,
        status=CourseProfileStatus.ACTIVE,
        provenance=[_provenance("source_fact")],
    )


def test_valid_internal_profile_normalizes_to_candidate() -> None:
    profile = _profile()

    candidate = profile.to_normalized_candidate()

    assert candidate.course_ref == "frappe_lms:COURSE-001"
    assert candidate.source_type is CourseSourceType.INTERNAL
    assert candidate.capabilities[0].capability_ref == "capability:feedback"
    assert candidate.target_level is None


def test_valid_external_profile_requires_provider_identity() -> None:
    profile = _profile(CourseSourceType.EXTERNAL)

    assert profile.provider_ref == "mock_provider"
    assert profile.provider_course_id == "external-001"
    assert profile.to_normalized_candidate().provider_course_id == "external-001"


def test_internal_profile_rejects_provider_identity() -> None:
    with pytest.raises(ValidationError, match="provider"):
        CourseCapabilityProfile(
            **_profile().model_dump(exclude={"provider_ref"}),
            provider_ref="mock_provider",
        )


def test_external_profile_rejects_missing_provider_identity() -> None:
    with pytest.raises(ValidationError, match="provider"):
        CourseCapabilityProfile(
            **_profile(CourseSourceType.EXTERNAL).model_dump(exclude={"provider_course_id"}),
            provider_course_id=None,
        )


def test_duplicate_capabilities_are_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate"):
        CourseCapabilityProfile(
            **_profile().model_dump(exclude={"capabilities"}),
            capabilities=[_capability(), _capability()],
        )


def test_duration_must_be_non_negative() -> None:
    with pytest.raises(ValidationError):
        CourseCapabilityProfile(
            **_profile().model_dump(exclude={"duration_minutes"}),
            duration_minutes=-1,
        )


def test_prerequisites_and_unknown_level_are_explicitly_nullable() -> None:
    profile = CourseCapabilityProfile(
        **_profile().model_dump(exclude={"target_level", "prerequisites"}),
        target_level=None,
        prerequisites=[],
    )

    assert profile.target_level is None
    assert profile.prerequisites == []


def test_provenance_requires_source_reference_and_method() -> None:
    with pytest.raises(ValidationError):
        CourseProvenance(kind="manual_mapping", source_ref="", method="fixture_authoring")


def test_external_course_has_provider_facts_without_capability_semantics() -> None:
    course = ExternalCourse(
        provider_ref="mock_provider",
        provider_course_id="external-001",
        title="Feedback Fundamentals",
        description="Synthetic provider course.",
        duration_minutes=90,
        delivery_mode="self_paced",
        language="en",
        availability=CourseAvailability.AVAILABLE,
        course_url="https://example.invalid/courses/external-001",
        provenance=[_provenance("provider_metadata")],
    )

    assert course.provider_course_id == "external-001"
    assert not hasattr(course, "capabilities")


def test_normalized_candidate_rejects_missing_external_provider_identity() -> None:
    with pytest.raises(ValidationError, match="provider"):
        NormalizedCourseCandidate(
            course_ref="mock_provider:external-001",
            source_type=CourseSourceType.EXTERNAL,
            source_system="mock_provider",
            title="Feedback Fundamentals",
            capabilities=[_capability()],
            provenance=[_provenance()],
        )


def test_normalized_candidate_rejects_provider_identity_for_internal_course() -> None:
    with pytest.raises(ValidationError, match="provider"):
        NormalizedCourseCandidate(
            course_ref="frappe_lms:COURSE-001",
            source_type=CourseSourceType.INTERNAL,
            source_system="frappe_lms",
            provider_ref="mock_provider",
            title="Feedback Fundamentals",
            capabilities=[_capability()],
            provenance=[_provenance()],
        )


def test_external_provider_candidate_can_be_unprofiled_before_manual_capability_mapping() -> None:
    candidate = NormalizedCourseCandidate(
        course_ref="openedx:course-v1:demo+101+2026",
        source_type=CourseSourceType.EXTERNAL,
        source_system="openedx",
        provider_ref="openedx",
        provider_course_id="course-v1:demo+101+2026",
        title="Open edX Fundamentals",
        capabilities=[],
        prerequisites=[],
        target_level=None,
        duration_minutes=None,
        availability=CourseAvailability.UNKNOWN,
        provenance=[_provenance("provider_metadata")],
    )

    assert candidate.capabilities == []
