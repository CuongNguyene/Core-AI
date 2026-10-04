from __future__ import annotations

import pytest

from app.course_catalog.schemas import (
    CourseAvailability,
    CourseCapability,
    CoursePrerequisite,
    CourseProfileStatus,
    CourseProvenance,
    CourseSourceType,
    CoverageType,
    NormalizedCourseCandidate,
)
from app.course_recommendation import (
    CourseRecommendationCandidate,
    CourseRecommendationEngine,
    CourseRecommendationRequest,
    CoverageStatus,
    LevelCompatibility,
    RecommendationTarget,
    candidate_from_profile,
)
from app.course_recommendation.schemas import (
    PrerequisiteStatus,
    RecommendationPrerequisiteContext,
)

ENGINE = CourseRecommendationEngine()


def provenance(ref: str) -> CourseProvenance:
    return CourseProvenance(kind="fixture", source_ref=ref, method="test_fixture")


def candidate(
    ref: str,
    *capabilities: str,
    source_type: CourseSourceType = CourseSourceType.INTERNAL,
    availability: CourseAvailability = CourseAvailability.AVAILABLE,
    target_level: str | None = None,
    prerequisites: list[CoursePrerequisite] | None = None,
    profile_status: CourseProfileStatus = CourseProfileStatus.ACTIVE,
    provider_ref: str | None = None,
) -> CourseRecommendationCandidate:
    normalized = NormalizedCourseCandidate(
        course_ref=ref,
        source_type=source_type,
        source_system="frappe_lms" if source_type is CourseSourceType.INTERNAL else "skillscommons",
        provider_ref=provider_ref if source_type is CourseSourceType.EXTERNAL else None,
        provider_course_id=f"id:{ref}" if source_type is CourseSourceType.EXTERNAL else None,
        title=f"Course {ref}",
        description="Description does not participate in matching.",
        capabilities=[
            CourseCapability(
                capability_ref=capability,
                coverage_type=CoverageType.DIRECT,
                target_level=target_level,
                provenance=[provenance(ref)],
            )
            for capability in capabilities
        ],
        prerequisites=prerequisites or [],
        target_level=target_level,
        availability=availability,
        provenance=[provenance(ref)],
    )
    return CourseRecommendationCandidate(course=normalized, profile_status=profile_status)


def request(
    *candidates: CourseRecommendationCandidate,
    capabilities: list[str] | None = None,
    target_level: str | None = None,
    context: RecommendationPrerequisiteContext | None = None,
    max_results: int = 5,
    **trace: str,
) -> CourseRecommendationRequest:
    return CourseRecommendationRequest(
        recommendation_target=RecommendationTarget(
            target_ref="learning-target:001",
            target_capability_refs=capabilities if capabilities is not None else ["cap:python"],
            target_level=target_level,
            prerequisite_context=context or RecommendationPrerequisiteContext(),
            **trace,
        ),
        candidates=list(candidates),
        max_results=max_results,
    )


def test_exact_single_capability_match_is_recommended() -> None:
    result = ENGINE.recommend(request(candidate("course:python", "cap:python")))
    assert [item.course_ref for item in result.recommendations] == ["course:python"]
    assert result.recommendations[0].coverage_status is CoverageStatus.FULL_COVERAGE
    assert result.recommendations[0].decision_details.coverage.matched_target_capability_refs == [
        "cap:python"
    ]


def test_no_capability_match_is_excluded() -> None:
    result = ENGINE.recommend(request(candidate("course:sales", "cap:sales")))
    assert result.recommendations == []
    assert result.no_suitable_reason == "NO_SUITABLE_COURSE"
    assert result.rejected_summary["NO_CAPABILITY_MATCH"] == 1


def test_full_multi_capability_coverage_ranks_above_partial() -> None:
    full = candidate("course:full", "cap:python", "cap:testing")
    partial = candidate("course:partial", "cap:python")
    result = ENGINE.recommend(request(full, partial, capabilities=["cap:python", "cap:testing"]))
    assert [item.course_ref for item in result.recommendations] == ["course:full", "course:partial"]
    assert result.recommendations[0].coverage_status is CoverageStatus.FULL_COVERAGE
    assert result.recommendations[1].coverage_status is CoverageStatus.PARTIAL_COVERAGE
    assert result.recommendations[1].missing_target_capability_refs == ["cap:testing"]


def test_unavailable_is_excluded_and_unknown_is_retained_with_warning() -> None:
    unavailable = candidate(
        "course:unavailable", "cap:python", availability=CourseAvailability.UNAVAILABLE
    )
    unknown = candidate("course:unknown", "cap:python", availability=CourseAvailability.UNKNOWN)
    available = candidate("course:available", "cap:python")
    result = ENGINE.recommend(request(unavailable, unknown, available))
    assert [item.course_ref for item in result.recommendations] == [
        "course:available",
        "course:unknown",
    ]
    assert result.recommendations[1].warnings == ["AVAILABILITY_UNKNOWN"]
    assert result.rejected_summary["COURSE_UNAVAILABLE"] == 1


@pytest.mark.parametrize("status", [CourseProfileStatus.DRAFT, CourseProfileStatus.DEPRECATED])
def test_only_active_profiles_are_eligible(status: CourseProfileStatus) -> None:
    inactive = candidate("course:inactive", "cap:python", profile_status=status)
    result = ENGINE.recommend(request(inactive))
    assert result.recommendations == []
    assert result.rejected_summary["PROFILE_NOT_ACTIVE"] == 1


def test_empty_capabilities_are_not_semantic_recommendation_candidates() -> None:
    provider_only = candidate("skillscommons:raw", provider_ref="skillscommons")
    result = ENGINE.recommend(request(provider_only))
    assert result.recommendations == []
    assert result.rejected_summary["NO_SEMANTIC_CAPABILITIES"] == 1


def test_prerequisite_satisfied_ranks_above_unknown_and_unsatisfied_is_excluded() -> None:
    prerequisite = CoursePrerequisite(kind="capability", ref="cap:basics")
    satisfied = candidate("course:satisfied", "cap:python", prerequisites=[prerequisite])
    result = ENGINE.recommend(
        request(
            satisfied,
            context=RecommendationPrerequisiteContext(known_capability_refs=["cap:basics"]),
        )
    )
    assert result.recommendations[0].prerequisite_status is PrerequisiteStatus.SATISFIED

    unknown = candidate("course:unknown", "cap:python", prerequisites=[prerequisite])
    unknown_result = ENGINE.recommend(request(unknown))
    assert unknown_result.recommendations[0].prerequisite_status is PrerequisiteStatus.UNKNOWN

    unsatisfied = candidate("course:unsatisfied", "cap:python", prerequisites=[prerequisite])
    unsatisfied_result = ENGINE.recommend(
        request(
            unsatisfied,
            context=RecommendationPrerequisiteContext(known_capability_refs=["cap:other"]),
        )
    )
    assert unsatisfied_result.recommendations == []


def test_explicitly_unsatisfied_prerequisite_is_excluded_when_context_is_explicit() -> None:
    prerequisite = CoursePrerequisite(kind="capability", ref="cap:basics")
    course = candidate("course:python", "cap:python", prerequisites=[prerequisite])
    context = RecommendationPrerequisiteContext(known_capability_refs=["cap:other"])
    result = ENGINE.recommend(request(course, context=context))
    assert result.recommendations == []
    assert result.rejected_summary["PREREQUISITE_UNSATISFIED"] == 1


def test_missing_prerequisite_evidence_is_unknown_not_unsatisfied() -> None:
    prerequisite = CoursePrerequisite(kind="course", ref="course:basics")
    result = ENGINE.recommend(
        request(candidate("course:python", "cap:python", prerequisites=[prerequisite]))
    )
    assert result.recommendations[0].prerequisite_status is PrerequisiteStatus.UNKNOWN
    assert "PREREQUISITE_STATUS_UNKNOWN" in result.recommendations[0].warnings


def test_unsupported_prerequisite_kind_is_unknown() -> None:
    prerequisite = CoursePrerequisite(kind="unsupported", ref="opaque")
    result = ENGINE.recommend(
        request(candidate("course:python", "cap:python", prerequisites=[prerequisite]))
    )
    assert result.recommendations[0].prerequisite_status is PrerequisiteStatus.UNKNOWN


def test_level_is_equality_only_without_invented_ordering() -> None:
    exact = candidate("course:exact", "cap:python", target_level="advanced")
    different = candidate("course:different", "cap:python", target_level="beginner")
    unknown = candidate("course:unknown", "cap:python")
    result = ENGINE.recommend(request(exact, different, unknown, target_level="advanced"))
    assert [item.course_ref for item in result.recommendations] == [
        "course:exact",
        "course:different",
        "course:unknown",
    ]
    assert result.recommendations[0].level_status is LevelCompatibility.EXACT
    assert result.recommendations[1].level_status is LevelCompatibility.DIFFERENT
    assert result.recommendations[2].level_status is LevelCompatibility.UNKNOWN


def test_internal_external_parity_has_no_source_preference() -> None:
    internal = candidate("course:internal", "cap:python")
    external = candidate(
        "course:external",
        "cap:python",
        source_type=CourseSourceType.EXTERNAL,
        provider_ref="skillscommons",
    )
    result = ENGINE.recommend(request(internal, external))
    assert result.recommendations[0].decision_details == result.recommendations[1].decision_details
    assert result.recommendations[0].coverage_status is result.recommendations[1].coverage_status


def test_duration_and_provider_do_not_change_semantic_rank_factors() -> None:
    short = candidate("course:short", "cap:python")
    long = candidate("course:long", "cap:python")
    result = ENGINE.recommend(request(short, long))
    assert [item.course_ref for item in result.recommendations] == ["course:long", "course:short"]
    assert result.recommendations[0].decision_details == result.recommendations[1].decision_details


def test_course_ref_is_stable_tie_breaker_and_input_order_independent() -> None:
    items = [candidate("course:z", "cap:python"), candidate("course:a", "cap:python")]
    first = ENGINE.recommend(request(*items)).model_dump(mode="json")
    second = ENGINE.recommend(request(*reversed(items))).model_dump(mode="json")
    assert first == second
    assert [item["course_ref"] for item in first["recommendations"]] == ["course:a", "course:z"]


def test_top_k_is_bounded_and_ranking_precedes_truncation() -> None:
    items = [candidate(f"course:{index:02d}", "cap:python") for index in range(8)]
    result = ENGINE.recommend(request(*items, max_results=3))
    assert len(result.recommendations) == 3
    assert [item.course_ref for item in result.recommendations] == [
        "course:00",
        "course:01",
        "course:02",
    ]


def test_duplicate_course_refs_are_rejected() -> None:
    with pytest.raises(ValueError, match="course_ref"):
        request(
            candidate("course:duplicate", "cap:python"), candidate("course:duplicate", "cap:python")
        )


def test_no_target_capabilities_returns_no_suitable_course_without_inference() -> None:
    result = ENGINE.recommend(request(candidate("course:title-only", "cap:other"), capabilities=[]))
    assert result.recommendations == []
    assert result.no_suitable_reason == "NO_TARGET_CAPABILITIES"


def test_trace_refs_are_preserved_without_raw_text() -> None:
    result = ENGINE.recommend(
        request(
            candidate("course:python", "cap:python"),
            source_learning_need_ref="need:001",
            source_learning_path_ref="path:001",
            source_path_step_ref="step:001",
            source_gap_refs=["gap:001"],
            source_role_requirement_refs=["role-req:001"],
        )
    )
    assert result.provenance.learning_need_ref == "need:001"
    assert result.provenance.gap_refs == ["gap:001"]
    assert "Description does not participate" not in result.model_dump_json()


@pytest.mark.parametrize(
    ("domain", "capability"),
    [
        ("software", "cap:python"),
        ("sales", "cap:negotiation"),
        ("finance", "cap:budgeting"),
        ("hr", "cap:facilitation"),
    ],
)
def test_cross_domain_behavior_is_domain_neutral(domain: str, capability: str) -> None:
    result = ENGINE.recommend(
        request(candidate(f"course:{domain}", capability), capabilities=[capability])
    )
    assert [item.course_ref for item in result.recommendations] == [f"course:{domain}"]


def test_skillscommons_raw_candidate_is_ineligible_until_semantically_enriched() -> None:
    raw = candidate("skillscommons:raw", provider_ref="skillscommons")
    enriched = candidate("skillscommons:raw", "cap:python", provider_ref="skillscommons")
    raw_result = ENGINE.recommend(request(raw))
    enriched_result = ENGINE.recommend(request(enriched))
    assert raw_result.recommendations == []
    assert enriched_result.recommendations[0].course_ref == "skillscommons:raw"


def test_profile_assembly_preserves_lifecycle_and_semantic_claims() -> None:
    from app.course_catalog.schemas import CourseCapability, CourseCapabilityProfile

    profile = CourseCapabilityProfile(
        id="profile:python",
        version=1,
        course_ref="frappe_lms:python",
        source_type=CourseSourceType.INTERNAL,
        source_system="frappe_lms",
        title_snapshot="Python",
        capabilities=[
            CourseCapability(
                capability_ref="cap:python",
                coverage_type=CoverageType.DIRECT,
                provenance=[provenance("frappe_lms:python")],
            )
        ],
        availability=CourseAvailability.AVAILABLE,
        status=CourseProfileStatus.DRAFT,
        provenance=[provenance("profile:python")],
    )
    assembled = candidate_from_profile(profile)
    assert assembled.profile_status is CourseProfileStatus.DRAFT
    assert assembled.course.capabilities[0].capability_ref == "cap:python"
