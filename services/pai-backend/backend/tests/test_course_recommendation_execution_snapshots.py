from __future__ import annotations

import json

import pytest
import test_course_rec_3d6_end_to_end as fixtures
import test_governed_course_projection as direct_claim_fixtures
import test_governed_target_adapter as target_fixtures

from app.capability_governance.course_projection import project_governed_course_capabilities
from app.course_recommendation.execution_snapshots import (
    RecommendationSnapshotInconsistent,
    build_execution_snapshots,
    request_fingerprint,
)


def _inputs():
    release = target_fixtures._active_release()
    target, _ = fixtures._target_projection((fixtures.CAPABILITY_COMMUNICATION,), release)
    _, course, _, _ = fixtures._course_projection(
        course_ref="skillscommons:course-snapshot",
        capability_refs=(fixtures.CAPABILITY_COMMUNICATION,),
        release=release,
    )
    return target, course


def test_builds_exact_request_and_minimized_governance_snapshot() -> None:
    target, course = _inputs()

    request, governance = build_execution_snapshots(target, (course,), max_results=3)

    assert request.recommendation_target == target.recommendation_target
    assert request.candidates[0].course == course.normalized_candidate
    assert request.max_results == 3
    assert governance.target.role_profile_id == target.role_profile_id
    assert governance.target.definition_pins == target.definition_pins
    assert governance.courses[0].course_ref == course.course_ref
    assert governance.courses[0].coverage[0].model_dump(mode="json") == {
        **course.coverage[0].model_dump(mode="json"),
        "sources": [
            {
                **course.coverage[0].sources[0].model_dump(mode="json"),
                "mapping_scope": course.coverage[0].sources[0].mapping_scope.value,
                "resolution_mode": course.coverage[0].sources[0].resolution_mode.value,
            }
        ],
    }
    encoded = governance.model_dump_json()
    assert '"requirements"' not in encoded
    assert "gap_entries" not in encoded
    assert json.loads(encoded)["schema_version"] == "1.0"
    assert governance.__class__.model_validate_json(encoded) == governance
    assert request.__class__.model_validate_json(request.model_dump_json()) == request


def test_rejects_target_refs_that_disagree_with_projection() -> None:
    target, course = _inputs()
    wrong_target = target.recommendation_target.model_copy(
        update={"target_capability_refs": [fixtures.CAPABILITY_WRITING]}
    )
    malformed = target.model_copy(update={"recommendation_target": wrong_target})

    with pytest.raises(RecommendationSnapshotInconsistent):
        build_execution_snapshots(malformed, (course,))


def test_draft_course_projection_is_not_recommendation_eligible() -> None:
    release = target_fixtures._active_release()
    target, _ = fixtures._target_projection((fixtures.CAPABILITY_COMMUNICATION,), release)
    _, draft, _, _ = fixtures._course_projection(
        course_ref="skillscommons:course-draft",
        capability_refs=(fixtures.CAPABILITY_COMMUNICATION,),
        release=release,
        profile_status=fixtures.CourseProfileStatus.DRAFT,
    )

    with pytest.raises(RecommendationSnapshotInconsistent):
        build_execution_snapshots(target, (draft,))


def test_rejects_course_coverage_that_does_not_match_candidate() -> None:
    target, course = _inputs()
    malformed = course.model_copy(update={"coverage": ()})

    with pytest.raises(RecommendationSnapshotInconsistent):
        build_execution_snapshots(target, (malformed,))


def test_rejects_current_target_course_join_with_different_definition_pin() -> None:
    target_release = target_fixtures._active_release("1.0")
    course_release = target_fixtures._active_release("2.0")
    target, _ = fixtures._target_projection((fixtures.CAPABILITY_COMMUNICATION,), target_release)
    _, course, _, _ = fixtures._course_projection(
        course_ref="skillscommons:course-pin-mismatch",
        capability_refs=(fixtures.CAPABILITY_COMMUNICATION,),
        release=course_release,
    )

    with pytest.raises(
        RecommendationSnapshotInconsistent, match="canonical_definition_pin_mismatch"
    ):
        build_execution_snapshots(target, (course,))


def test_request_fingerprint_is_stable_for_candidate_order() -> None:
    target, course_a = _inputs()
    release = target_fixtures._active_release()
    _, course_b, _, _ = fixtures._course_projection(
        course_ref="skillscommons:course-snapshot-b",
        capability_refs=(fixtures.CAPABILITY_COMMUNICATION,),
        release=release,
    )
    req_a, gov_a = build_execution_snapshots(target, (course_a, course_b))
    req_b, gov_b = build_execution_snapshots(target, (course_b, course_a))

    assert [item.course.course_ref for item in req_a.candidates] == sorted(
        item.course.course_ref for item in req_a.candidates
    )
    assert request_fingerprint(req_a, gov_a) == request_fingerprint(req_b, gov_b)


def test_internal_candidate_and_dc1_direct_claim_identity_round_trip() -> None:
    release = target_fixtures._active_release()
    target, _ = fixtures._target_projection((fixtures.CAPABILITY_COMMUNICATION,), release)
    _, internal_course, _, _ = fixtures._course_projection(
        course_ref="frappe_lms:internal-course",
        capability_refs=(fixtures.CAPABILITY_COMMUNICATION,),
        release=release,
        source_type=fixtures.CourseSourceType.INTERNAL,
    )
    internal_request, _ = build_execution_snapshots(target, (internal_course,))
    assert internal_request.candidates[0].course.source_type is fixtures.CourseSourceType.INTERNAL

    direct_release = direct_claim_fixtures._active_release()
    direct_target, _ = fixtures._target_projection(
        (direct_claim_fixtures.CAPABILITY_REF,), direct_release
    )
    direct_input, _ = direct_claim_fixtures._direct_input()
    active_profile = direct_claim_fixtures._profile(status=fixtures.CourseProfileStatus.ACTIVE)
    direct_projection = project_governed_course_capabilities(
        active_profile,
        direct_claims=(direct_input,),
        active_release_context=(direct_release,),
    )
    _, direct_governance = build_execution_snapshots(direct_target, (direct_projection,))
    source_id = direct_governance.courses[0].coverage[0].sources[0].source_ref.source_id
    assert source_id.startswith("dc1_")
    round_trip = direct_governance.__class__.model_validate_json(
        direct_governance.model_dump_json()
    )
    assert round_trip.courses[0].coverage[0].sources[0].source_ref.source_id == source_id
